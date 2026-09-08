from flask import Flask, render_template,send_from_directory, request, Response, jsonify, send_file, abort
import requests
from waitress import serve
import json
import argparse
import os
import sys
import signal
import threading
import time
from io import BytesIO
#from werkzeug import wrap_file
import appWorker
import appWorkerCb
import db_jira
import db_sales_force
from appSecurity import set_env_security_variable, NO_SECRET
from tools import setup_logger


# ========================
# Consts
# ========================

APP_SECRET_KEY = "super-secret^$^$^fsdfsdbhjhdqs"
SHUTDOWN_SECRET = os.environ.get("SHUTDOWN_SECRET", APP_SECRET_KEY)

DEFAULT_MAINTENANCE_DURATION = 3600
DEFAULT_POOL_SIZE            = 10
DEFAULT_LISTENER_TIMEOUT     = 2
DEFAULT_HTTP_SERVER_PORT     = 5000

ALLOWED_PATHS_FOR_MAINTENANCE = ["/", "/maintenance_status"]

# ========================
# Global variables
# ========================

app = Flask(__name__)
app.logger = setup_logger()

multiProcessingMode =  True
listenerTimeOut = DEFAULT_LISTENER_TIMEOUT
maintenanceMode = False
maintenanceDurationInSec = DEFAULT_MAINTENANCE_DURATION

# ========================
# HTTP Management
# ========================
@app.before_request
def before_request():
    app.logger.debug(f"[App] Request path: {request.path} args: {request.args}")
    
    if maintenanceMode and request.path not in ALLOWED_PATHS_FOR_MAINTENANCE:
        abort(503)
        
@app.route("/")
def index():
    global maintenanceMode, maintenanceDurationInSec
    
    if maintenanceMode:
        app.logger.debug(f"[App] Loading maintenance page with a planned restart in {maintenanceDurationInSec}s")
        return render_template("maintenance.html",initial_time=maintenanceDurationInSec), 503, {"Retry-After": f'{maintenanceDurationInSec}'}
    else:
        return render_template("index.html")
        
@app.route("/maintenance_status")
def maintenance_status():
    global maintenanceMode, maintenanceDurationInSec
    
    return jsonify({"maintenance": maintenanceMode, "duration":maintenanceDurationInSec})
    
@app.route("/help")
def help_page():
    client_id = request.args.get('client_id', 'unknown')
    return render_template("help.html", client_id=client_id)

@app.route("/sf_opportunity/", defaults={"id": None})
@app.route("/salesforce/Opportunity/<id>")
@app.route("/sf_opportunity/<id>")
def sf_opportunity_page(id):
    if id is None or id == '':
        id = "006Sd000006n3z1IAA"
        id = '0069K00000N0M89QAF'
        
    opportunity = db_sales_force.get_sf_opportunity(id)
    
    if opportunity:
        return render_template("sf_opportunity.html", opportunity=opportunity)
    else:
        return jsonify({"error": "Failed to get data"}), 400
        
@app.route("/sf_opportunity/details/", defaults={"id": None})
@app.route("/salesforce/Opportunity/details/<id>")
@app.route("/sf_opportunity/details/<id>")
def sf_opportunity_details_page(id):
    if id is None or id == '':
        id = "006Sd000006n3z1IAA"
        id = '0069K00000N0M89QAF'
        
    opportunity = db_sales_force.get_sf_opportunity(id)
    
    if opportunity:
        return render_template("sf_opportunity_details.html", opportunity=opportunity)
    else:
        return jsonify({"error": "Failed to get data"}), 400    
    
@app.route("/sf_opportunity/products/", defaults={"id": None})
@app.route("/salesforce/Opportunity/products/<id>")
@app.route("/sf_opportunity/products/<id>")
def sf_opportunity_products_page(id):
    if id is None or id == '':
        #id = "006Sd000006n3z1IAA"
        id = "0069K00000N0M89QAF"
        
    opportunity = db_sales_force.get_sf_opportunity(id)
    
    if opportunity:
        return render_template("sf_opportunity_products.html", opportunity=opportunity)
    else:
        return jsonify({"error": "Failed to get data"}), 400    

@app.route("/sf_opportunity/revenue/", defaults={"id": None})
@app.route("/salesforce/Opportunity/revenue/<id>")
@app.route("/sf_opportunity/revenue/<id>")
def sf_opportunity_revenue_page(id):
    if id is None or id == '':
        id = "006Sd000006n3z1IAA"
        
    opportunity = db_sales_force.get_sf_opportunity(id)
    
    if opportunity:
        return render_template("sf_opportunity_revenue.html", opportunity=opportunity)
    else:
        return jsonify({"error": "Failed to get data"}), 400   
    
@app.route("/jira_issue/", defaults={"key": None})
@app.route("/jira/issue/<key>")
@app.route("/jira_issue/<key>")
def jira_issue_page(key):
    if key is None or key == '':
        key = "EBACQ-42853"
        
    issue, resp = db_jira.get_jira_issue(key)
    
    if resp.ok:
        return render_template("jira_issue.html", issue=issue)
    else:
        return f"Error: {resp.status_code}", resp.status_code
        
@app.route("/hello")
def hello():
    return "Hello from IIS!"

@app.route("/register_client")
def register_client():
    global multiProcessingMode
    
    client_id = appWorker.new_client(multiProcessingMode, app.logger.debug)
    
    app.logger.debug(f"[App] register_client new client_id={client_id} PID {os.getpid()} from addr {request.remote_addr}")

    if client_id == -1:
        return jsonify({"error": "Failed to register client"}), 400  # Bad Request

    return jsonify({"client_id": client_id}), 200
    
@app.route("/change_privacy", methods=["POST"])
def change_privacy():
    data           = request.get_json()
    privacy_state  = data.get("privacy_state", False)
    privacy_secret = data.get("privacy_secret", NO_SECRET)
    client_id      = data.get("client_id")

    if appWorker.set_client_context(client_id,multiProcessingMode) == False:
        app.logger.error(f"[App] ❌ client_id {client_id} not found in client_queues PID {os.getpid()}")
        return "Client not registered", 410

    if privacy_state:
        if not privacy_secret or privacy_secret == NO_SECRET:
            privacy_secret = appWorker.getClientSecret(client_id)
    else:
        privacy_secret = NO_SECRET

    return jsonify({
        "success": True,
        "clientId": client_id,
        "privacy_state": privacy_state,
        "privacy_secret": privacy_secret
    })
    
@app.route("/get_json_data")
def get_json_data():
    client_id = request.args.get("client_id")
    
    app.logger.debug(f"[App] get_json_data client_id={client_id} PID {os.getpid()}")
    
    if appWorker.set_client_context(client_id,multiProcessingMode) == False:
        app.logger.warning(f"[App] 🚫 Attempt to get json after context expired: client_id={client_id}")
        return "Resource no longer available", 410
        
    data = appWorker.getClientData(client_id)
    
    if data is None:
        return jsonify({"error": "Failed to get data"}), 400  # Bad Request

    return jsonify(data), 200

@app.route("/download/<client_id>/<filename>")
def download_file(client_id, filename):
    
    app.logger.debug(f"[App] download client_id={client_id} filename={filename} PID {os.getpid()}")
    
    try:
        res = appWorker.set_client_context(client_id,multiProcessingMode)

        if appWorker.set_client_context(client_id,multiProcessingMode) == False:
            app.logger.warning(f"[App] 🚫 Attempt to download after context expired: client_id={client_id}, filename={filename}")
            return "Resource no longer available", 410
            
        data = appWorker.getFile(client_id,filename)
        
        if isinstance(data,BytesIO):
            return send_file(data,
                             as_attachment=True,
                             download_name=filename)
        elif data:
            return send_file(data,
                             as_attachment=True,
                             download_name=filename)        
        else:
            return "Not Found", 404
        
    except FileNotFoundError as e:
        app.logger.error(f"[App] ⚠️ Download failed, missing file {filename}: {e}")
        return "File not found", 404

    except Exception as e:
        app.logger.error(f"[App] ❌ Unexpected error while downloading {filename}")
        return "Internal Server Error", 500        
        
@app.route("/submit_report_to_server", methods=["POST"])
def submit_report_to_server():
    data           = request.get_json()
    client_id      = data.get("client_id")
    user_input     = data.get("input", "")
    no_AI_flag     = data.get("noAIFlag", False)
    privacy_secret = data.get("privacy_secret", NO_SECRET)

    return handle_client_request(
        client_id,
        appWorkerCb.worker_process_ai_analysis_func,
        extra_args=(user_input, no_AI_flag,privacy_secret)
    )
    
@app.route("/reset_data_to_ai_results", methods=["POST"])
def reset_data_to_ai_results():
    data           = request.get_json()
    client_id      = data.get("client_id")
    no_AI_flag     = data.get("noAIFlag", False)
    privacy_secret = data.get("privacy_secret", NO_SECRET)

    return handle_client_request(
        client_id,
        appWorkerCb.worker_process_reset_func,
        extra_args=(no_AI_flag,privacy_secret),
    )

@app.route("/submit_update_to_server", methods=["POST"])
def submit_update_to_server():
    data         = request.get_json()
    client_id    = data.get("client_id")
    updated_data = data.get("updated_data", [])
    privacy_secret = data.get("privacy_secret", NO_SECRET)
    
    if not updated_data:
        app.logger.debug(f"[App] ❌ no user data client_id={client_id} PID {os.getpid()} from addr {request.remote_addr}")
        return jsonify({"error": "No data provided"}), 400  # Bad Request
        
    return handle_client_request(
        client_id,
        appWorkerCb.worker_process_update_func,
        extra_args=(updated_data,privacy_secret))

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json()
    client_id = data.get("client_id")
    
    res = appWorker.register_client_hearbeat(client_id)
    
    return (("Succefull response", 200) if res is True else ("Request error response", 400))
    
@app.route("/abort_request", methods=["POST"])
def abort_request():
    data = request.get_json()
    client_id = data.get("client_id")
    
    res = appWorker.abort_execution(client_id)
    
    return (("Succefull response", 200) if res is True else ("Request error response", 400))
    
@app.route("/disconnect", methods=["POST", "GET"])
def disconnect():
    client_id = request.args.get("client_id")
    app.logger.debug(f"[App] disconnect called with client_id={client_id} PID {os.getpid()}")

    appWorker.remove_client(client_id)

    return "bye", 200
    
@app.route("/stream/<stream_type>")
def stream_data(stream_type):
    global listenerTimeOut, multiProcessingMode
    
    pid = os.getpid()
    client_id = request.args.get("client_id")
    app.logger.debug(f"[App] stream_data called with client_id={client_id} PID {pid} stream_type= {stream_type}")
    
    if appWorker.set_client_context(client_id,multiProcessingMode) == False:
        app.logger.error(f"[App] ❌ client_id {client_id} not found in client_queues PID {pid} stream_type= {stream_type}")
        return "Client not registered", 400

    app.logger.debug(f"[App] stream_data waiting for msg with client_id={client_id} PID {pid} stream_type= {stream_type}")
    
    resp = Response(appWorker.request_execution_listener(client_id, stream_type,listenerTimeOut), mimetype="text/event-stream")

    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    
    return resp
    
@app.route('/shutdown', methods=['POST'])
def shutdown():
    pid = os.getpid()
    app.logger.debug(f"[Flask] shutdown called with PID {pid}")
    
    if request.remote_addr != "127.0.0.1":
        app.logger.warning(f"[App] Shutdown blocked from {request.remote_addr}")
        return jsonify({"error": "Forbidden"}), 403

    secret = request.headers.get("X-Secret-Key")
    if secret != SHUTDOWN_SECRET:
        app.logger.warning("[App] Unauthorized shutdown attempt")
        return jsonify({"error": "Unauthorized"}), 403
        
    def _delayed_shutdown():
        try:
            #shutdown_func = request.environ.get('werkzeug.server.shutdown')
            #if shutdown_func is None:
            #    raise RuntimeError("Not running with the Werkzeug server")
            #shutdown_func()
            time.sleep(0.5)  # attendre que la réponse parte
            app.logger.debug(f"[Flask] Server shutting down...")
            os.kill(pid, signal.SIGINT)
        except KeyboardInterrupt:
            app.logger.debug(f"[Flask] Server down!")
            sys.exit(0)
        except Exception as e:
            app.logger.error(f"[Flask] Shutdown ❌ error: exception '{type(e).__name__}' raised with '{e}'")

    t = threading.Thread(target=_delayed_shutdown, daemon=True)
    
    if t:
        t.start()
        return 'Server shutting down...', 200
    else:
        app.logger.error(f"[Flask] shutdown ❌ error, no thread!")
        return jsonify({"error": "Unable to start thread"}), 500        

@app.errorhandler(404)
def handle_404(e):
    app.logger.error(f"[Flask] ❌ 404 Not Found: {request.path}")
    return "Page not found", 404

@app.errorhandler(405)
def handle_405(e):
    app.logger.error(f"[Flask] ❌ 405 Method Not Allowed: The method is not allowed for the requested URL {request.path} from addr {request.remote_addr}")
    return "Method Not Allowed", 405
    
@app.errorhandler(503)
def service_unavailable(e):
    app.logger.error(f"[Flask] ❌ 503 Service is temporarily unavailable due to maintenance")
    return "Service Unavailable: The server is temporarily unable to service your request due to maintenance downtime or capacity problems. Please try again later.", 503
    
@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"[Flask] ❌ Exception: {e}", exc_info=True)
    return "Internal Server Error", 500
    
def handle_client_request(client_id, worker_func, extra_args=None):
    global multiProcessingMode
    
    pid = os.getpid()
    
    app.logger.debug(f"[App] handle_client_request worker_func={worker_func.__name__} called with client_id={client_id} PID {pid}")
    
    if not appWorker.set_client_context(client_id,multiProcessingMode):
        app.logger.error(f"[App] ❌ client_id {client_id} not found in client_queues PID {pid}")
        return jsonify({"error": "Invalid client ID"}), 400
    
    try:
        res = appWorker.execute_request(client_id, worker_func, extra_args)
        return (("Succefull response", 200) if res is True else ("Request error response", 400))

    except Exception as e:
        app.logger.error(f"[App] ❌ handle_client_request worker_func={worker_func.__name__} client_id={client_id} ❌ error: exception '{type(e).__name__}' raised with '{e}'")
        return jsonify({"error": str(e)}), 500
    
# ========================
# Main
# ========================
    
def handle_sigint(signum, frame):
    app.logger.debug(f"[Flask] 🛑 Server down! got CTRL+C or SIGINT signal")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)
            
def myMain():
    global multiProcessingMode,listenerTimeOut, maintenanceMode, maintenanceDurationInSec, DEFAULT_MAINTENANCE_DURATION, DEFAULT_POOL_SIZE, DEFAULT_LISTENER_TIMEOUT, DEFAULT_HTTP_SERVER_PORT
    
    maintenanceDurationHelpStr = f"Indicate server maintenance duration in seconde (by default it is {DEFAULT_MAINTENANCE_DURATION}s)"
    timeOutSSEHelpStr          = f"Change timeout in seconds for SSE stream listener for unblocking (by default it is {DEFAULT_LISTENER_TIMEOUT})"
    poolsizeHelpStr            = f"Define the pool size of the child process of the worker server, put 0 for disabling pool (by default it is {DEFAULT_POOL_SIZE})"
    portHelpStr                = f"Indicate server port to use (by default it is {DEFAULT_HTTP_SERVER_PORT})"
    
    parser = argparse.ArgumentParser(description="EB product configuration script.")
    parser.add_argument('--no-multiprocessing', action='store_true',default=False, help='Use mapped memory for multi-process support. IIS server optimisation using several process by requests. (Enabled by default)')
    parser.add_argument('--erase', action='store_true', help='Delete output folder content with previous sessions data')
    parser.add_argument('--run', action='store_true',default=False, help='Run server (by default it is False, server is not started)')
    parser.add_argument('--port',type=int, default=DEFAULT_HTTP_SERVER_PORT, help=portHelpStr)
    parser.add_argument('--localhostonly',action='store_true', default=False, help='Limit server to local host only (by default it is any adress => 0.0.0.0)')
    parser.add_argument('--debug',action='store_true', default=False, help='Enable debug mode of Flask server.')
    parser.add_argument('--flask',action='store_true', default=False, help='Enable Flask server (by default it is waitress server.')
    parser.add_argument('--workerservermode',action='store_true', default=False, help='Start only the worker process in standalone for multiple process mode only')
    parser.add_argument('--stopworkerserver',action='store_true', default=False, help='Stop the worker process only')
    parser.add_argument('--stop',action='store_true', default=False, help='Stop the worker process and HTTP server')
    parser.add_argument('--poolsize',type=int, default=DEFAULT_POOL_SIZE, help=poolsizeHelpStr)
    parser.add_argument('--timeOutSSE', default=DEFAULT_LISTENER_TIMEOUT, help=timeOutSSEHelpStr)
    parser.add_argument('--maintenance',action='store_true', default=False, help='Put HTTP server in maintenance mode, worker process is not started for maintenance purpose)')
    parser.add_argument('--maintenanceDuration',type=int, default=DEFAULT_MAINTENANCE_DURATION, help=maintenanceDurationHelpStr)
    parser.add_argument('--pwd', type=str, default="", help="Define the password to use for decrypting credentials present into .env file")
    
    args = parser.parse_args()

    set_env_security_variable(args.pwd)
    
    maintenanceMode = args.maintenance
    
    try:
        timeout = int(args.timeOutSSE)
        maintenanceDurationInSec = int(args.maintenanceDuration)
        if timeout > 0:
            listenerTimeOut = timeout
            app.logger.debug(f"[App] Timeout of {listenerTimeOut}s set for SSE listner")
        else:
            listenerTimeOut = None
            app.logger.debug(f"[App] No timeout for SSE listner")
    except Exception as e:
        app.logger.debug(f"[App] ❌ Bad value for option timeOutSSE or maintenanceDuration, an integer value is expected Error: {type(e).__name__}: {e}")
        return
        
    if args.stopworkerserver or args.stop:
        app.logger.debug("[App] Stopping Worker Server")
        appWorker.stopAppWorker(app.logger.debug,True)
        app.logger.debug("[App] Worker Server Down!")
        if args.stop:
            app.logger.debug(f"[App] Stopping HTTP Server on PID {os.getpid()}")
            try:
                url = f"http://127.0.0.1:{args.port}/shutdown"
                headers = {"X-Secret-Key": APP_SECRET_KEY}
                response = requests.post(url, headers=headers)                
            except requests.exceptions.RequestException:
                pass
            except KeyboardInterrupt:
                app.logger.debug("[App] 🛑 KeyboardInterrupt, manual stop...")                
            except Exception as e:
                app.logger.debug(f"[App] ❌ Error: {type(e).__name__}: {e}")            
            finally:
                app.logger.debug("[App] Stop command complete!")
        else:
            app.logger.debug("[App] 🏁 Worker Server is now down!")
        return 

    workerStartPassed = True
    
    if not args.maintenance:

        multiProcessingMode = not args.no_multiprocessing
        
        mode = ("in standalone mode in its own process" if multiProcessingMode else "in hosted mode within its own thread")
        
        app.logger.debug(f"[App] Sarting Worker Server {mode}")
        
        workerStartPassed = appWorker.initAppWorker(multiProcessingMode,args.poolsize,args.erase,app.logger.debug)
        
        if not workerStartPassed:
            app.logger.debug(f"[App] ❌ Unable to start Worker Server {mode} check logs!")
        
    else:
        app.logger.debug(f"[App] Sarting in maintenance mode")

    if (args.run and args.workerservermode == False and workerStartPassed) or  args.maintenance:
            
        try:
            if args.localhostonly:
                host='127.0.0.1'
            else:
                host="0.0.0.0"
            
            port = int(args.port)
            
            if args.flask:
                app.logger.debug(f"[App] Sarting Flask HTTP Server host={host} port={port} ")
                
                app.run(host=host,debug=args.debug,threaded=True, port=port)
            else:
                
                app.logger.debug(f"[App] Sarting Waitress HTTP Server host={host} port={port}")
                
                serve(app, host=host, port=args.port, threads=100)
                    
        except KeyboardInterrupt:
            app.logger.debug("[App] 🛑 KeyboardInterrupt, manual stop...")
            raise
        except Exception as e:
            app.logger.debug(f"[App] ❌ Error: {type(e).__name__}: {e}")
        finally:
            if not args.maintenance:
                app.logger.debug("[App] Stopping Worker Server")
                appWorker.stopAppWorker(app.logger.debug)
            app.logger.debug("[App] 🏁 Run command complete")
    
if __name__ == "__main__":
    app.logger.debug(f"[App] START PID {os.getpid()}")
    myMain()
    app.logger.debug(f"[App] END PID {os.getpid()}")


    
