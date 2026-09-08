import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utility import print_main,print_main_tag, print_debug, print_priceIndication, print_priceListExtract
from tools import unix_path, setup_logger, fuzzy_match, get_integer, fmt_money, truncate_text
import db_sales_force as db_sf
import db_sales_force_conversion as db_sf_conv
import html_renderer as hr

logger = setup_logger()

MODULE_DIR = os.path.dirname(__file__)

# Callbacks for maintenance_and_tools


def maintenance_and_tools_section_pre_check_values_cb(questionnaire,item,key_name,value):
    """Auto-generated callback: TODO implement logic for maintenance_and_tools_section_pre_check_values_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'maintenance_and_tools_section_pre_check_values_cb' not implemented for key '{key_name}'")
    return questionnaire, output_string


def maintenance_and_tools_section_consolidate_values_cb(questionnaire,item,key_name,value):
    """Auto-generated callback: TODO implement logic for maintenance_and_tools_section_consolidate_values_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'maintenance_and_tools_section_consolidate_values_cb' not implemented for key '{key_name}'")
    return questionnaire, output_string


def maintenance_customer_comments_check_value_cb(parent_item,item,key_name,value):
    """Auto-generated callback: TODO implement logic for maintenance_customer_comments_check_value_cb"""
    output_string = None
    logger.debug(f"[Warning] Function 'maintenance_customer_comments_check_value_cb' not implemented for key '{key_name}'")
    return value, output_string
