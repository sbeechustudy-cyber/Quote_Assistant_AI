import os
import sys
#import sqlite3 as sqlite
from sqlcipher3 import dbapi2 as sqlite
import pandas as pd
from tabulate import tabulate
from utility import print_main, print_debug, print_priceIndication, print_priceListExtract
from tools import save_json_to_file, load_json_file, setup_logger, unix_path, module_dir, delete_file, file_name
import appSecurity
import db_sales_force_conversion as db_sf_conv
import products.product_license_types as pdlt
import db_price_list_if as dbpl_if
# ======================
# Consts Private
# ======================

MODULE_DIR = module_dir(__file__)

CSV_FILE_PATH = unix_path(MODULE_DIR, 'databases','db_allPrices.csv')
DB_FILE_PATH  = unix_path(MODULE_DIR, 'databases','db_allPrices.db')
DB_TABLE_NAME = "pricelist"
DB_COL_INDEX  = unix_path(MODULE_DIR, 'databases','.db_allPrices_index.json')

CSV_LICENSE_TYPES_FILE_PATH = unix_path(MODULE_DIR,'products','license_types.csv')
DB_LICENSE_TYPES_FILE_PATH  = unix_path(MODULE_DIR, 'databases','db_licenseTypes.db')
DB_LICENSE_TYPES_TABLE_NAME = "licensetypes"
DB_LICENSE_TYPES_COL_INDEX  = unix_path(MODULE_DIR, 'databases','.db_license_types_index.json')
LICENSE_TYPE_QUALIFIED = 'yes'

CONTINETNAL_GROUP_NAME = 'Continental AG'

# ========================
# Consts Public
# ========================

# ========================
# Global variables
# ========================

logger       = setup_logger()
logger_debug = logger.debug

# ======================
# 🔹 Consts for Test
# ======================
       
test_product_items = [
        "EB tresos 9 - AutoCore Generic Base Package",
        "EB tresos 9 - AutoCore Generic Multicore Package",
        "EB tresos 9 - AutoCore Generic Safety A/B Package",
        "EB tresos 9 - AutoCore Generic Safety C/D Package",
        "EB tresos 9 - AutoCore Generic Security Package",
        "EB tresos 9 - AutoCore OEM Extension Bootloader Package for Essentials",
        "EB tresos 9 - Board Support Package Code Flash Driver",
        "EB tresos 9 - Board Support Package MCAL",
        "EB tresos 9 - Board Support Package Platform",
        "EB tresos 9 - Board Support Package Safety OS",
        "EB tresos 9 - EB tresos Studio",
        "EB tresos 9 - Safety Approval Package (OS)",
        "EB tresos 9 - Safety Approval Package (RTE, E2E, TimE)",
        "EB tresos 9 - Safety OS (up to ASIL-D) Package",
        "EB tresos 9 - SOP Qualification Package for AutoCore Generic Base",
        "EB tresos 9 - SOP Qualification Package for AutoCore Generic Multi-Core",
        "EB tresos 9 - SOP Qualification Package for AutoCore Generic Security",
        "EB tresos 9 - SOP Qualification Package for Bootloader for Essentials",
        "EB zentur - HSM Firmware",
        "EB zoneo - ACM CanTrcv <HW>",
        "EB zoneo - ACM CanTrcv <HW> Partial Networking"
    ]       
    
test_license_type = [
        "Product Line License",
        "Development Maintenance for Product Line License",
        "Long Term Stable Maintenance - Subscription",
        "Cybersecurity Maintenance - Subscription",
        "Floating License",
        "Floating License Support & Maintenance",
        "Floating License - Subscription",
        "BSP - standard µC",
        "QP",
        "IP",
        "Qualification Package",
        "Qualification Package - Safety Approval",
        "Porting Package",
    ]

# ======================
# 🔹 Enablers
# ======================

def get_all_relevant_rtc_license_types(license_type):
    list_to_append=[]
    
    if any(license_type in s for s in pdlt.rtc_license_types):
        list_to_append.append(license_type)
        dev_license = f"Development Maintenance for {license_type}"
        list_to_append.append(dev_license)
        lts_license = f"Long Term Stable Maintenance for {license_type}"
        list_to_append.append(lts_license)
        cyber_license = f"Cybersecurity Monitoring Maintenance for {license_type}"
        list_to_append.append(cyber_license)

    for i, lst in enumerate(pdlt.all_lists, start=1):
        for item in lst:
            list_to_append.append(item)        

    return list_to_append

def append_upfront_payment_license(list_to_append, license_type):

    if any(license_type in s for s in pdlt.rtc_license_types):
        list_to_append.append(license_type)
        return license_type
    else:
        print_debug(f"append_upfront_payment_license ==> {license_type} Not found!!")
        return ""
        
def append_dev_maintenance_license(list_to_append, license_type):
    if license_type and license_type != "Evaluation License" and license_type != "Concept License":
        dev_license = f"Development Maintenance for {license_type}"
        list_to_append.append(dev_license)
        return dev_license
    else:
        return "N/A"
    
def append_tools_permanent_license(list_to_append, license_type):

    if any(license_type in s for s in pdlt.rtc_tools_license_types):
        dev_license = f"{license_type} Support & Maintenance"
        list_to_append.append(license_type)
        if 'Partner' in dev_license: 
            dev_license=''
        else:
            list_to_append.append(dev_license)
        return dev_license
    else:
        print_debug(f"append_tools_permanent_license ==> {license_type} Not found!!")
        return ""    
    
def append_tools_subscription_license(list_to_append, license_type):
    if any(license_type in s for s in pdlt.rtc_tools_license_subscription_types):
        dev_license = f"{license_type} - Subscription"
        if 'Partner' in dev_license or 'Dongle' in dev_license : dev_license='Single-User License - Subscription'
        list_to_append.append(dev_license)
        return dev_license
    else:
        print_debug(f"append_tools_subscription_license ==> {license_type} Not found!!")
        return ""    
        
def append_rtc_service_porting(list_to_append):
    list_to_append.append("BSP - standard µC")
    return 'BSP - standard µC'
    
def append_rtc_service_qualification(list_to_append):    
    list_to_append.append("QP")
    list_to_append.append("Qualification Package")
    list_to_append.append("Qualification Package - Safety Approval")
    
def append_rtc_startup_packages(list_to_append):
    list_to_append.append("IP")
    return 'IP'
    
def append_rtc_lts_maintenance(list_to_append,license_type):
    
    if license_type:
        if license_type != "Evaluation License" and license_type != "Concept License":
            lts_license = f"Long Term Stable Maintenance for {license_type}"
            list_to_append.append(lts_license)
            return lts_license
        else:
            return "N/A"
        
    list_to_append.append('Long Term Stable Maintenance - Subscription')
    return 'Long Term Stable Maintenance - Subscription'
    
def append_rtc_cybersecurity(list_to_append,license_type):
    
    if license_type:
        if license_type != "Evaluation License" and license_type != "Concept License":
            cyber_license = f"Cybersecurity Monitoring for {license_type}"
            list_to_append.append(cyber_license)
            return cyber_license
        else:
            return "N/A"
            
    list_to_append.append('Cybersecurity Maintenance - Subscription')
    return 'Cybersecurity Maintenance - Subscription'
    
# ======================
# 🔹 Search function
# ======================
    
def db_find_product_items(product_items = test_product_items, 
                          license_types_to_search = test_license_type,
                          price_list = db_sf_conv.pricelist_regions[2],
                          sf_ids: bool = True):
    
    col_index  = load_json_file(DB_COL_INDEX)
    
    conn = sqlite.connect(DB_FILE_PATH)
    cur = conn.cursor()
    cur.execute(f"PRAGMA key = '{appSecurity.db_sql_pricelist_pwd}'")
    
    table = []
    
    grp_number = 0
    items_found = []
    items_not_found = []
    for license_type in license_types_to_search:
        grp_number = grp_number + 1
        for item in product_items:
            search_key = f"{item.lower()}|{license_type.lower()}|{price_list.lower()}"

            cur.execute(f"SELECT * FROM {DB_TABLE_NAME} WHERE key = \"{search_key}\"")

            row = cur.fetchone()

            if row:
                
                if sf_ids:
                    rowRes = [None]*dbpl_if.TABLE_SIZE
                    rowRes[dbpl_if.TABLE_IDX_SF_PRICE_BOOK]        = row[col_index["pricebook2"]]
                    rowRes[dbpl_if.TABLE_IDX_SF_PRODUCT_ID]        = row[col_index["Product2Id"]]
                    rowRes[dbpl_if.TABLE_IDX_SF_PRICE_BOOK_ENTRY]  = row[col_index["PricebookEntryId"]]
                    rowRes[dbpl_if.TABLE_IDX_LICENSE_TYPE_ID]      = row[col_index["LicenseTypeId"]]
                else:
                    rowRes = [None]*(dbpl_if.TABLE_SIZE - 4)
                    
                rowRes[dbpl_if.TABLE_IDX_MAJOR_VERSION_NAME]       = row[col_index["Major_Version_Name"]]
                rowRes[dbpl_if.TABLE_IDX_PRODUCT_NAME]             = row[col_index["Product_Name"]]
                rowRes[dbpl_if.TABLE_IDX_PRODUCT_ITEM_NAME]        = row[col_index["Product_Item_Name"]]
                rowRes[dbpl_if.TABLE_IDX_PRODUCT_ITEM_DESCRIPTION] = row[col_index["Product_Item_Description"]]
                rowRes[dbpl_if.TABLE_IDX_PRICELIST]                = row[col_index["Pricelist"]]
                rowRes[dbpl_if.TABLE_IDX_ARTICLE_NUMBER]           = row[col_index["Article_Number"]]
                rowRes[dbpl_if.TABLE_IDX_LICENSE_TYPE_NAME]        = row[col_index["License_Type_Name"]]
                rowRes[dbpl_if.TABLE_IDX_AAV_CURRENCY]             = row[col_index["AAVCurrencyID"]]
                rowRes[dbpl_if.TABLE_IDX_QUANTITY]                 = 1
                rowRes[dbpl_if.TABLE_IDX_UNIT_PRICE]               = row[col_index["Price"]]
                rowRes[dbpl_if.TABLE_IDX_VALID_DATE]               = row[col_index["ValidFrom"]]
                rowRes[dbpl_if.TABLE_IDX_SALES_REGION]             = row[col_index["SalesRegion"]]
                rowRes[dbpl_if.TABLE_IDX_PRODUCT_GROUP_ID]         = str(grp_number)
                
                table.append(rowRes)
                
                if item not in items_found:
                    items_found.append(item)
                    #logger_debug(f"[DB_PRICE_LIST] item {item} article found for {license_type} and {price_list} search_key={search_key}")
            #else:
                #logger_debug(f"[DB_PRICE_LIST] For item {item} no article found for {license_type} and {price_list} search_key={search_key}")
    
    conn.close()
        
    for item in product_items:
        if item not in items_found:
            logger_debug(f"[DB_PRICE_LIST] ⚠️ For item {item} no article found for {price_list}")
            items_not_found.append(item)
        
    header_icons = [
        "🧱 Product Family",           # famille / bloc
        "🏷️ Product Name",             # étiquette / nom
        "🧬 Product Item Name",        # ADN / détail d’article
        "ℹ️ Product Item Description", # ADN / détail d’article
        "📜 Price List",               # liste / prix
        "🧩 Article Number",           # pièce / numéro d’article
        "🛠️ License Type",             # outils / type de licence
        "💱 Currency",                 # devise / monnaie
        "🔢 Quantity",
        "💰 Unit Price",               # argent / prix
        "📅 Valid From",               # calendrier / date de validité
        "🌍 Sales Region",        
        "🗂️ License Group Number"      # dossier / groupe de licence
    ]
    
    header_simple = [
        "Product Family",
        "Product Name",
        "Product Item Name",
        "Product Item Description",
        "Price List",
        "Article Number",
        "License Type",
        "Currency",
        "Quantity",
        "Unit Price",
        "Valid From",
        "Sales Region",        
        "License Group Number"
    ]
    
    if sf_ids:
        header_icons.append("pricebook2")
        header_icons.append("Product2Id")
        header_icons.append("PricebookEntryId")
        header_icons.append("LicenseTypeId")
        
        header_simple.append("pricebook2")
        header_simple.append("Product2Id")
        header_simple.append("PricebookEntryId")
        header_simple.append("LicenseTypeId")
        
        
    return table, header_icons, header_simple, items_not_found

def is_license_type_perpetual(license_type_data):
    licenseDuration = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_LICENSE_DURATION]
    return True if licenseDuration in ['perpetual'] else False

def is_license_type_subscription(license_type_data):
    licenseDuration = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_LICENSE_DURATION]
    return True if licenseDuration not in ['perpetual'] else False
    
def is_license_type_one_time_payment(license_type_data):
    paymentModel = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PAYMENT_MODEL]
    return True if paymentModel in ['One-time payment'] else False
    
def is_license_type_for_platformService(license_type_data):
    profile = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PROFILE]
    return True if profile not in ['License','Training','Hardware'] else False

def is_license_type_for_integration(license_type_data):
    profile = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PROFILE]
    return True if profile in ['Porting','Integration Package'] else False

def is_license_type_for_qualification(license_type_data):
    profile = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PROFILE]
    return True if profile in ['Qualification Package'] else False
    
def is_license_type_for_production(license_type_data):
    profile       = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PROFILE]
    perpetual     = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PERPETUAL]
    grantofrights = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_GRANT_OF_RIGHTS]
    return True if profile in ['License'] and perpetual == 1 and grantofrights == 'Reproduction and Distribution License' else False

def is_license_type_for_maintenance(license_type_data):
    profile        = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PROFILE]
    perpetual      = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PERPETUAL]
    grantofrights  = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_GRANT_OF_RIGHTS]
    license_method = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_LICENSE_METHOD]
    
    return True if profile in ['License'] and perpetual == 0 and grantofrights == 'n/a' and license_method == 'no technical license protection' else False
    
def is_license_type_for_tooling(license_type_data):
    profile       = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PROFILE]
    grantofrights = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_GRANT_OF_RIGHTS]
    return True if profile in ['License'] and grantofrights == 'Elektrobit Tooling Licence' else False

def is_license_type_for_tooling_maintenance(license_type_data):
    profile        = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PROFILE]
    perpetual      = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_PERPETUAL]
    grantofrights  = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_GRANT_OF_RIGHTS]
    license_method = license_type_data[dbpl_if.TABLE_LICENSE_TYPE_IDX_LICENSE_METHOD]
    return True if profile in ['License'] and perpetual == 0 and grantofrights == 'n/a' and license_method == 'FlexNet Publisher Application Activation Code' else False
    
def db_find_license_types(license_types_to_search = test_license_type):
    
    col_index  = load_json_file(DB_LICENSE_TYPES_COL_INDEX)
    
    conn = sqlite.connect(DB_LICENSE_TYPES_FILE_PATH)
    cur = conn.cursor()
    cur.execute(f"PRAGMA key = '{appSecurity.db_sql_pricelist_pwd}'")
    
    dict_licenses = {}
        
    items_found = []
    items_not_found = []
    
    for license_type in license_types_to_search:

        if LICENSE_TYPE_QUALIFIED not in license_type:
            search_key = f"{LICENSE_TYPE_QUALIFIED.lower()}|{license_type.lower()}"
        else:
            search_key = license_type.lower()
            
        if license_type in dict_licenses:
            continue
            
        cur.execute(f"SELECT * FROM {DB_LICENSE_TYPES_TABLE_NAME} WHERE key = \"{search_key}\"")

        row = cur.fetchone()
        rosRes = []

        if row:
            
            rowRes = [None]*dbpl_if.TABLE_LICENSE_TYPE_SIZE
                
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_CODE]                   = row[col_index["Code"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_NAME]                   = row[col_index["Name"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_DESCRIPTION]            = row[col_index["Description"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_LICENSE_DURATION]       = row[col_index["LicenseDuration"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_MAINTENANCE_DURATION]   = row[col_index["MaintenanceDuration"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_EXPECTED_DELIVERY_TIME] = row[col_index["ExpectedDeliveryTime"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_PAYMENT_MODEL]          = row[col_index["PaymentModel"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_EXPECTED_INVOICE_DATE]  = row[col_index["ExpectedInvoiceDate"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_GRANT_OF_RIGHTS]        = row[col_index["GrantOfRights"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_PROFILE]                = row[col_index["Profile"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_LICENSE_METHOD]         = row[col_index["LicenseMethod"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_PERPETUAL]              = row[col_index["Perpetual"]]
            rowRes[dbpl_if.TABLE_LICENSE_TYPE_IDX_UPDATE_RIGHT]           = row[col_index["UpdateRight"]]
            
            #table.append(rowRes)
            dict_licenses[license_type]=rowRes
            
            if license_type not in items_found:
                items_found.append(license_type)
                #logger_debug(f"[DB_PRICE_LIST] item {item} article found for {license_type} and {price_list} search_key={search_key}")
        else:
            if license_type not in items_not_found:
                logger_debug(f"[DB_PRICE_LIST] ⚠️ {license_type} not found for search_key={search_key}")
                items_not_found.append(license_type)
    
        
    conn.close()
        
    header_icons = [
        "🧱 Code",                     # structure / identifiant technique
        "🏷️ License Name",             # nom / étiquette
        "📝 Description",              # description fonctionnelle (plus clair que ADN)
        "⏳ License Duration",          # durée (temps)
        "📜 Maintenance Duration",     # contrat / maintenance
        "🚚 Expected Delivery Time",   # livraison / délai
        "🛠️ Payment Model",            # modèle commercial
        "🧾 Expected Invoice Date",    # facturation (plus précis que devise)
        "🔐 Grant Of Rights",           # droits / licence (sécurité)
        "💼 Profile",                  # profil de licence (business / scope)
        "📅 License Method",            # méthode / mode de licence
        "♾️ Perpetual",                 # perpétuel (symbole standard)
        "🔄 Update Right"               # droit de mise à jour
    ]
    
    header_simple = [
        "Code",
        "License Name",
        "Description",
        "License Duration",
        "Maintenance Duration",
        "Expected Delivery Time",
        "Payment Model",
        "Expected Invoice Date",
        "Grant Of Rights",
        "Profile",
        "License Method",
        "Perpetual",        
        "Update Right"
    ]
        
    return dict_licenses, header_icons, header_simple, items_not_found

def get_pricelist_region_and_currency(company_group_name,company_brand_name,company_name,company_currency,ai_quote_currenty):
    
    conti_pricelist = False
    
    if CONTINETNAL_GROUP_NAME in company_group_name:
        conti_pricelist = True
        pricelist_region = db_sf_conv.pricelist_regions[4]
        if ai_quote_currenty != 'EUR':
            print_debug(f"[DB_PRICE_LIST] ❌ Currency '{ai_quote_currenty}' not correct for {company_name}/{company_brand_name} so change to 'EUR'")
            ai_quote_currenty = 'EUR'
    else:   
        pricelist_region = db_sf_conv.sales_regions_to_pricelist_regions.get(ai_quote_currenty,'')
        
        if pricelist_region is None or pricelist_region == '':
            print_debug(f"[DB_PRICE_LIST] ❌ No pricelist region with currency '{ai_quote_currenty}' so change region according to account's currency")
            pricelist_region = db_sf_conv.currency_iso_code_to_pricelist_regions[company_currency]
            
    return pricelist_region, ai_quote_currenty, conti_pricelist
    
# ======================
# 🔹 DB creation
# ======================

schema = {
    "id": "INTEGER",
    "nom": "TEXT",
    "date_creation": "DATE",
    "montant": "REAL"
}

csv_pricelist_schema_to_sql = {
    "Major_Version_Name"       : "TEXT",
    "Product_Name"             : "TEXT",
    "Product_Item_Name"        : "TEXT",
    "Product_Item_Description" : "TEXT",
    "Pricelist"                : "TEXT",
    "Article_Number"           : "TEXT",
    "License_Type_Name"        : "TEXT",
    "AAVCurrencyID"            : "TEXT",
    "Price"                    : "REAL",
    "ValidFrom"                : "DATE",    
    "Remark"                   : "TEXT",
    "pricelist_validity"       : "TEXT"
}
    
csv_license_types_schema_to_sql = {
    'key'                          : "TEXT" ,
    'Qualified_for_pricelist_2024' : "TEXT" ,
    'Code'                         : "INTEGER",
    'Name'                         : "TEXT",
	'Description'                  : "TEXT",
	'LicenseDuration'              : "TEXT",
	'MaintenanceDuration'          : "TEXT",
    'ExpectedDeliveryTime'         : "TEXT",
    'PaymentModel'                 : "TEXT",	
    'ExpectedInvoiceDate'          : "TEXT",
    'GrantOfRights'                : "TEXT",
	'Profile'                      : "TEXT",
    'MandatoryOptional_ID'         : "TEXT",
	'LicenseMethod'                : "TEXT",
    'Cost_Center'                  : "INTEGER",
	'Discount_Rate'                : "REAL",
    'Operational_Profit_Rate'      : "REAL",
	'OperationalProfitType'        : "TEXT",
    'Perpetual'                    : "INTEGER",
    'Support_Hours_Amount'         : "TEXT",
	'UpdateRight'                  : "TEXT",
	'Apply_Withholding_Tax'        : "INTEGER"
}
    
def csv_to_sqlcipher(csv_file, db_file, db_col_idx_file, table_name, schema, password,drop_table=True,license_types_mode = False):
    
    logger_debug(f"[DB_PRICE_LIST] Creation of SQL db '{file_name(db_file)}' with table '{table_name}' from CSV file '{file_name(csv_file)}'")
    
    df = pd.read_csv(csv_file, sep=";", encoding="utf-8",keep_default_na=False)#na_values=["NA", "NaN", "#N/A"])
    
    df.columns = df.columns.str.replace(">= ", "")    
    df.columns = df.columns.str.replace(" ", "_")

    if not license_types_mode:
        
        cols = ["Product_Item_Name", "License_Type_Name", "Pricelist"]
        df[cols] = df[cols].apply(lambda s: s.astype(str).str.strip())
        
        df["CurrencyIsoCode"]  = df["Pricelist"].map(db_sf_conv.pricelist_regions_to_currency_iso_code)
        df["CurrencySymbole"]  = df["CurrencyIsoCode"].map(db_sf_conv.currency_iso_code_to_symbole)
        df["SalesRegion"]      = df["Pricelist"].map(db_sf_conv.pricelist_regions_to_sales_regions)
        df["pricebook2"]       = None
        df["Product2Id"]       = None
        df["PricebookEntryId"] = None
        df["LicenseTypeId"]    = (
            str(LICENSE_TYPE_QUALIFIED).lower() + "|"
            + df["License_Type_Name"].str.lower()
        )

        df["key"] = (
            df["Product_Item_Name"].str.lower()
            + "|"
            + df["License_Type_Name"].str.lower()
            + "|"
            + df["Pricelist"].str.lower()
        )
        
        schema = {**schema, "key"              : "TEXT"}
        schema = {**schema, "CurrencyIsoCode"  : "TEXT"}
        schema = {**schema, "CurrencySymbole"  : "TEXT"}
        schema = {**schema, "SalesRegion"      : "TEXT"}
        schema = {**schema, "pricebook2"       : "TEXT"}
        schema = {**schema, "Product2Id"       : "TEXT"}
        schema = {**schema, "PricebookEntryId" : "TEXT"}
        schema = {**schema, "LicenseTypeId"    : "TEXT"}
    else:
        cols = ["Qualified_for_pricelist_2024", "Name"]
        df[cols] = df[cols].apply(lambda s: s.astype(str).str.strip())
        
        df["key"] = (
            df["Qualified_for_pricelist_2024"].str.lower()
            + "|"
            + df["Name"].str.lower()
        )
        
    logger_debug(f"[DB_PRICE_LIST] Columns in df for CSV file '{file_name(csv_file)}': \n{list(df.columns)}")

    # Check for duplicates
    duplicates = df[df["key"].duplicated(keep=False)]
    duplicates_csv_file = csv_file.replace(".csv", "_duplicates.csv")
    delete_file(duplicates_csv_file)
    
    if not duplicates.empty:
        #logger_debug(duplicates.drop(columns=["key"]))
        
        duplicates_sorted = duplicates.sort_values(by=duplicates.columns.tolist())
        duplicates_sorted.to_csv(duplicates_csv_file, sep=";", index=False)
        
        unique_keys = duplicates["key"].drop_duplicates()

        if license_types_mode:
            keys_expanded = (
                unique_keys
                .str.split("|", expand=True)
                .rename(columns={
                    0: "Qualified_for_pricelist_2024",
                    1: "Name"
                })
            )
        else:
            keys_expanded = (
                unique_keys
                .str.split("|", expand=True)
                .rename(columns={
                    0: "Product_Item_Name",
                    1: "License_Type_Name",
                    2: "Pricelist"
                })
            )

        keys_expanded_sorted = keys_expanded.sort_values(by=keys_expanded.columns.tolist())
            
        logger_debug(f"[DB_PRICE_LIST] ⚠️ Duplicate keys detected in {file_name(csv_file)} : \n{tabulate(keys_expanded_sorted, headers=keys_expanded_sorted.columns,tablefmt='tsv')}")
        logger_debug(f"[DB_PRICE_LIST] ⚠️ See file {duplicates_csv_file}")
        
        for col in keys_expanded_sorted.columns:
            logger_debug(f"[DB_PRICE_LIST] {col}:")
            for value in keys_expanded_sorted[col].drop_duplicates():
                logger_debug(f"[DB_PRICE_LIST]\t- {value}")
    
        # Remove duplicates (keep first occurrence)
        df = df.drop_duplicates(subset="key", keep="first")

        logger_debug(f"[DB_PRICE_LIST] ✅ Duplicates have been removed from the DataFrame built from '{file_name(csv_file)}'.")

    else:
        logger_debug(f"[DB_PRICE_LIST] ✅ No duplicate found in '{file_name(csv_file)}'.")

    
    if drop_table and os.path.exists(db_file):
        
        if not delete_file(db_file):
            logger_debug("[DB_PRICE_LIST] ❌ db deletion error")
            return
        
    logger_debug(f"[DB_PRICE_LIST] Creating SQL db '{file_name(db_file)}' with table '{table_name}' with df...")
    
    try:
        with sqlite.connect(db_file) as conn:
            cur = conn.cursor()

            cur.execute(f"PRAGMA key = '{password}'")
            
            cols = ", ".join(f"{col} {dtype}" for col, dtype in schema.items())

            cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({cols})")

            if drop_table:
                cur.execute(f"DELETE FROM {table_name}")

            conn.commit()

    except Exception as e:
        logger_debug("[DB_PRICE_LIST] ❌ DB error:", e)
        return
    
    placeholders = ", ".join(["?" for _ in schema])
    insert_sql = f"INSERT INTO {table_name} ({', '.join(schema.keys())}) VALUES ({placeholders})"

    for row in df[schema.keys()].itertuples(index=False, name=None):
        row = list(row)
        if not license_types_mode:
            for i, (col, dtype) in enumerate(schema.items()):
                if dtype in ("REAL", "FLOAT"):
                    val_str = str(row[i]).replace(",", "")
                    row[i] = float(val_str) if val_str not in ("Inquire", "", "nan") else 0.0
                    #row[i] = pd.to_numeric(row[i], errors="coerce")
                elif dtype in ("DATE", "DATETIME"):
                    row[i] = pd.to_datetime(row[i], errors="coerce").strftime('%Y-%m-%d')       
        cur.execute(insert_sql, row)

    cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_key ON {table_name}(key)")
    conn.commit()
    
    cur.execute(f"SELECT * FROM {table_name} LIMIT 1")
    col_names = [desc[0] for desc in cur.description]
    col_index_mapping = {name: idx for idx, name in enumerate(col_names)}

    save_json_to_file(col_index_mapping,db_col_idx_file)

    conn.close()
    
    logger_debug(f"[DB_PRICE_LIST] ✅ SQL db '{file_name(db_file)}' created with table '{table_name}' from CSV file '{file_name(csv_file)}'")
       
def sanity_check(db_file,table_name, password):

    conn = sqlite.connect(db_file)
    cur = conn.cursor()
    cur.execute(f"PRAGMA key = '{password}'")

    cur.execute(f"SELECT Product_Item_Name, Price, Product2Id FROM {table_name} WHERE Product_Item_Name = \"EB tresos 9 - Board Support Package MCAL\" AND Pricelist = \"Euro\" LIMIT 10")
    rows = cur.fetchall()

    for r in rows:
        print(r)

    conn.close()
    
def license_types_sanity_check(db_file,table_name, password):

    conn = sqlite.connect(db_file)
    cur = conn.cursor()
    cur.execute(f"PRAGMA key = '{password}'")

    cur.execute(f"SELECT Name, Description, PaymentModel FROM {table_name} WHERE key = \"{LICENSE_TYPE_QUALIFIED.lower()}|project license\" LIMIT 10")
    rows = cur.fetchall()

    for r in rows:
        print(r)

    conn.close()

def update_pricelist_with_sf_ids(db_file,table_name, password):

    from db_sales_force import db_sf_get_price_book, db_sf_get_product, db_sf_get_price_book_entry, PRODUCT_ITEMS_MAPPING_TO_SF_FILE_PATH
    
    product_items_mapping  = load_json_file(PRODUCT_ITEMS_MAPPING_TO_SF_FILE_PATH)
    
    conn = sqlite.connect(db_file)
    cur = conn.cursor()
    cur.execute(f"PRAGMA key = '{password}'")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_Product_Item_Name ON {table_name}(Product_Item_Name)")
    
    price_book    = db_sf_get_price_book()
    price_book_id = price_book[0]
    
    reverseDict = {}
    for key, values in db_sf_conv.sf_product_family_mapping_to_pricelist.items():
        for v in values:
            reverseDict[v] = key
    sf_product_ids = []
    warnings = []
    
    logger_debug("[DB_PRICE_LIST] Inserting SF products reference to SQL DB for pricelist step 1/2...")
        
    for k,v in product_items_mapping.items():
        cur.execute(f"SELECT key, Product_Item_Name, License_Type_Name, CurrencyIsoCode, Pricelist FROM {table_name} WHERE Product_Item_Name = '{v['Product_Item_Name']}'")
        rows = cur.fetchall()
        
        #logger_debug(f"[DB_PRICE_LIST] 🔍 {len(rows)} records have been found in SQL database for '{v['Product_Item_Name']}'")
        
        sf_product_name = v['sf_product_name']
        
        if '*' in sf_product_name:
            sf_product_name = sf_product_name[:-1]
            
        product_results = db_sf_get_product(sf_product_name,product_item_family = None, fields_to_select='*')
        product_name = v['Product_Item_Name']
        
        if not product_results:
            logger_debug(f"[DB_PRICE_LIST] ❌ Product not found in SF : '{product_name}' sf_product_name:'{sf_product_name}'")
            cur.execute(f"""
                UPDATE {table_name}
                SET pricebook2 = ?, Product2Id = ?, PricebookEntryId = ?
                WHERE Product_Item_Name = ?
            """, ("-1","-1", "-1", product_name))
            conn.commit()
            continue
            
        nb_sf_products = len(product_results)
        
        for item in rows:
            
            if item[4] != 'Euro':
                continue
                
            sf_family_required = reverseDict[item[2]]
            
            occ = sum(1 for sf_product in product_results if sf_product.get("Family") == sf_family_required)
            product2_id = -1
            if occ == 0:
                if nb_sf_products > 1:
                    error_msg = f"[DB_PRICE_LIST] ⚠️ item name '{sf_product_name}' license type '{item[2]}'  >> no product found for type '{sf_family_required}' use alternative..."
                    if error_msg not in warnings:
                        logger_debug(error_msg)
                        warnings.append(error_msg)
                        
                    if sf_family_required == 'Update Right':
                        sf_family_required = 'License'
                    else:
                        logger_debug(f"[DB_PRICE_LIST] Error no alternative for {sf_family_required}..")
                        
                    occ = sum(1 for sf_product in product_results if sf_product.get("Family") == sf_family_required)
                    
                    if occ == 0:
                        logger_debug(f"[DB_PRICE_LIST] ❌ item name '{sf_product_name}' license type '{item[2]}'  >> no product found for type '{sf_family_required}'")
                        for p in product_results:
                            logger_debug(p['Family'],p['Name'])
                    elif occ > 1:
                        if 'EB zoneo GatewayCore' == sf_product_name:
                            for p in product_results:
                                if 'EB zoneo GatewayCore <HW> - License' in p['Name'] and p['Family'] == sf_family_required:
                                    product2_id = p['sf_id']
                                    break
                            
                        if product2_id == -1:
                            logger_debug(f"[DB_PRICE_LIST] ❌ item name '{sf_product_name}' license type '{item[2]}' >> too several products found for type '{sf_family_required}'")
                            for p in product_results:
                                if p['Family'] == sf_family_required:
                                    logger_debug(p['Name'])
                    else:
                        for sf_product in product_results:
                            if sf_product.get("Family") == sf_family_required:
                                product2_id = sf_product['sf_id']
                else:
                    product2_id = product_results[0]['sf_id']
            elif occ > 1:
                cyber_license = 'Cyber' in item[2]
                for p in product_results:
                    if p['Family'] == sf_family_required:
                        if cyber_license and 'Cyber' in p['Name']:
                            product2_id = p['sf_id']
                            break
                        elif not cyber_license and 'Cyber' not in p['Name']:
                            product2_id = p['sf_id']
                            break
                if product2_id == -1 and 'EB zoneo GatewayCore <HW> - License' == sf_product_name:
                    for p in product_results:
                        if 'EB zoneo GatewayCore - License' in p['Name'] and p['Family'] == sf_family_required:
                            product2_id = p['sf_id']
                            break
                
                if product2_id == -1:
                    logger_debug(f"[DB_PRICE_LIST] ❌ item name '{sf_product_name}' license type '{item[2]}' >>  several products found for type '{sf_family_required}'")
                    for p in product_results:
                        if p['Family'] == sf_family_required:
                            logger_debug(p['Name'])
            else:
                for sf_product in product_results:
                    if sf_product.get("Family") == sf_family_required:
                        product2_id = sf_product['sf_id']
                
            cur.execute(f"""
                UPDATE {table_name}
                SET Product2Id = ?
                WHERE Product_Item_Name = ? AND License_Type_Name = ?
            """, (str(product2_id), product_name,item[2]))
            
            if product2_id not in sf_product_ids:
                sf_product_ids.append(product2_id)
    
    conn.commit()
    logger_debug("[DB_PRICE_LIST] 🤔🔍 Sanity check for SF product IDs...")
    cur.execute(f"SELECT key, Product_Item_Name, License_Type_Name, CurrencyIsoCode, Pricelist FROM {table_name} WHERE Product2Id = '-1' AND pricebook2 = '{price_book_id}'")
    rows = cur.fetchall()
    if rows:
        logger_debug(f"[DB_PRICE_LIST] ⚠️ Several records don't have SF Product2Id for all currencies!!")
        for item in rows:
            if item[4] != 'Euro':
                continue
            logger_debug(f"item= '{item[1]}' license= '{item[2]}' pricelist region= '{item[4]}'")
    else:
        logger_debug("[DB_PRICE_LIST] ✅ Sanity check for SF product passed!")    
        
    logger_debug("[DB_PRICE_LIST] 💾 Update with SF product IDs done !")
    logger_debug("[DB_PRICE_LIST] Inserting SF products reference to SQL DB for pricelist step 2/2...")
    
    for sf_product_id in sf_product_ids:
        for currency in db_sf_conv.pricelist_currencies:
            price_book_entry   = db_sf_get_price_book_entry(price_book_id,sf_product_id,currency,fields_to_select='*')
            pricebook_entry_id = -1
            
            if not price_book_entry:
                logger_debug(f"[DB_PRICE_LIST] ⚠️ PricebookEntry not found for product id {sf_product_id} in currency '{currency}'")
            elif len(price_book_entry) > 1:
                logger_debug(f"[DB_PRICE_LIST] ⚠️ PricebookEntry several matches for product id {sf_product_id} in currency '{currency}'!!")
            else:  
                pricebook_entry_id = price_book_entry[0]['sf_id']
    
            cur.execute(f"""
                UPDATE {table_name}
                SET pricebook2 = ?, PricebookEntryId = ?
                WHERE Product2Id = ? AND CurrencyIsoCode = ?
            """, (str(price_book_id),str(pricebook_entry_id),str(sf_product_id),currency ))
    
    conn.commit()

    logger_debug("[DB_PRICE_LIST] 🤔🔍 Sanity check for SF PricebookEntryId...")
    
    cur.execute(f"SELECT key, Product_Item_Name, License_Type_Name, CurrencyIsoCode, Pricelist FROM {table_name} WHERE Product2Id != '-1' AND PricebookEntryId = '-1'")
    rows = cur.fetchall()
    if rows:
        logger_debug(f"[DB_PRICE_LIST] ⚠️ Several records don't have SF PricebookEntryId!!")
        for item in rows:
            logger_debug(f"item= '{item[1]}' license= '{item[2]}' pricelist region= '{item[4]}'")
    else:
        logger_debug("[DB_PRICE_LIST] ✅ Sanity check for SF PricebookEntryId passed!")  
        
    logger_debug("[DB_PRICE_LIST] 💾 Update with SF PriceBookEntry IDs done !")

    conn.close()
    
    return 
 
# ======================
# 🔹 main
# ======================
    
def main(argv=None):
    import argparse
    
    from context_manager import set_client_context, NO_SECRET

    set_client_context(-1,NO_SECRET,logger_debug,logger_debug,logger_debug,logger_debug,None)
    
    parser = argparse.ArgumentParser(description="Create a SQLite database from scratch based on pricelist csv file. The local database is encrypted with a password defined into env file.")
    parser.add_argument('--pwd', default=None, help='pwd for decrypting secrets in env file')
    parser.add_argument('--skipCreation', action='store_true', help='Disable db creation')
    
    if not argv:
        args = parser.parse_args()
    else:
        args = parser.parse_args(argv)
    
    logger_debug(f"[DB_PRICE_LIST] updating SQLite database from file {CSV_FILE_PATH}...")
 
    appSecurity.set_env_security_variable(args.pwd)
    
    if not appSecurity.db_sql_pricelist_pwd:
        if not appSecurity.decrypt_credentials():
            if not args.pwd:
                logger_debug("[DB_PRICE_LIST] No pwd provided! use option --pwd")   
            return False

    csv_to_sqlcipher(CSV_LICENSE_TYPES_FILE_PATH, 
                     DB_LICENSE_TYPES_FILE_PATH,
                     DB_LICENSE_TYPES_COL_INDEX,
                     DB_LICENSE_TYPES_TABLE_NAME,
                     csv_license_types_schema_to_sql,
                     password=appSecurity.db_sql_pricelist_pwd,
                     license_types_mode = True)   
                         
    if not args.skipCreation:
        csv_to_sqlcipher(CSV_FILE_PATH, 
                         DB_FILE_PATH,
                         DB_COL_INDEX,
                         DB_TABLE_NAME,
                         csv_pricelist_schema_to_sql,
                         password=appSecurity.db_sql_pricelist_pwd)

        update_pricelist_with_sf_ids(DB_FILE_PATH,DB_TABLE_NAME,password=appSecurity.db_sql_pricelist_pwd)
    
    logger_debug("Short test 1")
    
    sanity_check(DB_FILE_PATH,DB_TABLE_NAME,password=appSecurity.db_sql_pricelist_pwd)
    
    license_types_sanity_check(DB_LICENSE_TYPES_FILE_PATH,DB_LICENSE_TYPES_TABLE_NAME,password=appSecurity.db_sql_pricelist_pwd)

    logger_debug("Short test 2")
    
    table, header_icons, header_simple, items_not_found = db_find_product_items()
    logger_debug(table)
    
    listLicenseTypesIds = []
    if table:
        print(dbpl_if.TABLE_IDX_LICENSE_TYPE_ID)
        for i in table:
            listLicenseTypesIds.append(i[dbpl_if.TABLE_IDX_LICENSE_TYPE_ID])
        dict_licenses, header_icons, header_simple, items_not_found = db_find_license_types(listLicenseTypesIds)
        for k, v in dict_licenses.items():
            logger_debug(k)
            logger_debug(v)
        if items_not_found:
            logger_debug("[DB_PRICE_LIST] License type not found for:")
            logger_debug(items_not_found)
    else:
        logger_debug("[DB_PRICE_LIST] ❌ Error no product items found for test 2!")
        
    print("It is advised to delete csv file for now.\nDo you confirm the deletion? \n(Y)es or (N)o.")
    response = sys.stdin.readline().strip()
    if not response or 'y' not in response.lower():
        print("No file deleted, don't let your csv file on your disk!")
    else:
        if delete_file(CSV_FILE_PATH):
            print(f"Input file {CSV_FILE_PATH} has been deleted !")
        else:
            print(f"Deletion error! Input file {CSV_FILE_PATH} still present !")

    return True

if __name__ == "__main__":
    main()
