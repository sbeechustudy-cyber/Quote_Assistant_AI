import os
import time
import sys
from queue import Queue, Empty
import multiprocessing as mp
from multiprocessing.managers import BaseManager
from tools import setup_logger
from appSecurity import NO_SECRET

# ======================
# 🔹 Consts
# ======================
END_TOKEN = "__END__"
HELLO_TOKEN = "__HELLO__"
LISTENING_TOKEN = "__LISTENING__"
SERVER_STILL_WORKING_ON_TOKEN = "__SERVER_STILL_WORKING_ON__"

PROCESS_DONE_END_TOKEN = "__PROCESS_DONE_END__"
PROCESS_DONE_FETCH_DATA_END_TOKEN = "__PROCESS_DONE_FETCH_DATA_END__"
PROCESS_HEARTBEAT_END_TOKEN = "__PROCESS_HEARTBEAT_DONE_END__"
PROCESS_FAILURE_END_TOKEN = "__PROCESS_FAILED_END__"
PROCESS_ABORTED_END_TOKEN = "__PROCESS_ABORTED_END__"
PROCESS_REJECTED_BUSY_END_TOKEN = "__PROCESS_REJECTED_BUSY_END__"

SERVER_STOP_NTF_TOKEN = "__SERVER_STOP_NTF__"

DEFAULT_GET_TIMEOUT=3

QUEUE_MAIN  = "main"
QUEUE_DEBUG = "debug"
QUEUE_PL_EXTRACT = "priceListExtractStream"
QUEUE_PRICE_INDICATION = "priceIndicationStream"

# ========================
# Globals
# ========================

logger_debug = print

client_streams = {}        # {client_id: {"main": [], "debug": [], ...}}
json_result = {}
client_secret = {}
shared_client_stream_queues = {}
shared_json_result = {}
shared_client_secret = {}

pending_requests = {}
shared_pending_requests = {}

shared_worker_queue = None

queue_manager = None
queue_manager_address = ('127.0.0.1', 50000)
authkey = b'secret'

server_mode_flag = False

class QueueManager(BaseManager): pass

# ========================
# Data Access
# ========================
def getClientSecret(client_id):
    global client_secret
    if queue_manager is not None:
        proxy_obj =  queue_manager.get_client_secret(client_id)
        return proxy_obj._getvalue()
    else:
        return client_secret.get(client_id, NO_SECRET)
        
def setClientSecret(client_id,secret) -> bool:
    global client_secret
    if queue_manager is not None:
        proxy_obj= queue_manager.set_client_secret(client_id,secret)
        return bool(proxy_obj._getvalue())
    else:
        client_secret[client_id]=secret
        return True
        
def getClientData(client_id):
    global json_result
    if queue_manager is not None:
        proxy_obj =  queue_manager.get_json_result(client_id)
        return proxy_obj._getvalue()
    else:
        return json_result.get(client_id, [])
      
def setClientData(client_id, data):
    global json_result
    if queue_manager is not None:
        proxy_obj= queue_manager.set_json_result(client_id,data)
        return bool(proxy_obj._getvalue())
    else:
        json_result[client_id] = data
        
def appendRequest(client_id, worker_func,args):
    global pending_requests
    
    payload = {
        "client_id": client_id,
        "data": worker_func,
        "args": args
    }    
    
    if queue_manager is not None:
        queue_manager.append_request(client_id,payload)
        return True
    else:
        if client_id not in pending_requests:
            pending_requests[client_id]=[]
            
        pending_requests[client_id].append(payload)
        return True

def getPendingRequest(client_id):
    global pending_requests, queue_manager
    if queue_manager is not None:
        proxy_obj = queue_manager.get_pending_request(client_id)
        return  proxy_obj._getvalue()
    else:
        if client_id not in pending_requests or len(pending_requests[client_id]) == 0:
            return None
        else:
            return pending_requests[client_id].pop(0)
    
def getAppWorkerQueue():
    
    if queue_manager is not None:
        q = queue_manager.get_app_worker_queue()
        return q
    
    return get_app_worker_queue()
        
# ========================
# Messaging
# ========================
def send_to_all_clients(msg):
    global queue_manager, server_mode_flag
    if queue_manager:
        proxy_obj = queue_manager.putInQueueForAll(QUEUE_DEBUG,msg)
        return bool(proxy_obj._getvalue())        
    else:
        for client_id, queues in client_streams.items():
            queues[QUEUE_DEBUG].put(msg)
            
    return True
            
def send_request_result(client_id, end_proc_token):
    return send_message_to_stream(client_id,QUEUE_DEBUG,end_proc_token)

def send_message_to_stream(client_id, stream_name, msg):
    """Send a message to a client stream_name."""
    global queue_manager, server_mode_flag
    
    if queue_manager:
        proxy_obj=queue_manager.putInQueue(client_id, stream_name,msg)
        return bool(proxy_obj._getvalue())  
    else:    
        if client_id not in client_streams:
            logger_debug(f"[AppQueue] ❌ send_message_to_stream: Warning Client {client_id} not found in client_streams")
            return False
        
        #logger_debug(f"[AppQueue] send_message_to_stream SSE for client={client_id} stream_name={stream_name}")
        
        client_streams[client_id][stream_name].put(msg)#,block=False)
    
    return True

def send_message_to_all_streams(client_id, msg):
    """Send a message to a client stream."""
    if queue_manager:
        proxy_obj=queue_manager.putInAllQueues(client_id,msg)
        return bool(proxy_obj._getvalue())  
    else:        
        if client_id not in client_streams:
            logger_debug(f"[AppQueue] ❌ send_message_to_all_streams: Warning Client {client_id} not found in client_streams")
            return False
        
        try:
            for stream_name in list(client_streams[client_id].keys()):
                client_streams[client_id][stream_name].put(msg)
            return True
        except Exception as e:
            logger_debug(f"[AppQueue] ❌ send_message_to_all_streams for msg:{msg} Error={type(e).__name__}:{e}")
            return False
        
        return True
    
def end_all_streams(client_id):
    """Send END_TOKEN to all streams in order to inform client that the server will not send any longer data"""
    return send_message_to_all_streams(client_id,END_TOKEN)
        
def hello_all_streams(client_id):
    """Send HELLO_TOKEN to all streams in order to inform client that the server will start to send data soon"""
    return send_message_to_all_streams(client_id,HELLO_TOKEN)
        
# ======================
# 🔹 SSE event_stream
# ======================
def event_stream(client_id, stream, timeoutVal = DEFAULT_GET_TIMEOUT):
    global logger_debug
    """Generator for SSE (server → client)."""
    """Flux SSE stops after receiving __END__."""
    logger_debug(f"[AppQueue] event_stream SSE Listening for client={client_id} stream={stream}")
    
    q = client_streams[client_id][stream]
    
    yield f"data: {LISTENING_TOKEN}\n\n"
    sys.stdout.flush()
    while True:
        try:
            msg = q.get(timeout=timeoutVal)
            #msg = q.get()
            for line in msg.splitlines():
                yield f"data: {line}\n\n"
            sys.stdout.flush()
            
            if msg == END_TOKEN:
                logger_debug(f"[AppQueue] Closing SSE client={client_id} stream={stream}")
                break
        except Empty:
            yield f"data: {SERVER_STILL_WORKING_ON_TOKEN}\n\n"
            sys.stdout.flush()
            logger_debug(f"[AppQueue] Sending SERVER_STILL_WORKING_ON_TOKEN for SSE client={client_id} stream={stream}")
            break
        except ConnectionResetError as e:
            logger_debug(f"[AppQueue] ❌ event_stream client_id={client_id} stream={stream} ❌ Connection closed by client side: {e}")
            break
        except ConnectionError as e:
            logger_debug(f"[AppQueue] ❌ event_stream client_id={client_id} stream={stream} ❌ Connection issue: {e}")
            break
        except OSError as e:
            logger_debug(f"[AppQueue] ❌ event_stream client_id={client_id} stream={stream} ❌ OSError: {e}")                
            break
        except (ConnectionRefusedError, EOFError):
            logger_debug(f"[AppQueue] ❌ IsClientRegistered, Manager unavailable (probably shutting down)")
            break          
        except Exception as e:
            logger_debug(f"[AppQueue] ❌ event_stream client_id={client_id} stream={stream} ❌ error: {type(e).__name__}:{e}")
            break

    logger_debug(f"[AppQueue] event_stream client_id={client_id} stream={stream} closed")
        
    return 
# ========================
# Shared Queue (multiprocessing.BaseManager)
# ========================

def IsClientRegistered(client_id) -> bool:
    global queue_manager, client_streams, logger_debug
    
    try:
        if queue_manager is not None:
            proxy_obj=queue_manager.isClientRegistered(client_id)
            return bool(proxy_obj._getvalue())             
        else:
            return client_id in client_streams
    except (ConnectionRefusedError, EOFError):
        logger_debug(f"[AppQueue] ❌ IsClientRegistered, Manager unavailable (probably shutting down)")
        return False
    except Exception as e:
        logger_debug(f"[AppQueue] ❌ IsClientRegistered error: {type(e).__name__}:{e}")
        return False
        
def IsQueueInitialized():
    global client_streams
    try:
        return bool(client_streams)
    except NameError:
        return False
    except Exception as e:
        logger_debug(f"[IsQueueInitialized] ❌ Unexpected error: {type(e).__name__}:{e}")
        return False

def AreQueuesShared():
    global queue_manager
    return (queue_manager is not None)
    
def RemoveClientFromQueue(client_id):
    """Cleanup client resources."""
    global shared_client_stream_queues, client_streams, queue_manager,shared_pending_requests,pending_requests,json_result,shared_json_result, logger_debug,client_secret, shared_client_secret

    if queue_manager:
        queue_manager.remove_clientid_from_queue(client_id)
        
    if client_id in client_streams:
        del client_streams[client_id]
    if client_id in shared_client_stream_queues:
        del shared_client_stream_queues[client_id]
        
    if client_id in json_result:
        del json_result[client_id]
    if client_id in shared_json_result:
        del shared_json_result[client_id]
        
    if client_id in shared_client_secret:
        del shared_client_secret[client_id]
    if client_id in client_secret:
        del client_secret[client_id]
        
    if client_id in pending_requests:
        del pending_requests[client_id]
    if client_id in shared_pending_requests:
        del shared_pending_requests[client_id]        
        
    logger_debug(f"[AppQueue] Released client {client_id}")  
    
def init_queues(client_id,sharedQueue, startServerCb,prt_debug=print,newClient=False):
    global queue_manager, client_streams, logger_debug
    
    logger_debug = prt_debug

    if sharedQueue:
        if queue_manager is None: 
            queue_manager = init_queue_manager(startServerCb)
            if queue_manager is None: 
                logger_debug("[AppQueue] Unable to get queue manager instance!")
                return False
        if newClient and client_id not in client_streams:
            client_streams[client_id] = {
                    QUEUE_MAIN: queue_manager.getQueue(client_id,QUEUE_MAIN),
                    QUEUE_DEBUG: queue_manager.getQueue(client_id,QUEUE_DEBUG),
                    QUEUE_PL_EXTRACT: queue_manager.getQueue(client_id,QUEUE_PL_EXTRACT),
                    QUEUE_PRICE_INDICATION: queue_manager.getQueue(client_id,QUEUE_PRICE_INDICATION)
                }
    else:
        if newClient and client_id not in client_streams:
             client_streams[client_id] = {
                    QUEUE_MAIN: Queue(),
                    QUEUE_DEBUG: Queue(),
                    QUEUE_PL_EXTRACT: Queue(),
                    QUEUE_PRICE_INDICATION: Queue()
        }
        
    
    return True

def init_queue_manager(startServerCb):
    global queue_manager, client_streams
    if queue_manager is None:
        queue_manager = get_queue_manager(startServerCb)
        client_streams = {}
        return queue_manager
        
def get_queue_manager(startServerCb, retries=10, delay=0.5):
    global logger_debug
    
    try:
        return connect_to_queue_manager()
    except ConnectionRefusedError:
        logger_debug("[AppQueue] ❌ initial connect failed with ConnectionRefusedError")
    except KeyboardInterrupt:
        logger_debug("[AppQueue] ❌ interrupted by user (Ctrl+C)")
        raise        
    except Exception as e:
        logger_debug(f"[AppQueue] ❌ initial connect failed with {type(e).__name__}: {e}")

    if startServerCb is not None:
        startServerCb()
    else:
        logger_debug("[AppQueue] get_queue_manager: no callback for starting server provided...")

    for _ in range(retries):
        try:
            return connect_to_queue_manager()
        except ConnectionRefusedError:
            time.sleep(delay)            
        except KeyboardInterrupt:
            logger_debug("[AppQueue] ❌ interrupted by user (Ctrl+C)")
            raise            
        except Exception as e:
            logger_debug(f"[AppQueue] ❌ retry connect failed with {type(e).__name__}: {e}")
            time.sleep(delay)

    return None
    
def connect_to_queue_manager():
    QueueManager.register('getQueue')
    QueueManager.register('putInQueue')
    QueueManager.register('putInAllQueues')
    QueueManager.register('putInQueueForAll')
    QueueManager.register('remove_clientid_from_queue')
    QueueManager.register('get_app_worker_queue')
    QueueManager.register('isClientRegistered')
    QueueManager.register("set_json_result")
    QueueManager.register("get_json_result")
    QueueManager.register("get_client_secret")
    QueueManager.register("set_client_secret")
    QueueManager.register("get_pending_request")
    QueueManager.register("append_request")
    QueueManager.register("set_logger")
    
    m = QueueManager(address=queue_manager_address, authkey=authkey)
    m.connect()
    return m
    
def create_queue_manager(prt_debug=print):
    global shared_client_stream_queues,shared_client_secret, shared_json_result, logger_debug, shared_pending_requests, queue_manager, shared_worker_queue, server_mode_flag
    
    shared_json_result = {}
    shared_client_secret = {}
    shared_client_stream_queues = {}
    shared_pending_requests = {}
    shared_worker_queue = None
    logger_debug = prt_debug
    
    QueueManager.register('getQueue',callable=getQueue)
    QueueManager.register('putInQueue',callable=putInQueue)
    QueueManager.register('putInAllQueues',callable=putInAllQueues)
    QueueManager.register('putInQueueForAll',callable=putInQueueForAll)
    QueueManager.register('remove_clientid_from_queue',callable=remove_clientid_from_queue)
    QueueManager.register('get_app_worker_queue',callable=get_app_worker_queue)
    QueueManager.register('isClientRegistered',callable=isClientRegistered)
    QueueManager.register("set_json_result", callable=set_json_result)
    QueueManager.register("get_json_result", callable=get_json_result)
    QueueManager.register("get_client_secret", callable=get_client_secret)
    QueueManager.register("set_client_secret", callable=set_client_secret)
    QueueManager.register("get_pending_request", callable=get_pending_request)
    QueueManager.register("append_request", callable=append_request)
    QueueManager.register("set_logger", callable=set_logger)
    
    queue_manager = QueueManager(address=queue_manager_address, authkey=authkey)
    queue_manager.start()
    queue_manager.set_logger(prt_debug)
    server_mode_flag = True
    
    logger_debug(f"[AppQueue] Server started on {queue_manager_address}")
    
    return queue_manager

def shutdown_queue_manager() -> bool:
    global queue_manager, server_mode_flag
    
    if server_mode_flag and queue_manager:
        queue_manager.shutdown()
        queue_manager = None
        return True
        
    return False
    
def isClientRegistered(client_id) -> bool:
    global shared_client_stream_queues
    return bool(client_id in shared_client_stream_queues)
    
def get_app_worker_queue():
    global shared_worker_queue

    if shared_worker_queue is None:
        shared_worker_queue = Queue()

    return shared_worker_queue
    
def getQueue(client_id, stream_name):
    global shared_client_stream_queues
        
    if client_id not in shared_client_stream_queues:
        shared_client_stream_queues[client_id] = {
            QUEUE_MAIN: Queue(),
            QUEUE_DEBUG: Queue(),
            QUEUE_PL_EXTRACT: Queue(),
            QUEUE_PRICE_INDICATION: Queue()
        }    
    return shared_client_stream_queues[client_id][stream_name]    

def putInQueue(client_id, stream_name,msg) -> bool:
    global shared_client_stream_queues
        
    if shared_client_stream_queues and client_id in shared_client_stream_queues:
        shared_client_stream_queues[client_id][stream_name].put(msg)
        return True

    return False    

def putInAllQueues(client_id, msg) -> bool:
    global shared_client_stream_queues, logger_debug
    
    if client_id not in shared_client_stream_queues:
        logger_debug(f"[AppQueue] putInAllQueues: Warning Client {client_id} not found in client_streams")
        return False
    
    try:
        for stream_name in list(shared_client_stream_queues[client_id].keys()):
            shared_client_stream_queues[client_id][stream_name].put(msg)
        return True
    except Exception as e:
        logger_debug(f"[AppQueue] ❌ putInAllQueues for msg:{msg} Error={type(e).__name__}:{e}")
        return False
    
    return True
    
def putInQueueForAll(stream_name,msg) -> bool:
    global shared_client_stream_queues
        
    if shared_client_stream_queues:
        for client_id in shared_client_stream_queues:
            shared_client_stream_queues[client_id][stream_name].put(msg)
        return True

    return False 
    
def remove_clientid_from_queue(client_id):
    global shared_client_stream_queues, shared_json_result, shared_pending_requests, shared_client_secret
    
    if client_id in shared_client_stream_queues:
        del shared_client_stream_queues[client_id]
        
    if client_id in shared_json_result:
        del shared_json_result[client_id]
        
    if client_id in shared_pending_requests:
        del shared_pending_requests[client_id]
        
    if client_id in shared_client_secret:
        del shared_client_secret[client_id]

def set_logger(prt_debug):
    global logger_debug
    logger_debug = prt_debug
    return True
    
def set_json_result(client_id, value) -> bool:
    global shared_json_result
    shared_json_result[client_id] = value
    return True

def get_json_result(client_id):
    global shared_json_result
    ##return shared_json_result.get(client_id, [])
    if client_id in shared_json_result:
        return shared_json_result[client_id]
    else:
        return None
    
def get_client_secret(client_id):
    global shared_client_secret
    if client_id in shared_client_secret:
        return shared_client_secret[client_id]
    else:
        return NO_SECRET

def set_client_secret(client_id,secret):
    global shared_client_secret
    shared_client_secret[client_id]=secret
    return True
    
def get_pending_request(client_id):
    global shared_pending_requests
    
    if client_id in shared_pending_requests and len(shared_pending_requests[client_id]) > 0:
        return shared_pending_requests[client_id].pop(0)
    else:
        return None
def append_request(client_id, request):
    global shared_pending_requests

    if client_id not in shared_pending_requests:
        shared_pending_requests[client_id] = []
        
    shared_pending_requests[client_id].append(request)
      