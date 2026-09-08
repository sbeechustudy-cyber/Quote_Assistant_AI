import products.product_license_types as pdlt

pricelist_regions_to_currency_iso_code = { 'India':'INR', 'China':'CNY', 'Euro':'EUR', 'North America':'USD', 'Continental':'EUR', 'Japan':'JPY', 'South Korea':'KRW'}
currency_iso_code_to_pricelist_regions = { 'CNY':'China', 'EUR':'Euro', 'INR':'India', 'ILS': 'Euro', 'JPY':'Japan', 'KRW':'South Korea','SGD':'North America', 'USD':'North America'}

pricelist_regions    = ['India', 'China', 'Euro', 'North America', 'Continental', 'Japan', 'South Korea']
pricelist_currencies = ['CNY', 'EUR', 'INR', 'JPY', 'KRW', 'SGD', 'USD']

sales_regions_to_pricelist_regions = { 'India':'India', 'China':'China', 'Europe':'Euro', 'Americas':'North America', 'Continental':'Continental', 'Japan':'Japan', 'South Korea':'South Korea'}
pricelist_regions_to_sales_regions = { 'India':'India', 'China':'China', 'Euro':'Europe', 'North America':'Americas', 'Continental':'Continental', 'Japan':'Japan', 'South Korea':'South Korea'}

currency_iso_code            = ['CNY','EUR','INR','ILS','JPY','KRW','SGD','USD']
currency_iso_code_to_label   = {'CNY':'Chinese Yuan','EUR':'Euro','INR':'Indian Rupee','ILS':'Israeli Shekel','JPY':'Japanese Yen','KRW':'Korean Won','SGD':'Singapore Dollar','USD':'U.S. Dollar'}
currency_iso_code_to_symbole = {'CNY':'¥','EUR':'€','INR':'₹','ILS':'','JPY':'¥','KRW':'₩','SGD':'S$','USD':'$'}
currency_iso_label_to_code   = {'Chinese Yuan':'CNY','Euro':'EUR','Indian Rupee':'INR','Israeli Shekel':'ILS','Japanese Yen':'JPY','Korean Won':'KRW','Singapore Dollar':'SGD','U.S. Dollar':'USD'}

account_type_trans_sf_2_tool = {'Brand':'N/A', 'Group':'N/A', 'Other':'Other/University/Non-Automotive', 'TX':'Supplier/Tier1/Tier2', 'SIL':'Semiconductors', 'CV':'OEM','EV Startup':'OEM', 'LV':'OEM', 'ULV':'OEM'}
account_type_trans_tool_2_sf = {'Other':'Other','University':'Other','Non-Automotive':'Other', 'Supplier':'TX','Tier1':'TX','Tier2':'TX', 'Semiconductors':'SIL', 'OEM':'CV/EV Startup/LV/ULV'}

sf_product_family = ["Engineering Service","Hardware","License","Maintenance","Update Right"]

sf_product_family_mapping_to_pricelist = {

    "Engineering Service" : pdlt.rtc_tresos_porting_types + pdlt.rtc_tresos_qp_types + pdlt.rtc_tresos_ip_types + pdlt.rtc_zoneo_zentur_qp_types + pdlt.rtc_zentur_porting_types,
    "Hardware" : [],
    "License" : pdlt.rtc_license_types + pdlt.rtc_royalty_license_types + pdlt.rtc_tools_license_types + pdlt.rtc_tools_license_subscription_types,
    "Update Right": pdlt.rtc_dev_maintenance_license_types + pdlt.rtc_lts_maintenance_license_types + pdlt.rtc_cyber_maintenance_license_types + pdlt.rtc_maintenance_subscription_types + pdlt.rtc_tools_maintenance_license_types
}

def transform_sf_account_type(sf_account_obj):
    type = account_type_trans_sf_2_tool[sf_account_obj['EB_Account_Type__c']]
    return type.split("/")[0]
