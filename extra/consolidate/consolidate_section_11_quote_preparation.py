from datetime import datetime, timedelta
from product_questionnaire import item_get_value_checked, get_item_by_key_name, item_get_value,item_get_default_value, ITEM_NO_INFO, is_item_has_no_information, get_items_value_from_section
from product_questionnaire_db_connector import item_get_sf_object_id, update_item_value
import db_sales_force as db_sf
import db_sales_force_conversion as db_sf_conv
from db_price_list import get_pricelist_region_and_currency
from db_price_list_if import DEFAULT_PRICELIST_CURRENCY, DEFAULT_LICENSE_TYPE
from utility import print_main,print_main_tag, print_debug, print_priceIndication, print_priceListExtract
from tools import normalize_date,normalize_date_iso, end_of_month_plus_n_days, compute_first_delivery_date, days_diff_from_now, shift_date_by_n_days
from product_questionnaire_db_connector import get_account_invoice_entities, set_price_list_region, get_sf_object_reference_id, get_price_list_region
import html_renderer as hr
    
def check_quote_region_and_currency(questionnaire_data):
    
    db_ae_group      = ""
    db_sales_region  = ""
    pricelist_region = db_sf_conv.currency_iso_code_to_pricelist_regions[DEFAULT_PRICELIST_CURRENCY]
    
    item_company_name            = get_item_by_key_name("company_name",questionnaire_data)
    item_quote_currency_iso_code = get_item_by_key_name("quote_currency_iso_code",questionnaire_data)
    
    print_debug("Information from AI, before checks...")
    print_debug(f"item_quote_currency_iso_code: {item_quote_currency_iso_code['key_value']}")
    
    ai_quote_currenty      = item_get_value(item_quote_currency_iso_code)
    default_quote_currency = item_get_default_value(item_quote_currency_iso_code)
    sf_account_obj         = db_sf.db_sf_get_account_by_id(item_get_sf_object_id(item_company_name))

    if default_quote_currency not in db_sf_conv.currency_iso_code:
        default_quote_currency = DEFAULT_PRICELIST_CURRENCY
    
    if not sf_account_obj:
        if ai_quote_currenty is None or ai_quote_currenty not in db_sf_conv.currency_iso_code:
            print_main_tag(f"🔍❌ No quote currency identified ('{ai_quote_currenty}') for new account, then use default one '{default_quote_currency}'.")
            ai_quote_currenty = default_quote_currency
            update_item_value(item_quote_currency_iso_code,ai_quote_currenty)
        else:
            print_main_tag(f"🎯 Quote currency identified ('{ai_quote_currenty}') for new account.")
        
        pricelist_region = db_sf_conv.currency_iso_code_to_pricelist_regions[ai_quote_currenty]
        db_ae_group      = "tbd"
        db_sales_region  = "tbd"
        db_currency      = ai_quote_currenty
    else:
        sf_account_obj = sf_account_obj[0]
        
        db_company_name       = sf_account_obj['Name']
        db_company_brand_name = sf_account_obj['Brand__c']
        db_company_group_name = sf_account_obj['Group__c']
        db_ae_group           = sf_account_obj['AE_Group__c']
        db_currency           = sf_account_obj['CurrencyIsoCode']
        db_sales_region       = sf_account_obj['Sales_Region__c']

        pricelist_region,ai_quote_currenty,conti_pricelist = get_pricelist_region_and_currency(db_company_group_name,db_company_brand_name,db_company_name,db_currency,ai_quote_currenty)

        if conti_pricelist:
            update_item_value(item_quote_currency_iso_code,ai_quote_currenty)
            
    set_price_list_region(pricelist_region,questionnaire_data)
    
    #check quoted region
    if ai_quote_currenty is None or ai_quote_currenty not in db_sf_conv.currency_iso_code:
        print_main_tag(f"❌ No quote currency defined in the report: '{ai_quote_currenty}' so using info from SF db according to account's currency '{db_currency}' then price list to use is '{pricelist_region}' for account '{db_company_name}'!")
        ai_quote_currenty = db_currency
        update_item_value(item_quote_currency_iso_code,ai_quote_currenty)
    elif db_currency.lower() != ai_quote_currenty.lower():
        print_main_tag(f"⚠️ Requested Quote currency '{ai_quote_currenty}' is different from SalesForce Account region is '{db_sales_region}' and currency is '{db_currency}' for account '{db_company_name}'!")
    else:
        print_debug(f"🎯 Quote currency '{ai_quote_currenty}' identified for price list region '{pricelist_region}'.")

    final_msg = f"✅ Quote is established for '{pricelist_region}' pricelist with currency '{ai_quote_currenty}', sales region is '{db_sales_region}' and AE Group is '{db_ae_group}'.\n"
    
    #print_main_tag(final_msg)
    print_priceIndication(final_msg)
    print_priceListExtract(final_msg)

    return questionnaire_data
    
def check_quote_preparation_information(questionnaire_data):
    
    questionnaire_data = check_quote_region_and_currency(questionnaire_data)
    
    item_project_name                    = get_item_by_key_name("project_name",questionnaire_data)
    item_quote_preparation               = get_item_by_key_name("quote_preparation",questionnaire_data)
    item_quote_deadline                  = get_item_by_key_name("quote_deadline",questionnaire_data)
    item_quote_request_date              = get_item_by_key_name("quote_request_date",questionnaire_data)
    item_quote_close_date                = get_item_by_key_name("quote_close_date",questionnaire_data)
    item_quote_business_type             = get_item_by_key_name("quote_business_type",questionnaire_data)
    item_quote_invoicing_entity          = get_item_by_key_name("quote_invoicing_entity",questionnaire_data)
    item_quote_currency_iso_code         = get_item_by_key_name("quote_currency_iso_code",questionnaire_data)
    item_quote_recipient                 = get_item_by_key_name("quote_recipient",questionnaire_data)
    
    item_company_name                    = get_item_by_key_name("company_name",questionnaire_data)
    item_customer_name                   = get_item_by_key_name("customer_name",questionnaire_data)
    
    item_target_µC_manufacturer          = get_item_by_key_name("target_µC_manufacturer",questionnaire_data)
    item_target_µC_family                = get_item_by_key_name("target_µC_family",questionnaire_data)
    item_target_µC_derivative            = get_item_by_key_name("target_µC_derivative",questionnaire_data)
    
    ai_customer_name     = item_get_value(item_customer_name)
    ai_company_name      = item_get_value(item_company_name)
    
    ai_project_name      = item_get_value(item_project_name)
    ai_quote_deadline    = item_get_value(item_quote_deadline)
    ai_request_date      = item_get_value(item_quote_request_date)
    ai_close_date        = item_get_value(item_quote_close_date)
    ai_business_type     = item_get_value(item_quote_business_type)
    ai_invoicing_entity  = item_get_value(item_quote_invoicing_entity)
    ai_currency_iso_code = item_get_value(item_quote_currency_iso_code)
    ai_quote_recipient   = item_get_value(item_quote_recipient)
    
    ai_target_µC_manufacturer = item_get_value(item_target_µC_manufacturer)
    ai_target_µC_family       = item_get_value(item_target_µC_family)
    ai_target_µC_derivative   = item_get_value(item_target_µC_derivative)
    
    sf_account_obj            = db_sf.db_sf_get_account_by_id(item_get_sf_object_id(item_company_name))
    
    print_debug("Information from AI, before checks...")

    print_debug(f"item_customer_name           : {ai_customer_name}")
    print_debug(f"item_company_name            : {ai_company_name}")
    
    print_debug(f"item_project_name            : {ai_project_name}")
    print_debug(f"item_quote_deadline          : {ai_quote_deadline}")
    print_debug(f"item_quote_request_date      : {ai_request_date}")
    print_debug(f"item_quote_close_date        : {ai_close_date}")
    print_debug(f"item_quote_business_type     : {ai_business_type}")
    print_debug(f"item_quote_invoicing_entity  : {ai_invoicing_entity}")
    print_debug(f"item_quote_currency_iso_code : {ai_currency_iso_code}")
    print_debug(f"item_quote_recipient         : {ai_quote_recipient}")
    
    print_debug(f"ai_target_µC_manufacturer    : {ai_target_µC_manufacturer}")
    print_debug(f"ai_target_µC_family          : {ai_target_µC_family}")
    print_debug(f"ai_target_µC_derivative      : {ai_target_µC_derivative}")
        
    quote_deadline = item_get_value_checked(item_quote_deadline)
    if is_item_has_no_information(quote_deadline):
        quote_deadline = end_of_month_plus_n_days(None,default_offset=7)    
    update_item_value(item_quote_deadline,quote_deadline)

    quote_request_date = item_get_value_checked(item_quote_request_date)

    if is_item_has_no_information(quote_request_date):
        quote_request_date = normalize_date_iso(None)
    update_item_value(item_quote_request_date,quote_request_date)
    
    quote_close_date = item_get_value_checked(item_quote_close_date)
    if is_item_has_no_information(quote_close_date):
        quote_close_date = end_of_month_plus_n_days()
    update_item_value(item_quote_close_date,quote_close_date)

    diff = days_diff_from_now(quote_deadline,quote_request_date)
    
    if diff < 0:
        up_quote_deadline = shift_date_by_n_days(offset_in_days=7)
        print_main_tag(f"\t⚠️ quote deadline  '{quote_deadline}' prior to quote request date '{quote_request_date}', then set a date in the next 7 days: '{up_quote_deadline}'")
        quote_deadline = up_quote_deadline
        update_item_value(item_quote_deadline,quote_deadline)
        
    diff = days_diff_from_now(quote_request_date,quote_close_date)
    
    if diff < 0:
        up_quote_close_date = end_of_month_plus_n_days(quote_request_date,default_offset=90)
        print_main_tag(f"\t⚠️ quote close date  '{quote_close_date}' prior to quote request date '{quote_request_date}', then set a date in the next 7 days: '{up_quote_close_date}'")
        quote_close_date = up_quote_close_date
        update_item_value(item_quote_close_date,quote_close_date)        
    
    invoice_entities = get_account_invoice_entities(questionnaire_data)

    if invoice_entities and ai_invoicing_entity not in invoice_entities:
        print_main_tag(f"\t⚠️ Invoicing entity '{ai_invoicing_entity}' is not the usual one for account '{ai_company_name}' : {', '.join(invoice_entities)}")
    
    quote_recipient = item_get_value_checked(item_quote_recipient)
    
    if isinstance(quote_recipient,list) or quote_recipient == ITEM_NO_INFO or not quote_recipient:
        update_item_value(item_quote_recipient,ai_customer_name,sf_ref=item_get_sf_object_id(item_customer_name))
        
    quote_recipient_sf_id = get_sf_object_reference_id("quote_recipient",questionnaire_data)
    
    data = get_items_value_from_section("quote_preparation",questionnaire_data)
    
    data['quote_recipient_sf_id'] = quote_recipient_sf_id
    data['pricelist_region']      = get_price_list_region(questionnaire_data)#db_sf_conv.currency_iso_code_to_pricelist_regions[ai_currency_iso_code]
    data['first_delivery_date']   = normalize_date_iso(compute_first_delivery_date(quote_close_date))
        
    if sf_account_obj:
        html = hr.render_quote_preparation_data(data,sf_account_obj[0])
    else:
        html = hr.render_quote_preparation_data(data,None)

    print_main_tag(f"\n{html}")
    
    return questionnaire_data