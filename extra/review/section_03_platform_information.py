import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utility import print_main,print_main_tag, print_debug, print_priceIndication, print_priceListExtract
from tools import unix_path, setup_logger, fuzzy_match, get_integer, fmt_money, truncate_text
import db_sales_force as db_sf
import db_sales_force_conversion as db_sf_conv
import html_renderer as hr
import db_unified_hardware_list as db_uhwl
from product_questionnaire_db_connector import is_item_value_in_db_sf_picklist, update_item_db_value
from product_questionnaire import is_item_has_no_information

logger = setup_logger()

MODULE_DIR = os.path.dirname(__file__)

# Callbacks for platform_information


def platform_information_section_pre_check_values_cb(questionnaire,item,key_name,value):
    """Auto-generated callback: TODO implement logic for platform_information_section_pre_check_values_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'platform_information_section_pre_check_values_cb' not implemented for key '{key_name}'")
    return questionnaire, output_string


def platform_information_section_consolidate_values_cb(questionnaire,item,key_name,value):
    """Auto-generated callback: TODO implement logic for platform_information_section_consolidate_values_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'platform_information_section_consolidate_values_cb' not implemented for key '{key_name}'")
    return questionnaire, output_string


def target_µC_manufacturer_check_value_cb(parent_item,item,key_name,ai_silicon_manufacturer_name):
    """Auto-generated callback: TODO implement logic for target_µC_manufacturer_check_value_cb"""
    output_string             = None
    silicon_manufacturer_name = None
    
    if is_item_has_no_information(ai_silicon_manufacturer_name):
        silicon_manufacturer_name = 'Microcontroller not defined yet, too early stage'
        output_string = f"⚠️ Silicon manufacturer name is not known at this stage!"
    else:
        res = db_uhwl.search_silicon_vendor(ai_silicon_manufacturer_name)
        nb_res = len(res)
        if nb_res == 1:
            silicon_manufacturer_name = res[0]['vendor']
            sf_value = is_item_value_in_db_sf_picklist(silicon_manufacturer_name,item)
            
            if not sf_value:
                output_string = f"⚠️ Silicon vendor name '{ai_silicon_manufacturer_name}' found in Unified hardware list as '{silicon_manufacturer_name}' but not in Salesforce picklist!"
                update_item_db_value(item,None)
            else:
                output_string = f"🎯 Silicon vendor name '{ai_silicon_manufacturer_name}' found in Unified hardware list and Salesforce picklist as '{sf_value}'!"
                silicon_manufacturer_name = sf_value
        else:
            sf_value = is_item_value_in_db_sf_picklist(ai_silicon_manufacturer_name,item)
            output_string  = []
            if nb_res == 0:
                output_string.append(f"🔍❌ Silicon vendor name '{ai_silicon_manufacturer_name}' not found in Unified hardware list database!")
            else:
                output_string.append(f"⚠️ Several Silicon vendor name '{ai_silicon_manufacturer_name}' found in Unified hardware list database:")
                for r in res:
                    output_string.append(f"- Silicon vendor name '{r['vendor']}'")
            
            if not sf_value:
                output_string.append(f"⚠️ Silicon vendor name '{ai_silicon_manufacturer_name}' not found in Salesforce picklist!")
                update_item_db_value(item,None)
                if res == 0:
                    silicon_manufacturer_name = ai_silicon_manufacturer_name
                else:
                    silicon_manufacturer_name = []
                    for r in res:
                        silicon_manufacturer_name.append(r['vendor'])
            else:
                output_string.append(f"🎯 Silicon vendor name '{ai_silicon_manufacturer_name}' found in Salesforce picklist as {sf_value}!")
                update_item_db_value(item,sf_value)
                if res == 0:
                    silicon_manufacturer_name = sf_value
                else:
                    silicon_manufacturer_name = []
                    for r in res:
                        silicon_manufacturer_name.append(r['vendor'])

    return silicon_manufacturer_name, output_string


def target_µC_family_check_value_cb(parent_item,item,key_name,ai_family_name):
    """Auto-generated callback: TODO implement logic for target_µC_family_check_value_cb"""
    output_string        = None
    family_name          = None
    ai_family_name_lower = ai_family_name.lower()
    
    if is_item_has_no_information(ai_family_name):
        family_name = None
        output_string = f"⚠️ µC or SoC family name is not known at this stage!"
    else:
        res = db_uhwl.search_families(ai_family_name)
        nb_res = len(res)
        
        if nb_res > 1:
            for r in res:
                if r['family'].lower() == ai_family_name_lower:
                    res[0]=r
                    nb_res = 1
                    break
        
        if nb_res == 1:
            family_name = res[0]['family']
            serie_name  = res[0]['serie']
            sf_family_value = is_item_value_in_db_sf_picklist(family_name,item)
            sf_serie_value  = is_item_value_in_db_sf_picklist(serie_name,item)
            
            if not sf_family_value and not sf_serie_value:
                output_string = f"⚠️ µC or SoC Family name '{ai_family_name}' found in Unified hardware list as '{family_name}' but not in Salesforce picklist!"
                update_item_db_value(item,None)
            elif sf_family_value:
                output_string = f"🎯 µC or SoC Family name '{ai_family_name}' found in Unified hardware list and Salesforce picklist as '{sf_family_value}'!"
                update_item_db_value(item,sf_family_value)
            elif sf_serie_value:
                output_string = f"🎯⚠️ µC or SoC Family name '{ai_family_name}' found in Unified hardware list as '{family_name}' but Salesforce picklist as '{sf_serie_value}'!"
                update_item_db_value(item,sf_serie_value)               
        else:
            output_string  = []
            sf_family_value = is_item_value_in_db_sf_picklist(ai_family_name,item)
            sf_serie_value  = is_item_value_in_db_sf_picklist(ai_family_name,item)              
            if nb_res == 0:
                output_string.append(f"🔍❌ µC or SoC Family name '{ai_family_name}' not found in Unified hardware list database!")
            else:
                output_string.append(f"⚠️ Several µC or SoC Family name '{ai_family_name}' found in Unified hardware list database:")
                for r in res:
                    output_string.append(f"- µC or SoC Family name '{r['family']}' for serie '{r['serie']}'")
            
            if not sf_family_value and not sf_serie_value:
                output_string.append(f"⚠️ µC or SoC Family name '{ai_family_name}' not found in Salesforce picklist!")
                update_item_db_value(item,None)
                if res == 0:
                    family_name = ai_family_name
                else:
                    family_name = []
                    for r in res:
                        family_name.append(r['family'])                
            elif sf_family_value:
                output_string.append(f"🎯 µC or SoC Family name '{ai_family_name}' found in Salesforce picklist as '{sf_family_value}'!")
                update_item_db_value(item,sf_family_value)
                if res == 0:
                    family_name = sf_family_value
                else:
                    family_name = []
                    for r in res:
                        family_name.append(r['family'])  
            elif sf_serie_value:
                output_string.append(f"🎯⚠️ µC or SoC Family name '{ai_family_name}' found in Salesforce picklist as '{sf_serie_value}'!")
                update_item_db_value(item,sf_serie_value)
                if res == 0:
                    family_name = ai_family_name
                else:
                    family_name = []
                    for r in res:
                        family_name.append(r['family'])                 
    
    return family_name, output_string


def target_µC_derivative_check_value_cb(parent_item,item,key_name,ai_derivative_name):
    """Auto-generated callback: TODO implement logic for target_µC_derivative_check_value_cb"""
    output_string   = None
    derivative_name = None
    ai_derivative_name_lower = ai_derivative_name.lower()
    
    if is_item_has_no_information(ai_derivative_name):
        derivative_name = None
        output_string = f"⚠️ µC or SoC derivative name is not known at this stage!"
    else:
        res = db_uhwl.search_derivative(ai_derivative_name)
        nb_res = len(res)

        if nb_res > 1:
            for r in res:
                if r['derivative'].lower() == ai_derivative_name_lower:
                    res[0]=r
                    nb_res = 1
                    break
        
        if nb_res == 1:
            derivative_name = res[0]['derivative']
            sf_derivative_name = is_item_value_in_db_sf_picklist(derivative_name,item)
            
            if not sf_derivative_name:
                output_string = f"⚠️ µC or SoC Derivative name '{ai_derivative_name}' found in Unified hardware list as '{derivative_name}' but not in Salesforce picklist!"
                update_item_db_value(item,None)
            else:
                output_string = f"🎯 µC or SoC Derivative name '{ai_derivative_name}' found in Unified hardware list and Salesforce picklist as '{sf_derivative_name}'!"
                update_item_db_value(item,sf_derivative_name)
        else:
            output_string  = []
            sf_derivative_name = is_item_value_in_db_sf_picklist(ai_derivative_name,item)
            if nb_res == 0:
                output_string.append(f"🔍❌ µC or SoC Derivative name '{ai_derivative_name}' not found in Unified hardware list database!")
            else:
                output_string.append(f"⚠️ Several µC or SoC Derivative name '{ai_derivative_name}' found in Unified hardware list database:")
                for r in res:
                    output_string.append(f"- µC or SoC Derivative name '{r['derivative']}' for family '{r['family']}' and serie '{r['serie']}'")
            
            if not sf_derivative_name:
                output_string.append(f"⚠️ µC or SoC Derivative name '{ai_derivative_name}' not found in Salesforce picklist!")
                update_item_db_value(item,None)
                if res == 0:
                    derivative_name = ai_derivative_name
                else:
                    derivative_name = []
                    for r in res:
                        derivative_name.append(r['derivative'])                
            else:
                output_string.append(f"🎯 µC or SoC Derivative name '{ai_derivative_name}' found in Salesforce picklist as '{sf_derivative_name}'!")
                update_item_db_value(item,sf_derivative_name)
                if res == 0:
                    derivative_name = sf_derivative_name
                else:
                    derivative_name = []
                    for r in res:
                        derivative_name.append(r['derivative'])   
                
    return derivative_name, output_string

def target_autosar_version_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for target_autosar_version_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'target_autosar_version_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string


def target_compiler_vendor_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for target_compiler_vendor_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'target_compiler_vendor_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string


def target_compiler_version_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for target_compiler_version_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'target_compiler_version_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string


def target_mcal_vendor_name_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for target_mcal_vendor_name_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'target_mcal_vendor_name_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string


def target_mcal_vendor_version_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for target_mcal_vendor_version_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'target_mcal_vendor_version_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string


def target_customer_comments_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for target_customer_comments_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'target_customer_comments_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string
