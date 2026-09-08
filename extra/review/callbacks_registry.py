from .section_01_customer_information import *
from .section_02_project_information import *
from .section_03_platform_information import *
from .section_04_ecu_communication import *
from .section_05_ecu_functional_safety import *
from .section_06_ecu_security import *
from .section_07_ecu_software_update import *
from .section_08_additional_features import *
from .section_09_maintenance_and_tools import *
from .section_10_platform_services import *
from .section_11_quote_preparation import *

questionnaire_callbacks = {
    'customer_information': {
        'precheck_func': customer_information_section_pre_check_values_cb,
        'consolidate_func': customer_information_section_consolidate_values_cb,
        'values_to_check': {
            'customer_name': customer_name_check_value_cb,
            'company_name': company_name_check_value_cb,
            'company_brand_name': company_brand_name_check_value_cb,
            'company_location': company_location_check_value_cb,
            'customer_job_title': customer_job_title_check_value_cb,
            'customer_department': customer_department_check_value_cb,
            'customer_email': customer_email_check_value_cb,
            'customer_phone_number': customer_phone_number_check_value_cb,
            'customer_mobile_phone_number': customer_mobile_phone_number_check_value_cb,
            'customer_role': customer_role_check_value_cb,
            'company_type': company_type_check_value_cb,
            'company_customer_comments': company_customer_comments_check_value_cb
        }
    },
    'project_information': {
        'precheck_func': project_information_section_pre_check_values_cb,
        'consolidate_func': project_information_section_consolidate_values_cb,
        'values_to_check': {
            'project_name': project_name_check_value_cb,
            'project_ecu_name': project_ecu_name_check_value_cb,
            'project_oem_name': project_oem_name_check_value_cb,
            'project_nb_oems': project_nb_oems_check_value_cb,
            'project_oem_car_platform': project_oem_car_platform_check_value_cb,
            'project_nb_oem_car_platform': project_nb_oem_car_platform_check_value_cb,
            'project_production_duration': project_production_duration_check_value_cb,
            'project_phase': project_phase_check_value_cb,
            'project_license_type': project_license_type_check_value_cb,
            'project_customer_comments': project_customer_comments_check_value_cb
        }
    },
    'platform_information': {
        'precheck_func': platform_information_section_pre_check_values_cb,
        'consolidate_func': platform_information_section_consolidate_values_cb,
        'values_to_check': {
            'target_µC_manufacturer': target_µC_manufacturer_check_value_cb,
            'target_µC_family': target_µC_family_check_value_cb,
            'target_µC_derivative': target_µC_derivative_check_value_cb,
            'target_autosar_version': target_autosar_version_check_value_cb,
            'target_compiler_vendor': target_compiler_vendor_check_value_cb,
            'target_compiler_version': target_compiler_version_check_value_cb,
            'target_mcal_vendor_name': target_mcal_vendor_name_check_value_cb,
            'target_mcal_vendor_version': target_mcal_vendor_version_check_value_cb,
            'target_customer_comments': target_customer_comments_check_value_cb
        }
    },
    'ecu_communication': {
        'precheck_func': ecu_communication_section_pre_check_values_cb,
        'consolidate_func': ecu_communication_section_consolidate_values_cb,
        'values_to_check': {
            'ecu_com_can_transceivers_list': ecu_com_can_transceivers_list_check_value_cb,
            'ecu_com_flexray_transceivers_list': ecu_com_flexray_transceivers_list_check_value_cb,
            'ecu_com_ethernet_transceivers_list': ecu_com_ethernet_transceivers_list_check_value_cb,
            'ecu_com_ethernet_driver_required': ecu_com_ethernet_driver_required_check_value_cb,
            'ecu_com_ethernet_switch_reference': ecu_com_ethernet_switch_reference_check_value_cb,
            'ecu_com_customer_comment': ecu_com_customer_comment_check_value_cb
        }
    },
    'ecu_functional_safety': {
        'precheck_func': ecu_functional_safety_section_pre_check_values_cb,
        'consolidate_func': ecu_functional_safety_section_consolidate_values_cb,
        'values_to_check': {
            'safety_customer_comment': safety_customer_comment_check_value_cb
        }
    },
    'ecu_security': {
        'precheck_func': ecu_security_section_pre_check_values_cb,
        'consolidate_func': ecu_security_section_consolidate_values_cb,
        'values_to_check': {
            'security_customer_comments': security_customer_comments_check_value_cb
        }
    },
    'ecu_software_update': {
        'precheck_func': ecu_software_update_section_pre_check_values_cb,
        'consolidate_func': ecu_software_update_section_consolidate_values_cb,
        'values_to_check': {
            'swu_customer_comments': swu_customer_comments_check_value_cb
        }
    },
    'additional_features': {
        'precheck_func': additional_features_section_pre_check_values_cb,
        'consolidate_func': additional_features_section_consolidate_values_cb,
        'values_to_check': {
            'addon_customer_comments': addon_customer_comments_check_value_cb
        }
    },
    'maintenance_and_tools': {
        'precheck_func': maintenance_and_tools_section_pre_check_values_cb,
        'consolidate_func': maintenance_and_tools_section_consolidate_values_cb,
        'values_to_check': {
            'maintenance_customer_comments': maintenance_customer_comments_check_value_cb
        }
    },
    'platform_services': {
        'precheck_func': platform_services_section_pre_check_values_cb,
        'consolidate_func': platform_services_section_consolidate_values_cb,
        'values_to_check': {
            'platform_service_customer_comments': platform_service_customer_comments_check_value_cb
        }
    },
    'quote_preparation': {
        'precheck_func': quote_preparation_section_pre_check_values_cb,
        'consolidate_func': quote_preparation_section_consolidate_values_cb,
        'values_to_check': {
            'quote_general_comment': quote_general_comment_check_value_cb,
            'quote_deadline': quote_deadline_check_value_cb,
            'quote_request_date': quote_request_date_check_value_cb,
            'quote_close_date': quote_close_date_check_value_cb,
            'quote_recipient': quote_recipient_check_value_cb
        }
    }
}
