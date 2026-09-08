# context_manager.py
import threading

NO_SECRET       = None

clients_context = {}

_thread_local = threading.local()

def set_current_client(client_id):
    _thread_local.id = client_id

def get_current_client():
    return getattr(_thread_local, "id", None)
    
def init_client_context(client_id):
    clients_context[client_id] = {
        "questionnaire_structure": {},
        "prt_main": None,
        "prt_debug": None,
        "prt_priceListExtract": None,
        "prt_priceIndication": None,
        "client_secret": NO_SECRET
    }

def set_client_context(client_id,client_secret, mainStream, debugStream, priceListExtractStream, priceIndicationStream, default_questionnaire, callbacks = None):
    if client_id not in clients_context:
        init_client_context(client_id)

    set_current_client(client_id)
    
    clients_context[client_id].update({
        "questionnaire_structure": default_questionnaire,
        "client_secret": client_secret if client_secret != '' and isinstance(client_secret,str) else NO_SECRET,
        "prt_main": mainStream,
        "prt_debug": debugStream,
        "prt_priceListExtract": priceListExtractStream,
        "prt_priceIndication": priceIndicationStream,
        "prt_main_buffer": []
    })
    
    if callbacks:
        for cb in callbacks:
            cb(client_id)

def get_context(client_id):
    return clients_context.get(client_id, None)

def cleanup_client(client_id):
    clients_context.pop(client_id, None)
