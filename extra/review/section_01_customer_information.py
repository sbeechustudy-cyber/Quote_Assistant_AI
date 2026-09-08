import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utility import print_main,print_main_tag, print_debug, print_priceIndication, print_priceListExtract
from tools import unix_path, setup_logger, fuzzy_match, get_integer, fmt_money, truncate_text, is_valid_email, is_valid_phone
import db_sales_force as db_sf
import db_sales_force_conversion as db_sf_conv
import html_renderer as hr
from extra.consolidate.consolidate_section_01_customer_information import check_customer_and_company_information

logger = setup_logger()

MODULE_DIR = os.path.dirname(__file__)

# Callbacks for customer_information


def customer_information_section_pre_check_values_cb(questionnaire,item,key_name,value):
    """Auto-generated callback: TODO implement logic for customer_information_section_pre_check_values_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'customer_information_section_pre_check_values_cb' not implemented for key '{key_name}'")
    return questionnaire, output_string


def customer_information_section_consolidate_values_cb(questionnaire,item,key_name,value):
    """Auto-generated callback: TODO implement logic for customer_information_section_consolidate_values_cb"""
    output_string = None
    
    questionnaire = check_customer_and_company_information(questionnaire)

    return questionnaire, output_string


def customer_name_check_value_cb(parent_item,item,key_name,ai_customer_name):
    """Auto-generated callback: TODO implement logic for customer_name_check_value_cb"""
    output_string  = None
    customer_name  = None
    
    sf_contact_obj = db_sf.db_sf_find_contact(ai_customer_name) 
    
    nb_contacts = len(sf_contact_obj) if sf_contact_obj else 0
    
    if nb_contacts == 1:
        customer_name = sf_contact_obj[0]['Name']
        link_contact = db_sf.db_get_contact_hyperlink(sf_contact_obj[0]['sf_id'],customer_name,noIcon=True)
        
        if customer_name != ai_customer_name:
            output_string = f"🎯 Customer name '{ai_customer_name}' found in SF database as '{link_contact}'"
        else:
            output_string = f"🎯 Customer name '{ai_customer_name}' confirmed and found {link_contact} in SF database!"
            
    elif nb_contacts > 1:
        customer_name  = []
        output_string  = []
        output_string.append(f"⚠️ Customer name '{ai_customer_name}' found in SF database for several matches:")
        for c in sf_contact_obj:
            link_contact = db_sf.db_get_contact_hyperlink(c['sf_id'],c['Name'],noIcon=True)
            output_string.append(f"- Customer name '{link_contact}'")
            customer_name.append(c['Name'])        
    else:
        output_string = f"🔍❌ Customer name '{ai_customer_name}' not found in SalesForce!"
    
    return customer_name, output_string


def company_name_check_value_cb(parent_item,item,key_name,ai_company_name):
    """Auto-generated callback: TODO implement logic for company_name_check_value_cb"""
    output_string = None
    company_name  = None
        
    accounts = db_sf.db_sf_get_account_names(sf_id=True)
    
    company_name_found  = fuzzy_match(accounts,ai_company_name, all_best=True,value_key='Name',extra_key='sf_id',extra_key2=None)

    nb_company_names = len(company_name_found) if company_name_found else 0
    
    if nb_company_names == 1:
        c = company_name_found[0]
        company_name = c[0]
        link_account = db_sf.db_get_account_hyperlink(c[2],c[0],noIcon=True)

        if company_name != ai_company_name:
            output_string = f"🎯 Company name '{ai_company_name}' found in SF database as '{link_account}'"
        else:
            output_string = f"🎯 Company name '{ai_company_name}' confirmed and found {link_account} in SF database!"
    elif nb_company_names > 1:
        company_name  = []
        output_string = []
        output_string.append(f"⚠️ Company name '{ai_company_name}' found in SF database for several matches:")
        for c in company_name_found:
            link_account = db_sf.db_get_account_hyperlink(c[2],c[0],noIcon=True)
            output_string.append(f"- company name '{link_account}'")
            company_name.append(c[0])
    else:
        output_string = f"🔍❌ Company name '{ai_company_name}' not found in SalesForce!"
        
    return company_name, output_string

def company_brand_name_check_value_cb(parent_item,item,key_name,ai_company_brand_name):
    """Auto-generated callback: TODO implement logic for company_brand_name_check_value_cb"""
    output_string = None
    company_brand = None
        
    accounts_brand = db_sf.db_sf_get_account_brands(sf_id=True)
    
    company_brand_found = fuzzy_match(accounts_brand,ai_company_brand_name, all_best=True,value_key='Brand__c',extra_key='sf_id',extra_key2='Name')
        
    nb_company_brand_names = len(company_brand_found) if company_brand_found else 0

    if nb_company_brand_names == 1:
        c = company_brand_found[0]
        company_brand = c[0]        
        if company_brand != ai_company_brand_name:
            output_string = f"🎯 Company Brand name '<strong>{ai_company_brand_name}</strong>' found in SF database as '<strong>{company_brand}</strong>'"
        else:
            output_string = f"🎯 Company Brand name '<strong>{ai_company_brand_name}</strong>' confirmed and found in SF database!"
    elif nb_company_brand_names > 1:
        company_brand = []
        output_string = []
        output_string.append(f"⚠️ Company Brand name '<strong>{ai_company_brand_name}</strong>' found in SF database for several matches:")
        for c in company_brand_found:
            link_account = db_sf.db_get_account_hyperlink(c[2],c[3],noIcon=True)
            output_string.append(f"- company Brand name '<strong>{c[0]}</strong>' and company '{link_account}'")
            company_brand.append((c[0],c[3]))
    else:
        output_string = f"🔍❌ Company Brand name '<strong>{ai_company_brand_name}</strong>' not found in SF!"
        
    return company_brand, output_string

def company_location_check_value_cb(parent_item,item,key_name,ai_company_country):
    """Auto-generated callback: TODO implement logic for company_location_check_value_cb"""
    output_string = None
        
    company_location          = fuzzy_match(db_sf.db_sf_get_account_distinct_countries(),ai_company_country)
    company_location_iso_code = fuzzy_match(db_sf.db_sf_get_account_distinct_countries_isocode(),ai_company_country,value_key='BillingCountryCode',extra_key='BillingCountry',extra_key2=None)
    
    ## check company location 
    if company_location and company_location != ai_company_country:
        output_string = f"🎯 Company country '{ai_company_country}' found in SF database as '{company_location}'"
    elif company_location:
        output_string = f"🎯 Company country '{ai_company_country}' confirmed and found in SF database!"
    elif company_location is None and company_location_iso_code is None:
        output_string = f"🔍❌ Company country '{ai_company_country}' not found in SF!"   
    else:
        nb_iso_codes = len(company_location_iso_code) if company_location_iso_code else 0

        if nb_iso_codes == 1:
            c = company_location_iso_code[0]
            iso_code = c[0]
            country  = c[2]
            if company_location is None:
                company_location = country
                output_string = f"🎯 Company country '<strong>{ai_company_country}</strong>' confirmed and found in SF database thanks to ISO code '<strong>{iso_code}</strong>' so country is '<strong>{country}</strong>'!"
            elif company_location == country:
                output_string = f"🎯 Company country ISO code '<strong>{ai_company_country}</strong>' confirmed and found in SF database, country is '<strong>{country}</strong>'!"
            else:
                output_string = f"⚠️ Company country ISO code '<strong>{ai_company_country}</strong>' confirmed and found in SF database but divergence between iso code '{country}' and previously found '{company_location}'!"
        elif nb_iso_codes > 1:
            output_string    = []
            company_location = []
            output_string.append(f"⚠️ Company country ISO code '<strong>{ai_company_country}</strong>' found in SF database for several matches:")
            for c in company_location_iso_code:
                output_string.append(f"- company country ISO code '<strong>{c[0]}</strong>' country: {c[2]}")
                company_location.append((c[0],c[2]))
        
    return company_location, output_string

def customer_job_title_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for customer_job_title_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'customer_job_title_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string


def customer_department_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for customer_department_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'customer_department_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string


def customer_email_check_value_cb(parent_item,item,key_name,ai_customer_email):
    """Auto-generated callback: TODO implement logic for customer_email_check_value_cb"""
    output_string = None
    customer_email = None
    
    validity = is_valid_email(ai_customer_email)
    
    if validity:
        customer_email = ai_customer_email
        output_string = f"✅ Customer email '{ai_customer_email}' is well formated!" 
    else:
        output_string = f"❌ Customer email '{ai_customer_email}' is malformated!"           
    
    return customer_email, output_string


def customer_phone_number_check_value_cb(parent_item,item,key_name,ai_customer_phone_number):
    """Auto-generated callback: TODO implement logic for customer_phone_number_check_value_cb"""
    output_string = None
    customer_phone_number = None
    
    validity = is_valid_phone(ai_customer_phone_number)
    
    if validity:
        customer_phone_number = ai_customer_phone_number
        output_string = f"✅ Customer phone number '{ai_customer_phone_number}' is well formated!" 
    else:
        output_string = f"❌ Customer phone number '{ai_customer_phone_number}' is malformated!"  
        
    return customer_phone_number, output_string


def customer_mobile_phone_number_check_value_cb(parent_item,item,key_name,ai_customer_mobile_phone_number):
    """Auto-generated callback: TODO implement logic for customer_mobile_phone_number_check_value_cb"""
    output_string = None
    customer_mobile_phone_number = None
    
    validity = is_valid_phone(ai_customer_mobile_phone_number)
    
    if validity:
        customer_mobile_phone_number = ai_customer_mobile_phone_number
        output_string = f"✅ Customer mobile phone number '{ai_customer_mobile_phone_number}' is well formated!" 
    else:
        output_string = f"❌ Customer mobile phone number '{ai_customer_mobile_phone_number}' is malformated!"  
        
    return customer_mobile_phone_number, output_string


def customer_role_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for customer_role_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'customer_role_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string


def company_type_check_value_cb(parent_item,item,key_name,ai_company_type):
    """Auto-generated callback: TODO implement logic for company_type_check_value_cb"""
    output_string = None
    company_type  = None
    
    def check_company_type(ai_company_type,sf_account_obj=None):
    
        company_type = fuzzy_match(db_sf_conv.account_type_trans_tool_2_sf,ai_company_type)
        
        if company_type:
            sf_type = db_sf_conv.account_type_trans_tool_2_sf[company_type]
            if sf_account_obj and sf_account_obj['EB_Account_Type__c'] not in sf_type:
                company_type = db_sf_conv.transform_sf_account_type(sf_account_obj)
        elif sf_account_obj:
            company_type= db_sf_conv.transform_sf_account_type(sf_account_obj)
        else:
            company_type= None
            
        return company_type
        
    company_type = check_company_type(ai_company_type)
    
    ## check company type 
    if company_type is None: 
        output_string = f"🔍❌ Company type '<strong>{ai_company_type}</strong>' not found in SF!"
    elif company_type != ai_company_type:
        output_string = f"🎯 Company type '<strong>{ai_company_type}</strong>' found in SF database as '<strong>{company_type}</strong>'"
    else:
        output_string = f"🎯 Company type '<strong>{ai_company_type}</strong>' confirmed and found in SF database!"
   
    return company_type, output_string


def company_customer_comments_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for company_customer_comments_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'company_customer_comments_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string
