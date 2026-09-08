import multiprocessing as mp
from queue import Queue, Empty
import threading
import os
import time
import uuid
import atexit
import sys
from io import BytesIO
import appQueue
from tools import setup_logger, OUTPUT_DIR
from tools import erase_output_folder, auto_erase_output_folder, make_dir, setup_logger, read_file
from appSecurity import decrypt_credentials, decrypt_func,generate_secret

# ======================
# 🔹 Consts
# ======================

WORKER_TYPE_PROCESS = "Process"
WORKER_TYPE_THREAD = "Thread"

APP_WORKER_INSTANCE_NAME = "AppWorker"
APP_WORKER_CHILD_INSTANCE_NAME = "AppChildWorker"

CHILD_WORKER_TIME_OUT_LIMIT_SECONDS = 10 * 60 # 10 minutes

DEFAULT_CHILD_WORKER_JOIN_TIMEOUT = 2
DEFAULT_WORKER_JOIN_TIMEOUT = 5
DEFAULT_JOIN_TIMEOUT = 2

DEFAULT_CHILD_WORKER_SLEEP_TIMEOUT = 1
DEFAULT_WORKERS_MONITOR_SLEEP_TIMEOUT = 1

DEFAULT_POOL_SIZE = 5
MAX_POOL_SIZE = 15

DEFAULT_MULTI_PROCESS_MODE = True
CLIENT_SESSION_TIMEOUT_SECONDS = 15 * 60  # 15 minutes

WORKER_EVENT                 = "__WORKER_EVENT__"
POOL_EVENT                   = "__POOL_EVENT__"

STOP_EVENT_TOKEN             = "__STOP_WORKER__"
REQ_PENDING_EVENT_TOKEN      = "__REQ_PENDING__"
SEE_CLIENT_EVENT_TOKEN       = "__SEE_CLIENT__"
CLIENT_HEARTBEAT_EVENT_TOKEN = "__CLIENT_HEARTBEAT__"
REMOVE_CLIENT_EVENT_TOKEN    = "__REMOVE_CLIENT__"
ABORT_OPERATION_EVENT_TOKEN  = "__ABORT_OPERATION_FOR_CLIENT__"

WORKER_STATE_IDLE       = "IDLE"
WORKER_STATE_PROCESSING = "PROCESSING"
WORKER_STATE_ERROR      = "ERROR"
WORKER_STATE_STOPPED    = "STOPPED"
WORKER_STATE_WANTED     = "WANTED"
WORKER_STATE_SHUTDOWN   = "SHUTDOWN"
WORKER_STATE_GARBAGED   = "GARBAGED"
WORKER_STATE_DEADLOCK   = "DEAD_LOCKED"

THRESHOLD_NB_THREADS_DEADLOCKED = 20

# ========================
# Globals
# ========================
thread_mode = False
logger_debug = print
app_worker_instance = None
#workers
workers_process_mode = True
workers_task_queue = None
workers_state_queue = None
#Worker Monitoring
workers_instance = {} # {worker_name: {"obj": t/p, "state": "Idle"}}
threads_garbage_collector = {} # {id: {"obj":t}}
client_active = {}  # {client_id: worker_name}
worker_states = {}  # key: worker_name, value: dict {state, client_id, timestamp}
workers_monitor_stopped = True
workers_monitor_thread = None
#Cleaner for client id
cleaner_worker_thread = None
stop_cleaner_worker_thread = False
client_last_seen = {}

# ========================
# App Worker General
# ========================

def initAppWorker(muliproc_mode,pool_size,eras_outputs=False, prt_debug=print):
    
    global logger_debug, thread_mode
    
    logger_debug = prt_debug
    
    if eras_outputs:
        erase_output_folder(logger_debug)
    else:
        auto_erase_output_folder(logger_debug)    
    
    thread_mode = not muliproc_mode
    
    if not decrypt_credentials():
        return False
        
    return startAppWorkerInstance(muliproc_mode,pool_size)
        
def stopAppWorker(prt_debug,force=False):
    global logger_debug
    logger_debug = prt_debug
    
    stopAppWorkerInstance(force)

def new_client(muliproc_mode = DEFAULT_MULTI_PROCESS_MODE, prt_debug=print):
    """Register a new client with unique client_id."""
    global logger_debug
    
    client_id = str(uuid.uuid4())
    
    logger_debug = prt_debug

    res = appQueue.init_queues(client_id,
                               sharedQueue=muliproc_mode,
                               startServerCb=startAppWorkerProc,
                               prt_debug=logger_debug,
                               newClient=True)
    
    if res == True:
        logger_debug(f"[AppWorker] New client registered: {client_id}, multi-process mode is {muliproc_mode}")

        keep_alive_session(client_id)
        
        appQueue.setClientSecret(client_id,generate_secret())
       
        return client_id
    else:
        return -1
        
def remove_client(client_id):
    if client_id and appQueue.IsQueueInitialized():
        return send_msg_to_app_worker(client_id,REMOVE_CLIENT_EVENT_TOKEN)
    else:
        return True

def set_client_context(client_id,muliproc_mode = DEFAULT_MULTI_PROCESS_MODE) -> bool:
    
    if muliproc_mode == True:
        ##client mode, server is normally already started by another process
        init = appQueue.IsQueueInitialized()

        if init == False:
            res = appQueue.init_queues(client_id,
                                       sharedQueue=muliproc_mode,
                                       startServerCb=None,
                                       prt_debug=logger_debug,
                                       newClient=False)
            if res == False: return False

    return appQueue.IsClientRegistered(client_id)

def execute_request(client_id, worker_func, extra_args=None):
    
    appQueue.appendRequest(client_id, worker_func, extra_args)
    
    return send_msg_to_app_worker(client_id, REQ_PENDING_EVENT_TOKEN,POOL_EVENT)
    
def abort_execution(client_id):
    if client_id and appQueue.IsQueueInitialized():
        return send_msg_to_app_worker(client_id,ABORT_OPERATION_EVENT_TOKEN)
    else:
        return True    

def register_client_hearbeat(client_id):
    if client_id and appQueue.IsQueueInitialized():
        return send_msg_to_app_worker(client_id,CLIENT_HEARTBEAT_EVENT_TOKEN)
    else:
        return True 
        
def request_execution_listener(client_id, stream_type,timeout = appQueue.DEFAULT_GET_TIMEOUT):
    return appQueue.event_stream(client_id, stream_type,timeout)
    
def getClientData(client_id):
    
    keep_alive_session(client_id)
    
    return appQueue.getClientData(client_id)

def getClientSecret(client_id):
    return appQueue.getClientSecret(client_id)
    
def getFile(client_id,filename):

    if not appQueue.IsClientRegistered(client_id):
        return None
        
    filepath = f"{OUTPUT_DIR}/{client_id}/{filename}"
    
    privacy_secret = appQueue.getClientSecret(client_id)
    
    decrypted_file = read_file(f"{OUTPUT_DIR}/{client_id}/{filename}",
                               decrypt_func_cb=decrypt_func,
                               bytesIo = True,
                               retRawData = False,
                               clientSecret=privacy_secret)
                                   
    if isinstance(decrypted_file,BytesIO):
        return decrypted_file
    elif decrypted_file:##raw data as is on disk
        return filepath
    else:##not found
        return None
                         
# ========================
# App Worker Process/Thread Management
# ========================
    
def startAppWorkerInstance(muliproc_mode,pool_size=DEFAULT_POOL_SIZE):
    
    atexit.register(garbageCleanup)
    
    if muliproc_mode:
        return startAppWorkerProc(pool_size)
    else:
        return startAppWorkerThread(pool_size)

def startAppWorkerProc(pool_size=DEFAULT_POOL_SIZE):
    global app_worker_instance
    
    if app_worker_instance is None:
        app_worker_instance = checkAppWorkerProcIsRunning()
        
        if app_worker_instance: 
            app_worker_instance.terminate()
            app_worker_instance = None
    
    if app_worker_instance is None or not app_worker_instance.is_alive():
        #ctx = mp.get_context("spawn")
        app_worker_instance = mp.Process(target=app_worker_main,
                                        args=(int(pool_size),True),
                                        name=APP_WORKER_INSTANCE_NAME)
        app_worker_instance.start()
        
    return True
        
def startAppWorkerThread(pool_size=DEFAULT_POOL_SIZE):
    global app_worker_instance
    
    if app_worker_instance is None or not app_worker_instance.is_alive():

        app_worker_instance = threading.Thread(target=app_worker_main,
                                              args=(int(pool_size),False),
                                              name=APP_WORKER_INSTANCE_NAME)
        app_worker_instance.start()

    return True
    
def garbageCleanup():
    global thread_mode
    
    logger_debug(f"[atexit] 🧹 Garbage Collector Start")
    
    stopAppWorkerInstance(bool(not thread_mode))
    release_workers()
    
    logger_debug(f"[atexit] 🧹 Garbage Collector End")
    
def stopAppWorkerInstance(force = True):
    global app_worker_instance
    
    if(isinstance(app_worker_instance,threading.Thread)):
        stopAppWorkerThread(force)
        return
        
    if(isinstance(app_worker_instance,mp.Process) or force):
        stopAppWorkerProc(force)

    return True
    
def stopAppWorkerProc(force = True):
    global app_worker_instance
    
    logger_debug(f"[AppWorker] stopAppWorkerProc start with force:{force}")
    
    if app_worker_instance is None:
        app_worker_instance = checkAppWorkerProcIsRunning()
        
    if app_worker_instance:
        if app_worker_instance.is_alive():

            init = appQueue.IsQueueInitialized()
            
            if init == False:
                appQueue.init_queues(-1,True,None,logger_debug)

            send_msg_to_app_worker(-1,STOP_EVENT_TOKEN)
            
            app_worker_instance.join(timeout=DEFAULT_WORKER_JOIN_TIMEOUT)
        
            if app_worker_instance.is_alive():
                logger_debug("[AppWorker] Process did not stop, terminating...")
                app_worker_instance.terminate()
                app_worker_instance.join()

        app_worker_instance = None                
        logger_debug("[AppWorker] App Worker Process stopped")
    elif force == True or appQueue.AreQueuesShared():
        init = appQueue.IsQueueInitialized()
        
        res = False
        
        if init == False:
            res = appQueue.init_queues(-1,True,None,logger_debug)

        if res:
            send_msg_to_app_worker("-1",STOP_EVENT_TOKEN)
        else:
            logger_debug("[AppWorker] App Worker Process already stopped!!")
    
    logger_debug("[AppWorker] stopAppWorkerProc end")
    
def stopAppWorkerThread(force = True):
    global app_worker_instance
    
    logger_debug(f"[AppWorker] stopAppWorkerThread start with force:{force}")
    
    if app_worker_instance:
        if app_worker_instance.is_alive() or force:
            send_msg_to_app_worker(-1,STOP_EVENT_TOKEN)
            ##app_worker_instance.terminate()
        app_worker_instance.join()
        logger_debug("[AppWorker] App Worker Thread stopped")
        app_worker_instance = None
    elif force == True:
        send_msg_to_app_worker(-1,STOP_EVENT_TOKEN)
        logger_debug("[AppWorker] App Worker Thread stopped")
        app_worker_instance = None
    else:
        logger_debug("[AppWorker] App Worker Thread already stopped!!")
    
    logger_debug("[AppWorker] stopAppWorkerThread end")
    
def checkAppWorkerProcIsRunning():
    
    for child in mp.active_children():
        if child.name == APP_WORKER_INSTANCE_NAME:
            logger_debug(f"[AppWorker] Manager process is still running, {child.name} (PID={child.pid})")
            return child
    
    return None

def send_msg_to_app_worker(client_id,msg,event_type=WORKER_EVENT):
    logger_debug(f"[AppWorker] Sending message {msg} to App Worker instance, client_id:{client_id}")

    try:
        q = appQueue.getAppWorkerQueue()
        q.put({"client_id": client_id, "action": msg, "type": event_type})
        return True
        
    except Exception as e:
            logger_debug(f"[AppWorker] ❌ send_msg_to_app_worker Error: {type(e).__name__}:{e}")
            return False
    
def app_worker_main(num_workers, workerProcessMode=True):
    """
    Generic worker main function for processes or threads
    worker_type: "process" or "thread"
    """
    global client_last_seen, logger_debug, workers_instance, workers_task_queue, workers_state_queue, workers_process_mode, app_worker_instance

    logger = setup_logger()
    logger_debug = logger.debug

    workers_task_queue   = None
    workers_state_queue  = None
    client_last_seen     = {}
    workers_instance     = {}
    workers_process_mode = workerProcessMode
    worker_type          = (WORKER_TYPE_PROCESS if workers_process_mode else WORKER_TYPE_THREAD)
    queue_manager        = None
    worker_count         = 0

    pid = os.getpid()
    tid = threading.get_ident()
    
    logger_debug(f"[AppWorker] {worker_type} started with a pool size of {num_workers} (PID:{pid} TID:{tid})")
    
    if workers_process_mode:
        queue_manager = appQueue.create_queue_manager(logger_debug)

    start_workers_state_monitoring()
    
    create_pool_of_child(num_workers)

    worker_queue = appQueue.getAppWorkerQueue()
    
    try:
        while True:
            logger_debug(f"[AppWorker] {worker_type} waiting for message (PID:{pid} TID:{tid})...")
            payload = worker_queue.get()
            msg = payload["action"]
            type = payload["type"]
            cid = payload["client_id"]

            logger_debug(f"[AppWorker] {worker_type} got msg {msg} for {type} (PID:{pid} TID:{tid})")

            clean_pool()

            touch_client(cid)
            
            if(type == WORKER_EVENT):
                if msg == STOP_EVENT_TOKEN:
                    appQueue.send_to_all_clients(appQueue.SERVER_STOP_NTF_TOKEN)
                    break
                elif msg == REMOVE_CLIENT_EVENT_TOKEN:
                    release_client(cid)
                    continue
                elif msg == ABORT_OPERATION_EVENT_TOKEN:
                    shutdown_worker(cid)
                    continue
                elif msg == CLIENT_HEARTBEAT_EVENT_TOKEN:
                    send_termination_to_client(cid,appQueue.PROCESS_HEARTBEAT_END_TOKEN)
                    continue                     
                elif msg == SEE_CLIENT_EVENT_TOKEN:
                    continue

            while True:
                request = appQueue.getPendingRequest(cid)
                
                if request is None:
                    break

                if workers_task_queue:
                    if does_child_worker_operate_for_client(cid):
                        worker_func = request["data"]
                        logger_debug(f"[AppWorker] ⚠️ A request already ongoing for client_id={cid} discard worker_func={worker_func.__name__} (PID:{pid} TID:{tid})")
                        appQueue.send_request_result(cid, appQueue.PROCESS_REJECTED_BUSY_END_TOKEN)
                        break
                    workers_task_queue.put(request)
                else:
                    worker_count+=1
                    client_id = request["client_id"]
                    worker_func = request["data"]
                    extra_args = request["args"]

                    logger_debug(f"[AppWorker] {worker_type} starts Child as a {worker_type.capitalize()} for client_id={client_id} worker_func={worker_func.__name__} (PID:{pid} TID:{tid})")

                    w = create_worker(client_id,worker_func,extra_args,f"APP_WORKER_CHILD_INSTANCE_NAME_{worker_count}",worker_count)

                    logger_debug(f"[AppWorker] Child {worker_type} started with name: {w.name}")

    finally:
        logger_debug(f"[AppWorker] {worker_type} shutting down (PID:{pid} TID:{tid})...")
        release_workers()
        del worker_queue
        worker_queue = None
        app_worker_instance = None
        appQueue.shutdown_queue_manager()
        queue_manager = None

    logger_debug(f"[AppWorker] {worker_type} is done! (PID:{pid} TID:{tid})")
    
def create_worker(client_id=-1,worker_func=None, extra_args=None,wname=APP_WORKER_CHILD_INSTANCE_NAME,wnum=0):
    global workers_instance, workers_task_queue, workers_state_queue, workers_process_mode
    
    if workers_process_mode:
        w = mp.Process(target=child_worker_main, 
                       args=(workers_task_queue,workers_state_queue,workers_process_mode,client_id,worker_func, extra_args,wname,wnum),
                       name=wname,
                       daemon=True)
    else:
        w = threading.Thread(target=child_worker_main,
                             args=(workers_task_queue,workers_state_queue, workers_process_mode, client_id, worker_func, extra_args, wname,wnum),
                             name=wname,
                             daemon=True)

    w.start()
    workers_instance[wname] = {"obj": w, "state": WORKER_STATE_IDLE, "wnum":wnum}
    
    return w
    
def release_workers():
    stop_garbage_collector()
    shutdown_pool()
    stop_workers_state_monitoring()
    
# ========================
# Pool Management
# ========================
    
def create_pool_of_child(num_workers):
    global workers_instance, workers_task_queue, workers_process_mode
    
    if num_workers <= 0:
        logger_debug(f"[AppWorker] No pool created, child process will be created on demand for PID {os.getpid()}...")
        return None
    if num_workers > MAX_POOL_SIZE: 
        logger_debug(f"[AppWorker] pool size too big {num_workers} limited to {MAX_POOL_SIZE} for PID {os.getpid()}...")
        num_workers = MAX_POOL_SIZE

    workers_task_queue = mp.Queue() if workers_process_mode else Queue()
    workers_instance.clear()

    for i in range(num_workers):
        wname = f"{APP_WORKER_CHILD_INSTANCE_NAME}_{i}"
        w = create_worker(wname=wname,wnum=i)
        
    return True
    
def clean_pool():
    global workers_instance, logger_debug

    for wname in list(workers_instance.keys()):
        obj = workers_instance[wname]["obj"]
        if not obj.is_alive():
            logger_debug(f"[AppWorker] Cleaning zombie Worker {wname}")
            try:
                obj.join(timeout=DEFAULT_CHILD_WORKER_JOIN_TIMEOUT)
            except Exception as e:
                logger_debug(f"[AppWorker] ❌ join() failed for {wname}: {type(e).__name__}:{e}")
            finally:
                workers_instance.pop(wname, None)

def shutdown_pool():
    global workers_instance, workers_task_queue, workers_process_mode
    
    logger_debug("[AppWorker] ♻️ Stopping pool...")

    if workers_task_queue:
        #stop worker child
        for _ in workers_instance:
            workers_task_queue.put(None)

        for wname, winfo in list(workers_instance.items()):
            obj = winfo["obj"]
            try:
                obj.join(timeout=DEFAULT_CHILD_WORKER_JOIN_TIMEOUT)
            except Exception as e:
                logger_debug(f"[AppWorker] ❌ join() failed for {wname}: {type(e).__name__}:{e}")
                continue
                
        if workers_process_mode:
            workers_task_queue.close()
        else:
            workers_task_queue.task_done()
        workers_task_queue = None
    else:
        logger_debug("[AppWorker] ♻️ Pool already stopped!")

    # Kill remaining workers
    for wname, winfo in list(workers_instance.items()):
        obj = winfo["obj"]

        if obj.is_alive():
            if workers_process_mode:
                logger_debug(f"[AppWorker] Terminating Worker {wname}")
                obj.terminate()
            try:
                obj.join(timeout=DEFAULT_CHILD_WORKER_JOIN_TIMEOUT)
                if workers_process_mode:
                    obj.close()
            except Exception as e:
                logger_debug(f"[AppWorker] ❌ join() after terminate failed for {wname}: {type(e).__name__}:{e}")
                continue
        else:
            try:
                obj.join()
            except Exception as e:
                logger_debug(f"[AppWorker] ❌ join() final failed for {wname}: {type(e).__name__}:{e}")
                continue

        logger_debug(f"[AppWorker] Worker {wname} is now down")
        workers_instance.pop(wname, None)

    workers_instance.clear()

    logger_debug("[AppWorker] ♻️ Pool shutdown complete...")
    return True

# ========================
# Garbage Collector Management for Client Session
# ========================
        
def start_garbage_collector():
    global cleaner_worker_thread
    global stop_cleaner_worker_thread
    
    if cleaner_worker_thread is None:
        logger_debug(f"[CleanUpWorker] 🗑️ Starting Cleaner Worker Thread...")
        stop_cleaner_worker_thread = False
        cleaner_worker_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleaner_worker_thread.start()
        
def stop_garbage_collector():
    global cleaner_worker_thread
    global stop_cleaner_worker_thread
    global client_last_seen
    
    if cleaner_worker_thread is not None:
        logger_debug(f"[CleanUpWorker] 🗑️ Stopping carbage collector PID {os.getpid()}")
        stop_cleaner_worker_thread = True
        cleaner_worker_thread.join()
        cleaner_worker_thread = None
    else:
        logger_debug(f"[CleanUpWorker] 🏁 Carbage collector already stopped! PID {os.getpid()}")
    
    client_last_seen.clear()
    client_last_seen = {}
        
def cleanup_worker(infinite=True):
    global cleaner_worker_thread
    global client_last_seen
    global stop_cleaner_worker_thread
    """Background thread: remove inactive clients."""
    logger_debug(f"[CleanUpWorker] 🗑️ Worker Started.")
    counter = 0
    while stop_cleaner_worker_thread is False:
        if counter == 60:
            counter = 0
            logger_debug(f"[CleanUpWorker] 🗑️ Check clients sessions duration...")
            now = time.time()
            for client_id, last in list(client_last_seen.items()):
                if now - last > CLIENT_SESSION_TIMEOUT_SECONDS:
                    logger_debug(f"[CleanUpWorker] 🗑️ Releasing client={client_id}")
                    release_client(client_id)

            if not client_last_seen: 
                logger_debug(f"[CleanUpWorker] 🗑️ no client id, queue is empty.")
                break
        else:
            counter+=1
        if infinite:
            time.sleep(1)
        else:
            break

    cleaner_worker_thread = None        
    logger_debug(f"[CleanUpWorker] 🏁 Worker is now down!")

def keep_alive_session(client_id):
    logger_debug(f"[AppWorker] Client {client_id} has been seen now.") 
    send_msg_to_app_worker(client_id,SEE_CLIENT_EVENT_TOKEN)
    
def touch_client(client_id):
    """Update last activity timestamp."""
    global client_last_seen
    
    if client_id and client_id != -1:
        client_last_seen[client_id] = time.time()
    
        start_garbage_collector()    
    
def release_client(client_id):
    """Cleanup client resources."""
    global client_last_seen

    shutdown_worker(client_id)
    
    appQueue.RemoveClientFromQueue(client_id)
    
    if client_id in client_last_seen:
        del client_last_seen[client_id]
        
    logger_debug(f"[AppWorker] Client {client_id} has been released.")        
    
# ========================
# Worker Child Process
# ========================

def workers_state_monitoring_main():

    global client_active, workers_instance, workers_state_queue, workers_process_mode, worker_states, workers_monitor_stopped, logger_debug, threads_garbage_collector

    logger_debug("[WorkersStateMonitoring] 👀 Thread Start")
    
    worker_states             = {}
    client_active             = {}  # {client_id: worker_name}
    threads_garbage_collector = {}
    
    if not workers_state_queue:
        logger_debug("[WorkersStateMonitoring] ❌ no queue!")
        workers_monitor_stopped =True
        
    while not workers_monitor_stopped:
        try:
            state_update = workers_state_queue.get(timeout=DEFAULT_WORKERS_MONITOR_SLEEP_TIMEOUT)
            wname     = state_update["wname"]
            wnum      = state_update["wnum"]
            state     = state_update["state"]
            client_id = state_update["client_id"]
            timestamp = state_update.get("timestamp", time.time())

            if not wname and client_id in client_active:
                wname = client_active[client_id]
            elif wname not in workers_instance:
                if client_id in client_active:
                    del client_active[client_id]
                if state == WORKER_STATE_GARBAGED and wnum in threads_garbage_collector:
                    wname = threads_garbage_collector[wnum]["wname"]
                    logger_debug(f"[WorkersStateMonitoring] 👀 {wname} orphelan removed from garbage state={state} TID={wnum} (last client {client_id})")
                    del threads_garbage_collector[wnum]
                    
                continue
                    
            worker_states[wname] = {
                "state": state,
                "client_id": client_id,
                "timestamp": timestamp,
                "wnum": wnum
            }
            
            workers_instance[wname]["state"] = state

            logger_debug(f"[WorkersStateMonitoring] 👀 {wname} -> {state} (last client {client_id})")

            if state == WORKER_STATE_PROCESSING:
                client_active[client_id] = wname
            elif state == WORKER_STATE_IDLE:
                if client_id in client_active:
                    del client_active[client_id]
            elif state == WORKER_STATE_STOPPED:
                logger_debug(f"[WorkersStateMonitoring] 👀 Worker {wname} stopped, restarting...")
                if client_id in client_active:
                    del client_active[client_id]
                w = create_worker(wname=wname,wnum=wnum)
                logger_debug(f"[WorkersStateMonitoring] {w.name} restarted!")
            elif state == WORKER_STATE_ERROR:
                logger_debug(f"[WorkersStateMonitoring] 👀 Worker {wname} stopped brutaly! wating for STOPPED msg...")
                send_termination_to_client(client_id, appQueue.PROCESS_FAILURE_END_TOKEN)
                if client_id in client_active:
                    del client_active[client_id]
            elif state == WORKER_STATE_WANTED:
                if client_id in client_active:
                    wname = client_active[client_id]
                    wnum  = worker_states[wname]["wnum"]
                    terminate_child_worker(client_id,wname,wnum,appQueue.PROCESS_ABORTED_END_TOKEN)
                else:
                    logger_debug(f"[WorkersStateMonitoring] 👀 No worker to kill for client {client_id}")
            elif state == WORKER_STATE_DEADLOCK:
                terminate_child_worker(client_id,wname,wnum,appQueue.PROCESS_FAILURE_END_TOKEN)
            elif state == WORKER_STATE_SHUTDOWN:
                logger_debug(f"[WorkersStateMonitoring] 👀 Worker {wname} shutdown.")
                if wname in worker_states:
                    del worker_states[wname]
                if client_id in client_active:
                    del client_active[client_id]
                if not worker_states:
                    workers_monitor_stopped = True
                    logger_debug("[WorkersStateMonitoring] 👀 leaving right now as pool is empty!")
                    break
            if not workers_process_mode:
                workers_state_queue.task_done()
                    
        except Empty:
            now = time.time()
            
            for cid in client_active:
                w = client_active[cid]
                if now - worker_states[w]["timestamp"] > CHILD_WORKER_TIME_OUT_LIMIT_SECONDS:
                    logger_debug(f"[WorkersStateMonitoring] 🗑️ No response from {w} for client={cid} after {CHILD_WORKER_TIME_OUT_LIMIT_SECONDS}s, killing it right now!")
                    send_state_to_workers_monitor(workers_state_queue,
                                                  WORKER_STATE_DEADLOCK,
                                                  cid,
                                                  w,
                                                  worker_states[w]["wnum"])
            continue
        except Exception as e:
            logger_debug(f"[WorkersStateMonitoring] ❌ Unexpected error for worker {wname} in state={state} > {type(e).__name__}:{e}")
            workers_monitor_stopped = True
            break

    logger_debug("[WorkersStateMonitoring] 🏁 Thread End")

def terminate_child_worker(client_id,wname,wnum, token_to_send):
    global client_active, workers_instance, workers_state_queue, workers_process_mode, worker_states, logger_debug, threads_garbage_collector
    
    if wname in workers_instance:
        obj = workers_instance[wname]["obj"]
        if workers_process_mode:
            logger_debug(f"[WorkersStateMonitoring] 👀 Killing worker {wname} for client:{client_id}...")
            if obj.is_alive():
                obj.terminate()
            obj.join()
            obj.close()
        else:
            tid = obj.ident
            threads_garbage_collector[tid] = {"obj": obj,"wname":f"{wname}_zombie"}
            nb_threads_in_garbage = len(threads_garbage_collector)
            logger_debug(f"[WorkersStateMonitoring] 👀 Can't kill thread ID={tid}, let it to completion, create new thread for worker {wname}! nb th in garbage: {nb_threads_in_garbage}")
            if nb_threads_in_garbage > THRESHOLD_NB_THREADS_DEADLOCKED:
                logger_debug(f"[WorkersStateMonitoring] 🆘 Panic too many threads in deadlock state, stop process rith now!")
                send_msg_to_app_worker(-1,STOP_EVENT_TOKEN)
        
        del client_active[client_id]
        send_state_to_workers_monitor(workers_state_queue,WORKER_STATE_STOPPED,client_id,wname,wnum)
        send_termination_to_client(client_id, token_to_send)
    else:
        logger_debug(f"[WorkersStateMonitoring] ❌ No worker found to kill with name {wname} for client:{client_id} who looks to have left...")

def send_termination_to_client(client_id,msg):
    appQueue.send_request_result(client_id, msg)
    appQueue.end_all_streams(client_id)

def does_child_worker_operate_for_client(client_id):
    global client_active
    return (client_id in client_active)
    
def shutdown_worker(cid):
    global workers_state_queue
    send_state_to_workers_monitor(workers_state_queue,WORKER_STATE_WANTED,cid)

def send_state_to_workers_monitor(state_queue, state,cid,wname=None,wnum=-1):
    state_queue.put({"wname": wname,"state": state,"client_id": cid,"timestamp": time.time(), "wnum":wnum})
    
def start_workers_state_monitoring():
    global workers_monitor_stopped, workers_monitor_thread, logger_debug, workers_process_mode, workers_state_queue

    if workers_monitor_thread and workers_monitor_thread.is_alive():
        logger_debug("[WorkersStateMonitoring] 👀 Thread already running")
        return

    workers_state_queue     = mp.Queue() if workers_process_mode else Queue()
    workers_monitor_stopped = False
    workers_monitor_thread = threading.Thread(target=workers_state_monitoring_main,
                                              args=(),
                                              daemon=True,
                                              name="WorkersStateMonitoringThread"
    )
    workers_monitor_thread.start()
    logger_debug("[WorkersStateMonitoring] 👀 Thread launched")

def stop_workers_state_monitoring():
    global workers_monitor_stopped, workers_monitor_thread, logger_debug, workers_state_queue
    workers_monitor_stopped = True

    if workers_monitor_thread:
        workers_monitor_thread.join(timeout=DEFAULT_JOIN_TIMEOUT)
        logger_debug("[WorkersStateMonitoring] 🏁 Thread stopped")
        workers_monitor_thread = None 
    else:
        logger_debug(f"[WorkersStateMonitoring] 🏁 Workers Monitoring Thread already stopped! PID {os.getpid()}")
        
    if workers_state_queue: 
        if workers_process_mode:
            workers_state_queue.close()
        else:
            workers_state_queue.task_done()
        workers_state_queue = None
 
# ========================
# Worker Child Main
# ========================
def child_worker_main(task_queue,state_queue, workerProcessMode,client_id,worker_func, extra_args, wname, wnum):
    global logger_debug, threads_garbage_collector
    
    logger = setup_logger()
    logger_debug = logger.debug    
    
    pid = os.getpid()
    tid = threading.get_ident()
    wid = (pid if workerProcessMode else tid)
    
    last_client_id = client_id
    
    state_end = WORKER_STATE_STOPPED

    worker_type = (WORKER_TYPE_PROCESS if workerProcessMode else WORKER_TYPE_THREAD)

    logger_debug(f"[{wname}] 👷 {worker_type} worker started (PID:{pid} TID:{tid})")

    def check_threads_garbage():
        if not workerProcessMode and tid in threads_garbage_collector:
            wname = threads_garbage_collector[tid]["wname"]
            logger_debug(f"[{wname}] 👷 {worker_type} is in the garbage, no more task to do so exiting (PID:{pid} TID:{tid})")
            send_state_to_workers_monitor(state_queue,WORKER_STATE_GARBAGED,last_client_id,None,tid)
            logger_debug(f"[{wname}] 🏁 {worker_type} worker end  (PID:{pid} TID:{tid})")
            return True
        return False
        
    def send_state_to_monitoring(state,cid):
        send_state_to_workers_monitor(state_queue,state,cid,wname,wnum)
        
    def execute(client_id, worker_func, extra_args):
        logger_debug(f"[{wname}] 👷 {worker_type} execute for {client_id} ({worker_func.__name__}) (PID:{pid} TID:{tid})")

        ret = appQueue.hello_all_streams(client_id)

        if ret:
            result = worker_func(client_id, extra_args)

            ret = appQueue.send_request_result(client_id, result)
            if ret:
                ret = appQueue.end_all_streams(client_id)
            
        return ret

    try:
        if task_queue is not None:
            noTask = False
            while True:
                
                if not noTask:
                    logger_debug(f"[{wname}] 👷 {worker_type} waiting task (PID:{pid} TID:{tid})")
                    send_state_to_monitoring(WORKER_STATE_IDLE,last_client_id)
                
                try:
                    task = task_queue.get(timeout=DEFAULT_CHILD_WORKER_SLEEP_TIMEOUT)  # timeout en secondes
                    noTask = False
                except Empty:
                    noTask = True ## avoid to polute logs
                    if(check_threads_garbage()):
                        state_end=-1
                        break
                    continue 
                
                if task is None:
                    logger_debug(f"[{wname}] 👷 {worker_type} received None, no more task to do so exiting (PID:{pid} TID:{tid})")
                    state_end = WORKER_STATE_SHUTDOWN
                    break
                
                client_id = task["client_id"]
                worker_func = task["data"]
                extra_args = task["args"]
                
                last_client_id = client_id

                if workerProcessMode:
                    appQueue.init_queues(client_id,sharedQueue=True,startServerCb=None,prt_debug=logger_debug)
                    
                if appQueue.IsClientRegistered(client_id):
                    send_state_to_monitoring(WORKER_STATE_PROCESSING,last_client_id)
                    
                    ret = execute(client_id, worker_func, extra_args)
                    
                    if(check_threads_garbage()):
                        state_end=-1
                        break
                    
                    if ret == False:
                        logger_debug(f"[{wname}] 👷 execute cmd has failed for {worker_func.__name__} client_id:{client_id}!! (PID:{pid} TID:{tid})")
                        appQueue.send_request_result(client_id, appQueue.PROCESS_FAILURE_END_TOKEN)
                else:
                    logger_debug(f"[{wname}] 👷 execute cmd discarded for {worker_func.__name__} because client_id:{client_id} has gone!! (PID:{pid} TID:{tid})")

                if not workerProcessMode:
                    task_queue.task_done()
        else:
            send_state_to_monitoring(WORKER_STATE_PROCESSING,last_client_id)
            execute(client_id, worker_func, extra_args)
            state_end = WORKER_STATE_SHUTDOWN
            if(check_threads_garbage()):
                state_end=-1
            
    except Exception as e:
        send_state_to_monitoring(WORKER_STATE_ERROR,last_client_id)
        logger_debug(f"[{wname}] ❌ {worker_type} error: {type(e).__name__}:{e} (PID:{pid} TID:{tid})")
    finally:
        if state_end != -1:
            send_state_to_monitoring(state_end,last_client_id)
            logger_debug(f"[{wname}] 🏁 {worker_type} worker end  (PID:{pid} TID:{tid})")        
    