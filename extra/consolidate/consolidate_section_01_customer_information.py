from product_questionnaire import item_get_value_checked, get_item_by_key_name, item_get_value, ITEM_NO_INFO,  is_item_has_no_information
from product_questionnaire_db_connector import update_item_value, append_sf_instance, map_sf_object_to_questionnaire, set_account_invoice_entities
import db_sales_force as db_sf
import db_sales_force_conversion as db_sf_conv
from utility import print_main,print_main_tag, print_debug, print_priceIndication, print_priceListExtract
import html_renderer as hr

# ========================
# Consts
# ========================

# ========================
# Global variables
# ========================

# ========================
# Contact & Company Verification
# ========================
    
def search_customer_in_sf_db(ai_customer_email,ai_customer_name,ai_company_name,ai_company_country):
    
    sf_contact_obj = None
    nb_contacts    = 0
    
    if '@' not in ai_customer_email and is_item_has_no_information(ai_customer_name):
        print_main_tag(f"🚫 Invalid customer's email! and no customer name, then unable to find a contact name in SF!")
        return None, -1
        
    ## Search by customer email
    if '@' in ai_customer_email:
        sf_contact_obj = db_sf.db_sf_find_contact_from_email(ai_customer_email)
        if sf_contact_obj:
            print_main_tag(f"🎯 Found customer in SF from email <a href='mailto:{ai_customer_email}'>{ai_customer_email}</a>, now using as it a trusted source...")
            return sf_contact_obj, 1
    else:
        print_main_tag(f"⚠️ No valid customer's email <strong>'{ai_customer_email}'</strong>, checking with the name '{ai_customer_name}'...")
    
    if is_item_has_no_information(ai_customer_name):
        print_main_tag(f"⚠️ No customer from email <strong>'{ai_customer_email}'</strong> found in SF and no customer name provided!")
        return None, 0
    else:
        print_main_tag(f"⚠️ No customer from email <strong>'{ai_customer_email}'</strong> found in SF, now checking with the name '{ai_customer_name}'...")        
        
    ## Search by customer name 
    
    msg = None
    
    ## Search contact by name, company name & location
    if ai_company_name and ai_company_country:
        sf_contact_obj = db_sf.db_sf_find_contact(ai_customer_name,account_name=ai_company_name, contact_country=None, account_country=ai_company_country,brand_name=ai_company_name) 
        if not sf_contact_obj:
            print_main_tag(f"🔍❌ No contact found in SF from contact name <strong>'{ai_customer_name}'</strong> with company or brand name'<strong>{ai_company_name}</strong>' located in country '<strong>{ai_company_country}</strong>'!")
        else:
            msg = f"🎯 Found customer in SF from contact name <strong>'{ai_customer_name}'</strong> with company or brand name'<strong>{ai_company_name}</strong>' located in country '<strong>{ai_company_country}</strong>'!"
            
    ## Search contact by name, company name without location
    if ai_company_name and not sf_contact_obj:
        sf_contact_obj = db_sf.db_sf_find_contact(ai_customer_name,account_name=ai_company_name, contact_country=None, account_country=None, brand_name=ai_company_name) 
        if not sf_contact_obj:
            print_main_tag(f"🔍❌ No contact found in SF from contact name <strong>'{ai_customer_name}'</strong> with company or brand name '<strong>{ai_company_name}</strong>' whatever the country!")
        else:
            msg = f"🎯 Found customer in SF from contact name <strong>'{ai_customer_name}'</strong> with company or brand name '<strong>{ai_company_name}</strong>' whatever the country!"

    ## Search contact by name, company location
    if ai_company_country and not sf_contact_obj:
        sf_contact_obj = db_sf.db_sf_find_contact(ai_customer_name,account_name=None, contact_country=None, account_country=ai_company_country) 
        if not sf_contact_obj:
            print_main_tag(f"🔍❌ No contact found in SF from contact name <strong>'{ai_customer_name}'</strong> located in country '<strong>{ai_company_country}</strong>' whatever the company!")
        else:
            msg = f"🎯 Customer found in SF from contact name <strong>'{ai_customer_name}'</strong> located in country '<strong>{ai_company_country}</strong>' whatever the company!"

    ## Search contact by name only
    if not sf_contact_obj:
        sf_contact_obj = db_sf.db_sf_find_contact(ai_customer_name)                     
        msg = f"🎯 Found customer in SF from contact name <strong>'{ai_customer_name}'</strong> without company name <strong>'{ai_company_name}'</strong>!"
    
    nb_contacts = len(sf_contact_obj) if sf_contact_obj else 0
    
    if nb_contacts == 1:
        print_main_tag(msg)
    elif nb_contacts > 1:
        print_main_tag(f"⚠️ Found several customers in SF with contact name <strong>'{ai_customer_name}'</strong> with company or brand name <strong>'{ai_company_name}'</strong>:")
        
        account_ids = {c["AccountId"] for c in sf_contact_obj if c.get("AccountId")}
        
        rows = db_sf.db_sf_get_accounts_by_ids(account_ids)
        
        account_map = {row["sf_id"]: row for row in rows}
        
        for c in sf_contact_obj:
            sf_account_obj = account_map.get(c["AccountId"], None)
            
            account_name    = sf_account_obj["Name"] if sf_account_obj else "N/A"
            account_country = sf_account_obj["BillingCountry"] if sf_account_obj else "N/A"
            
            print_main_tag(f"\t\t- <strong>{c['Name']}</strong> from company '<strong>{account_name}</strong>' based in '{account_country}'")
    else:
        print_main_tag(f"🔍❌ No customer found in SF with name <strong>'{ai_customer_name}'</strong> for company <strong>'{ai_company_name}'</strong>!")
        
    print_main_tag("")
    
    return sf_contact_obj, nb_contacts
        
def search_company_in_sf_db(ai_customer_name,ai_company_name,ai_company_country):
    
    sf_account_obj = None
    nb_accounts    = 0
    
    if ai_company_name != ITEM_NO_INFO:
        sf_account_obj = db_sf.db_sf_find_account_from_name_country(ai_company_name,ai_company_country)
        
        nb_accounts = len(sf_account_obj) if sf_account_obj else 0
        
        if nb_accounts == 1:
            print_main_tag(f"🎯 Found company '{sf_account_obj[0]['Name']}' in SF from name <strong>'{ai_company_name}'</strong>! located in {sf_account_obj[0]['BillingCountry']} type: {db_sf_conv.transform_sf_account_type(sf_account_obj[0])} brand: '{sf_account_obj[0]['Brand__c']}'")
        elif nb_accounts > 1:
            print_main_tag(f"⚠️ Found several company in SF with name <strong>'{ai_company_name}'</strong>!")
            for a in sf_account_obj:
                print_main_tag(f"\t\t- '{a['Name']}' located in '{a['BillingCountry']}' type: '{db_sf_conv.transform_sf_account_type(a)}' brand: '{sf_account_obj[0]['Brand__c']}'")
        else:
            print_main_tag(f"⚠️ No entry found in SF, new company '{ai_company_name}' and new customer '{ai_customer_name}' to create!")
    
    return sf_account_obj, nb_accounts

def check_customer_and_company_information(questionnaire_data):
    
    item_company_name                 = get_item_by_key_name("company_name",questionnaire_data)
    item_company_brand_name           = get_item_by_key_name("company_brand_name",questionnaire_data)
    item_company_location             = get_item_by_key_name("company_location",questionnaire_data)
    item_company_type                 = get_item_by_key_name("company_type",questionnaire_data)
    
    item_customer_name                = get_item_by_key_name("customer_name",questionnaire_data)
    item_customer_job_title           = get_item_by_key_name("customer_job_title",questionnaire_data)
    item_customer_department          = get_item_by_key_name("customer_department",questionnaire_data)
    item_customer_email               = get_item_by_key_name("customer_email",questionnaire_data)
    item_customer_phone_number        = get_item_by_key_name("customer_phone_number",questionnaire_data)
    item_customer_mobile_phone_number = get_item_by_key_name("customer_mobile_phone_number",questionnaire_data)
    
    ai_customer_name      = item_get_value(item_customer_name)
    ai_customer_email     = item_get_value(item_customer_email)
    ai_company_name       = item_get_value(item_company_name)
    ai_company_brand_name = item_get_value(item_company_brand_name)
    ai_company_country    = item_get_value(item_company_location)
    ai_company_type       = item_get_value(item_company_type)
    
    print_debug("Information from AI, before checks...")
    
    print_debug(f"item_company_name                 : {ai_company_name}")
    print_debug(f"item_company_location             : {ai_company_country}")
    print_debug(f"item_company_type                 : {ai_company_type}")
    
    print_debug(f"item_customer_name                : {ai_customer_name}")
    print_debug(f"item_customer_job_title           : {item_get_value(item_customer_job_title)}")
    print_debug(f"item_customer_department          : {item_get_value(item_customer_department)}")
    print_debug(f"item_customer_email               : {ai_customer_email}")
    print_debug(f"item_customer_phone_number        : {item_get_value(item_customer_phone_number)}")
    print_debug(f"item_customer_mobile_phone_number : {item_get_value(item_customer_mobile_phone_number)}")
    
    #company_name, company_brand = check_company_name_in_sf_db(ai_company_name)
    
    company_name  = item_get_value_checked(item_company_name)
    company_brand = item_get_value_checked(item_company_brand_name)
    
    if isinstance(company_name,str):
        update_item_value(item_company_name,company_name)
    elif company_name:
        print_debug(f"⚠️ No update for company name as several companies found from name '{ai_company_name}' candidates: '{company_name}'")

    #company_location = check_company_country_in_sf_db(ai_company_country)
    
    company_location = item_get_value_checked(item_company_location)
    
    update_item_value(item_company_location,company_location)
    
    #company_type = check_company_type_in_sf_db(ai_company_type)
    
    company_type = item_get_value_checked(item_company_type)
    
    update_item_value(item_company_type,company_type)
        
    sf_contact_obj = None
    sf_account_obj = None
    nb_contacts    = 0
    nb_accounts    = 0
    
    sf_contact_obj,nb_contacts = search_customer_in_sf_db(ai_customer_email,ai_customer_name,ai_company_name,ai_company_country)
        
    if sf_contact_obj:
        if nb_contacts == 1:
            sf_account_obj = db_sf.db_sf_get_account_by_id(sf_contact_obj[0]["AccountId"])
            
            data = append_sf_instance("PrimaryContact","Contact",sf_contact_obj[0],sf_data_section=None,replaceAiAnswer=True)
            data = append_sf_instance("Account","Account",sf_account_obj[0],sf_data_section=data,replaceAiAnswer=True)
            #data = append_sf_instance("PrimaryContactRole","OpportunityContactRole",{"sf_id":"-1","Role":"Evaluator"},sf_data_section=data,replaceAiAnswer=True)
            
            map_sf_object_to_questionnaire(questionnaire_data,data)
            
            update_item_value(item_company_type,db_sf_conv.transform_sf_account_type(sf_account_obj[0]))
            
            print_main_tag(hr.render_sf_contact_and_company_card(sf_contact_obj[0],sf_account_obj[0]),html=True)
            
            opportunities = db_sf.db_sf_get_opportunities_for_contact(sf_contact_obj[0]['sf_id'])
            
            print_main_tag("\n<strong>Contact's Opportunities:</strong>\n")
            
            print_main_tag(hr.render_sf_contact_opportunities(opportunities),html=True)
            
            opportunities = db_sf.db_sf_get_opportunities_with_lines_for_account(sf_account_obj[0]['sf_id'])
            
            print_main_tag("\n<strong>Account's Opportunities:</strong>\n")

            print_main_tag(hr.render_sf_account_opportunities(opportunities),html=True)
            
            set_account_invoice_entities(opportunities, questionnaire_data)
            
        else:
            print_main_tag("⚠️ Please correct AI response with the appropriate customer name and company. Opportunity cannot be created right now.")
    elif ai_company_name != ITEM_NO_INFO:
        print_main_tag(f"⚠️ Customer '{ai_customer_name}' has not been found into Sales Force database for company '{ai_company_name}', new entry creation...")
        
        sf_account_obj,nb_accounts = search_company_in_sf_db(ai_customer_name,ai_company_name,ai_company_country)
        
        if nb_accounts == 1:
            sf_account_obj = sf_account_obj[0]
            
            data = append_sf_instance("Account","Account",sf_account_obj,sf_data_section=None,replaceAiAnswer=True)
            
            map_sf_object_to_questionnaire(questionnaire_data,data)
            
            update_item_value(item_company_type,db_sf_conv.transform_sf_account_type(sf_account_obj))
            
            opportunities = db_sf.db_sf_get_opportunities_with_lines_for_account(sf_account_obj['sf_id'])
            
            print_main_tag("\n<strong>Account's Opportunities:</strong>\n")

            print_main_tag(hr.render_sf_account_opportunities(opportunities),html=True)

            set_account_invoice_entities(opportunities, questionnaire_data)
            
            db_sf.db_sf_create_new_contact_for_account(sf_account_obj)
            
        elif nb_accounts > 1:
            print_main_tag("⚠️ Please correct AI response with the appropriate company name, customer name not found in SF and will be created when account is identified. Opportunity cannot be created right now.")
        elif nb_accounts == 0:
            db_sf.db_sf_create_new_account_and_contact()
    else:
        print_main_tag(f"⚠️ Customer '{ai_customer_name}' has not been found into Sales Force database for company '{ai_company_name}', new entry creation...")
        
    return questionnaire_data