
# ======================
# 🔹 Licenses Schem definition
# ======================

rtc_license_types = [
        "Project License",
        "Product Line License",
        "Evaluation License",
        "Concept License",
        "OEM-restricted Product Line License",
        "ECU Cross-Platform License for OEM",
        "BU License for Tier 1",
        "OEM-restricted Company License for Tier 1",
        "Company License for OEM",
        "Company License for Tier 1",
        "Template"
    ]
       
rtc_dev_maintenance_license_types = [
        "Development Maintenance for Project License",
        "Development Maintenance for Product Line License",
        "N/A",
        "N/A",
        "Development Maintenance for OEM-restricted Product Line License",
        "Development Maintenance for ECU Cross-Platform License for OEM",
        "Development Maintenance for BU License for Tier 1",
        "Development Maintenance for OEM-restricted Company License for Tier 1",
        "Development Maintenance for Company License for OEM",
        "Development Maintenance for Company License for Tier 1",
        "Unknown"
    ]       
       
rtc_lts_maintenance_license_types = [
        "Long Term Stable Maintenance for Project License",
        "Long Term Stable Maintenance for Product Line License",
        "N/A",
        "N/A",
        "Long Term Stable Maintenance for OEM-restricted Product Line License",
        "Long Term Stable Maintenance for ECU Cross-Platform License for OEM",
        "Long Term Stable Maintenance for BU License for Tier 1",
        "Long Term Stable Maintenance for OEM-restricted Company License for Tier 1",
        "Long Term Stable Maintenance for Company License for OEM",
        "Long Term Stable Maintenance for Company License for Tier 1",
        "Unknown"
    ]
    
rtc_cyber_maintenance_license_types = [
        "Cybersecurity Monitoring for Project License",
        "Cybersecurity Monitoring for Product Line License",
        "N/A",
        "N/A",
        "Cybersecurity Monitoring for OEM-restricted Product Line License",
        "Cybersecurity Monitoring for ECU Cross-Platform License for OEM",
        "Cybersecurity Monitoring for BU License for Tier 1",
        "Cybersecurity Monitoring for OEM-restricted Company License for Tier 1",
        "Cybersecurity Monitoring for Company License for OEM",
        "Cybersecurity Monitoring for Company License for Tier 1",
        "Unknown"
    ]

rtc_maintenance_subscription_types = [
        "Long Term Stable Maintenance - Subscription",
        "Cybersecurity Maintenance - Subscription"
    ]
    
rtc_maintenance_license_types = [
        rtc_lts_maintenance_license_types,
        rtc_cyber_maintenance_license_types,
        rtc_maintenance_subscription_types
    ]
    
rtc_royalty_license_types = [
        "Development License - Subscription",
        "Production License - per Unit"
    ]
    
rtc_tools_license_types = [
        "Dongled License",
        "Floating License",
        "Floating License (leased)",
        "Partner Customer Evaluation License",
        "Partner License",
        "Single-User License",
        "Single-User License (leased)"
    ]
    
rtc_tools_maintenance_license_types = [
        "Dongled License Support & Maintenance",
        "Floating License Support & Maintenance",
        "N/A",
        "N/A",
        "N/A",
        "Single-User License Support & Maintenance",
        "N/A"
    ]

rtc_tools_license_subscription_types = [
        "Floating License - Subscription",
        "Single-User License - Subscription"
    ]

rtc_tresos_porting_types = [
    "BSP - non-standard µC",
    "BSP - standard µC"
]

rtc_tresos_qp_types = [
    "QP"
]

rtc_tresos_ip_types = [
    "IP",
    "Consulting"
]

rtc_zoneo_zentur_qp_types = [
    "Qualification Package",
    "Qualification Package - Safety Approval"
]

rtc_zentur_porting_types = [
    "Porting Package"
]

all_lists = [
    rtc_maintenance_subscription_types,
    rtc_royalty_license_types,
    rtc_tools_license_types, 
    rtc_tools_maintenance_license_types,
    rtc_tools_license_subscription_types,
    rtc_tresos_porting_types,
    rtc_tresos_qp_types,
    rtc_tresos_ip_types,
    rtc_zoneo_zentur_qp_types,
    rtc_zentur_porting_types
   ]
