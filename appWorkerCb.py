import appQueue
import product_configurator

def worker_process_ai_analysis_func(client_id, args):
    user_input, no_AI_flag,privacy_secret = args
    
    # Wrappers for flushing prints to streams
    def print_main(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_MAIN, msg)
    def print_debug(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_DEBUG, msg)
    def print_priceListExtract(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_PL_EXTRACT, msg)
    def print_priceIndication(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_PRICE_INDICATION, msg)
    
    res = product_configurator.process_ai_analysis(client_id,privacy_secret, user_input, no_AI_flag, print_main, print_debug, print_priceListExtract, print_priceIndication)
    appQueue.setClientData(client_id,res)
    
    return (appQueue.PROCESS_DONE_FETCH_DATA_END_TOKEN if (res is not None) else appQueue.PROCESS_FAILURE_END_TOKEN)
    
def worker_process_reset_func(client_id, args):
    no_AI_flag,privacy_secret = args
    
    # Wrappers for flushing prints to streams
    def print_main(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_MAIN, msg)
    def print_debug(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_DEBUG, msg)
    def print_priceListExtract(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_PL_EXTRACT, msg)
    def print_priceIndication(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_PRICE_INDICATION, msg)
    
    res = product_configurator.process_reset(client_id,privacy_secret,no_AI_flag, print_main, print_debug, print_priceListExtract, print_priceIndication)
    appQueue.setClientData(client_id,res)

    return (appQueue.PROCESS_DONE_FETCH_DATA_END_TOKEN if (res is not None) else appQueue.PROCESS_FAILURE_END_TOKEN)
    
def worker_process_update_func(client_id, args):
    data,privacy_secret = args
    # Wrappers for flushing prints to streams
    def print_main(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_MAIN, msg)
    def print_debug(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_DEBUG, msg)
    def print_priceListExtract(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_PL_EXTRACT, msg)
    def print_priceIndication(msg): appQueue.send_message_to_stream(client_id, appQueue.QUEUE_PRICE_INDICATION, msg)

    res = product_configurator.process_update(client_id,privacy_secret, data, print_main, print_debug, print_priceListExtract, print_priceIndication)
    
    return (appQueue.PROCESS_DONE_END_TOKEN if res is True else appQueue.PROCESS_FAILURE_END_TOKEN)
   