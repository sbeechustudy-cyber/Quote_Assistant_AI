import os
import sys
from datetime import datetime, timedelta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utility import print_main,print_main_tag, print_debug, print_priceIndication, print_priceListExtract
from tools import unix_path, setup_logger, normalize_date_iso, days_diff_from_now, end_of_month_plus_n_days, shift_date_by_n_days
import db_sales_force as db_sf
import db_sales_force_conversion as db_sf_conv
import html_renderer as hr
from extra.consolidate.consolidate_section_11_quote_preparation import check_quote_preparation_information
from product_questionnaire import is_item_has_no_information
from product_questionnaire_db_connector import update_item_value

logger = setup_logger()

MODULE_DIR = os.path.dirname(__file__)

# Callbacks for quote_preparation


def quote_preparation_section_pre_check_values_cb(questionnaire,item,key_name,value):
    """Auto-generated callback: TODO implement logic for quote_preparation_section_pre_check_values_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'quote_preparation_section_pre_check_values_cb' not implemented for key '{key_name}'")
    return questionnaire, output_string


def quote_preparation_section_consolidate_values_cb(questionnaire,item,key_name,value):
    """Auto-generated callback: TODO implement logic for quote_preparation_section_consolidate_values_cb"""
    output_string = None
    
    questionnaire = check_quote_preparation_information(questionnaire)
    
    return questionnaire, output_string


def quote_general_comment_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for quote_general_comment_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'quote_general_comment_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string


def quote_deadline_check_value_cb(parent_item,item,key_name,ai_deadline_date):
    """Auto-generated callback: TODO implement logic for quote_deadline_check_value_cb"""
    output_string = None
    deadline_date = None
    now           = shift_date_by_n_days(offset_in_days=7,str_format=False)
    now_str       = normalize_date_iso(now)

    if is_item_has_no_information(item):
        deadline_date  = now_str
        output_string = f"⚠️ no deadline date identified within the report then use date of today + 7 days '{deadline_date}'!"
    else:
        res = normalize_date_iso(ai_deadline_date)
        
        if res == None:
            deadline_date  = now_str
            output_string = f"❌ identified deadline date '{ai_deadline_date}' within the report is incorrect then use date of today + 7 days '{deadline_date}'!"
        else:
            diff = days_diff_from_now(res,now)
            if diff > 0:
                deadline_date  = res
                output_string = f"✅ identified deadline date '{ai_deadline_date}' within the report is in the later than usual delay of 7 days '{deadline_date}'!"
            elif diff <= 0 and diff >=-7 :
                deadline_date  = res
                output_string = f"✅ identified deadline date '{deadline_date}' within the report is ok."
            else:
                deadline_date  = now_str
                output_string = f"✅ identified deadline date '{ai_deadline_date}' within the report is in the past, then use day of today + 7 days'{deadline_date}'"
                
    return deadline_date, output_string


def quote_request_date_check_value_cb(parent_item,item,key_name,ai_request_date):
    """Auto-generated callback: TODO implement logic for quote_request_date_check_value_cb"""
    output_string = None
    request_date  = None
    now           = normalize_date_iso()
    now_str       = normalize_date_iso(now)
            
    if is_item_has_no_information(item):
        request_date  = now_str
        output_string = f"⚠️ no request date identified within the report then use date of today '{request_date}'!"
    else:
        res = normalize_date_iso(ai_request_date)
        
        if res == None:
            request_date  = now_str
            output_string = f"❌ identified request date '{ai_request_date}' within the report is incorrect then use date of today '{request_date}'!"
        else:
            diff = days_diff_from_now(res,now)
            if diff > 0:
                request_date  = now_str
                output_string = f"❌ identified request date '{ai_request_date}' within the report is in the futur then use date of today '{request_date}'!"
            elif diff == 0:
                request_date  = now_str
                output_string = f"✅ identified request date '{request_date}' within the report is today."
            elif diff > -10:
                request_date  = res
                output_string = f"✅ identified request date '{request_date}' within the report is prior of today."
            else:
                request_date  = now_str
                output_string = f"✅ identified request date '{ai_request_date}' within the report is too old, then use day of today '{request_date}'"
                
    return request_date, output_string


def quote_close_date_check_value_cb(parent_item,item,key_name,ai_close_date):
    """Auto-generated callback: TODO implement logic for quote_close_date_check_value_cb"""
    output_string    = None
    output_string    = None
    close_date       = None
    now              = datetime.utcnow()
    now_plus_90d_str = end_of_month_plus_n_days(now,default_offset=90)
            
    if is_item_has_no_information(item):
        close_date  = now_plus_90d_str
        output_string = f"⚠️ no close date identified within the report then use date of today + ~90 days '{close_date}'!"
    else:
        res = normalize_date_iso(ai_close_date)
        
        if res == None:
            close_date  = now_plus_90d_str
            output_string = f"❌ identified close date '{ai_close_date}' within the report is incorrect then use date of today + ~90days '{close_date}'!"
        else:
            diff = days_diff_from_now(res,now)
            if diff >= 30:
                close_date  = res
                output_string = f"✅ identified close date '{ai_close_date}' within the report is ok'!"
            else:
                close_date  = end_of_month_plus_n_days(now,default_offset=30)
                output_string = f"❌ identified close date '{ai_close_date}' within the report is too short, then use day of today + ~30 days '{close_date}'"
                
    return close_date, output_string


def quote_recipient_check_value_cb(parent_item,item,key_name,ai_recipient_name):
    """Auto-generated callback: TODO implement logic for quote_recipient_check_value_cb"""
    output_string  = None
    recipient_name  = None
    
    sf_contact_obj = db_sf.db_sf_find_contact(ai_recipient_name) 
    
    nb_contacts = len(sf_contact_obj) if sf_contact_obj else 0
    
    if nb_contacts == 1:
        recipient_name = sf_contact_obj[0]['Name']
        link_contact = db_sf.db_get_contact_hyperlink(sf_contact_obj[0]['sf_id'],recipient_name,noIcon=True)
        
        update_item_value(item,recipient_name,sf_contact_obj[0]['sf_id'])
        
        if recipient_name != ai_recipient_name:
            output_string = f"🎯 Recipient name '{ai_recipient_name}' found in SF database as '{link_contact}'"
        else:
            output_string = f"🎯 Recipient name '{ai_recipient_name}' confirmed and found {link_contact} in SF database!"
            
    elif nb_contacts > 1:
        recipient_name  = []
        output_string  = []
        output_string.append(f"⚠️ Recipient name '{ai_recipient_name}' found in SF database for several matches:")
        for c in sf_contact_obj:
            link_contact = db_sf.db_get_contact_hyperlink(c['sf_id'],c['Name'],noIcon=True)
            output_string.append(f"- Recipient name '{link_contact}'")
            recipient_name.append(c['Name'])        
    else:
        output_string = f"🔍❌ Recipient name '{ai_recipient_name}' not found in SalesForce!"
    
    return recipient_name, output_string
