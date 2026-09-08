#import sqlite3 as sqlite
from sqlcipher3 import dbapi2 as sqlite
from datetime import datetime, timedelta
from simple_salesforce import Salesforce, SalesforceMalformedRequest
import pandas as pd
import re
from utils.sf.sf_objects_description import load_objects
from tools import fuzzy_match, setup_logger, clean_dataframe_nan, module_dir, unix_path
from utility import print_main, print_debug, print_priceIndication, print_priceListExtract
import appSecurity

# ========================
# Consts
# ========================

MODULE_DIR = module_dir(__file__)

SF_LOGIN_URL  = "https://elektrobit--partial.sandbox.lightning.force.com"  # sandbox => test, prod => login

DB_FILE_PATH = unix_path(MODULE_DIR, 'databases','db_sf.db')
DB_COL_INDEX  = unix_path(MODULE_DIR, 'databases','.db_sf_index.json')

OBJECT_KEY_FIELDS = {
    "Account": ["Name", "BillingCountry", "BillingCity"],
    "Contact": ["Name", "Email"],
    "Opportunity": ["Name", "AccountId"]
}

PRODUCT_ITEMS_MAPPING_TO_SF_FILE_PATH = unix_path(MODULE_DIR, 'products','productItems_mapping_to_sf.json')

# ========================
# Global variables
# ========================

sf           = None
logger       = setup_logger()
logger_debug = logger.debug

# ========================
# SQLite Management
# ========================

def get_or_create_record(object_name, fields_dict):
    global sf, logger_debug
    
    try:
        key_fields = OBJECT_KEY_FIELDS.get(object_name)
        if not key_fields:
            raise ValueError(f"No key_fields defined for {object_name}")

        table_name = object_name.lower() + "s"

        # 1️⃣ Search SQLite cache
        conn = sqlite.connect(DB_FILE_PATH)
        cursor = conn.cursor()
        where_clause = " AND ".join(f"{k}=?" for k in key_fields)
        values = [fields_dict.get(k, "") for k in key_fields]
        cursor.execute(f"SELECT Id FROM {table_name} WHERE {where_clause} LIMIT 1", values)
        result = cursor.fetchone()
        if result:
            conn.close()
            return result[0]
        conn.close()

        # 2️⃣ Search Salesforce
        sf_object = getattr(sf, object_name)
        soql_conditions = " AND ".join(f"{k}='{fields_dict[k]}'" for k in key_fields)
        soql = f"SELECT Id FROM {object_name} WHERE {soql_conditions} LIMIT 1"
        sf_result = sf.query(soql)
        if sf_result["records"]:
            record_id = sf_result["records"][0]["Id"]
            fields_dict["Id"] = record_id
            fields_dict["LastUpdated"] = datetime.now()
            upsert_record_sqlite(table_name, fields_dict)
            return record_id

        # 3️⃣ Create in Salesforce
        new_record = sf_object.create(fields_dict)
        record_id = new_record["id"]
        fields_dict["Id"] = record_id
        fields_dict["LastUpdated"] = datetime.now()
        upsert_record_sqlite(table_name, fields_dict)
        return record_id

    except Exception as e:
        logger_debug(f"[DB_SF] ❌ Error in get_or_create_record for {object_name}: exception '{type(e).__name__}' raised with '{e}'")
        return None

    
########################################################

def db_sf_get_opportunities_with_lines_for_account(account_id):
    """
    Retourne toutes les opportunités d'un account avec leurs lignes (OpportunityLineItem).
    """
    query = """
    SELECT 
        o.sf_id AS opportunity_id,
        o.Name AS opportunity_name,
        o.Bid_Lead__c,
        o.StageName,
        o.CloseDate,
        o.Amount,
        o.Amount_EUR__c,
        o.AccountId AS account_id,
        o.Invoicing_Entity__c,
        u.sf_id AS bid_lead_id,
        u.Name AS bid_lead_name,        
        GROUP_CONCAT(oli.sf_id) AS line_ids,
        SUM(CASE WHEN p.Family = 'Engineering Service' THEN oli.Quantity ELSE 0 END) AS eng_serv_quantity,
        SUM(CASE WHEN p.Family = 'Engineering Service' THEN oli.TotalPrice ELSE 0 END) AS eng_serv_total,
        SUM(CASE WHEN p.Family = 'Engineering Service' THEN oli.Total_Price_in_EUR__c ELSE 0 END) AS eng_serv_total_eur,
        SUM(CASE WHEN p.Family = 'Hardware' THEN oli.Quantity ELSE 0 END) AS hw_quantity,
        SUM(CASE WHEN p.Family = 'Hardware' THEN oli.TotalPrice ELSE 0 END) AS hw_total,
        SUM(CASE WHEN p.Family = 'Hardware' THEN oli.Total_Price_in_EUR__c ELSE 0 END) AS hw_total_eur,
        SUM(CASE WHEN p.Family = 'License' THEN oli.Quantity ELSE 0 END) AS license_quantity,
        SUM(CASE WHEN p.Family = 'License' THEN oli.TotalPrice ELSE 0 END) AS license_total,
        SUM(CASE WHEN p.Family = 'License' THEN oli.Total_Price_in_EUR__c ELSE 0 END) AS license_total_eur,
        SUM(CASE WHEN p.Family = 'Maintenance' THEN oli.Quantity ELSE 0 END) AS maintenance_quantity,
        SUM(CASE WHEN p.Family = 'Maintenance' THEN oli.TotalPrice ELSE 0 END) AS maintenance_total,
        SUM(CASE WHEN p.Family = 'Maintenance' THEN oli.Total_Price_in_EUR__c ELSE 0 END) AS maintenance_total_eur,
        SUM(CASE WHEN p.Family = 'Update Right' THEN oli.Quantity ELSE 0 END) AS update_right_quantity,
        SUM(CASE WHEN p.Family = 'Update Right' THEN oli.TotalPrice ELSE 0 END) AS update_right_total,
        SUM(CASE WHEN p.Family = 'Update Right' THEN oli.Total_Price_in_EUR__c ELSE 0 END) AS update_right_total_eur,          
        GROUP_CONCAT(DISTINCT oli.Market_segment__c) AS markets,
        GROUP_CONCAT(DISTINCT oli.PI_PJ__c) AS pi_pj_list,
        GROUP_CONCAT(DISTINCT p.Name) AS products,
        GROUP_CONCAT(DISTINCT p.Family) AS product_families
    FROM opportunity o
    LEFT JOIN user u ON u.sf_id = o.Bid_Lead__c
    LEFT JOIN opportunitylineitem oli ON oli.OpportunityId = o.sf_id
    LEFT JOIN product2 p ON p.sf_id = oli.Product2Id
    WHERE o.AccountId = ?
    GROUP BY o.sf_id
    ORDER BY o.CloseDate DESC
    """

    rows = sql_execute_query(
        DB_FILE_PATH,
        query,
        password=appSecurity.db_sql_sf_pwd,
        params=(account_id,)
    )

    return rows

def db_sf_get_opportunities_for_contact(contact_id: str):
    query1 = """
        SELECT 
            o.sf_id AS opportunity_id,
            o.Name AS opportunity_name,
            o.StageName,
            o.CloseDate,
            o.Amount,
            o.Amount_EUR__c,
            c.sf_id AS contact_id,
            c.FirstName,
            c.LastName,
            c.Email
        FROM opportunity o
        JOIN opportunitycontactrole ocr ON o.sf_id = ocr.OpportunityId
        JOIN contact c ON c.sf_id = ocr.ContactId
        WHERE c.sf_id = ?
    """
    
    query2 = """
        SELECT 
            o.sf_id          AS opportunity_id,
            o.Name           AS opportunity_name,
            o.StageName,
            o.CloseDate,
            o.Amount,
            c.sf_id          AS contact_id,
            c.FirstName,
            c.LastName,
            c.Email,
            CASE 
                WHEN o.ContactId = c.sf_id THEN 'Primary'
                ELSE ocr.Role
            END              AS contact_role
        FROM opportunity o
        LEFT JOIN opportunitycontactrole ocr 
               ON o.sf_id = ocr.OpportunityId
        LEFT JOIN contact c 
               ON c.sf_id = COALESCE(ocr.ContactId, o.ContactId)
        WHERE c.sf_id = ?
    """
    query = """
        SELECT 
            o.sf_id          AS opportunity_id,
            o.Name           AS opportunity_name,
            o.StageName,
            o.CloseDate,
            o.Amount,
            o.Amount_EUR__c,
            c.sf_id          AS contact_id,
            c.FirstName,
            c.LastName,
            c.Email,
            GROUP_CONCAT(
                CASE 
                    WHEN o.ContactId = c.sf_id THEN 'Primary'
                    ELSE ocr.Role
                END, ', '
            ) AS contact_roles
        FROM opportunity o
        LEFT JOIN opportunitycontactrole ocr 
               ON o.sf_id = ocr.OpportunityId
        LEFT JOIN contact c 
               ON c.sf_id = COALESCE(ocr.ContactId, o.ContactId)
        WHERE c.sf_id = ?
        GROUP BY o.sf_id, c.sf_id
        ORDER BY o.CloseDate DESC, c.sf_id
    """
    
    rows = sql_execute_query(
        DB_FILE_PATH,
        query,
        password=appSecurity.db_sql_sf_pwd,
        params=(contact_id,)   # tuple avec un seul paramètre
    )

    return rows
  

def db_sf_create_new_contact_for_account(sf_account_obj):
    logger.warning("[DB_SF] db_sf_create_new_contact_for_account not yet implemented!!!")
    
def db_sf_create_new_account_and_contact():
    logger.warning("[DB_SF] db_sf_create_new_account_and_contact not yet implemented!!!")
    
def db_sf_get_accounts_by_ids(account_ids):
    return db_sf_get_objects_by_ids("Account",account_ids)

def db_sf_get_objects_by_ids(sf_object_name,object_ids):
    if not object_ids or not sf_object_name:
        return {}

    table = sf_object_name.lower()
    
    placeholders = ",".join("?" for _ in object_ids)
    query = f"SELECT * FROM {table} WHERE sf_id IN ({placeholders})"

    rows = sql_execute_query(
                            DB_FILE_PATH,
                            query,
                            password=appSecurity.db_sql_sf_pwd,
                            params=tuple(object_ids)
                            )

    return rows
    
def db_sf_get_accounts_by_ids_(account_ids):
    placeholders = ",".join("?" for _ in account_ids)
    query = f"SELECT sf_id, Name FROM account WHERE sf_id IN ({placeholders})"
    rows = sql_execute_query(DB_FILE_PATH, query, password=appSecurity.db_sql_sf_pwd, params=tuple(account_ids))
    
    return rows
    
def db_get_hyperlink(object):
    return f"{SF_LOGIN_URL}/lightning/r/{object}/"
    
def db_get_object_hyperlink(object,sf_id, link_text, icon):
    url = f"{SF_LOGIN_URL}/lightning/r/{object}/{sf_id}/view"
    link = f'<a href="{url}" target="_blank">{icon} {link_text}</a>'
    return link

def db_get_opportunity_hyperlink(sf_id, link_text,noIcon=False):
    return db_get_object_hyperlink("Opportunity",sf_id,link_text,'💼' if not noIcon else '')
    
def db_get_contact_hyperlink(sf_id, link_text,noIcon=False):
    return db_get_object_hyperlink("Contact",sf_id,link_text,'👤' if not noIcon else '')

def db_get_account_hyperlink(sf_id, link_text,noIcon=False):
    return db_get_object_hyperlink("Account",sf_id,link_text,'🏢' if not noIcon else '')
    
def sql_get_object_for_attribute(sf_object_name, attribute_name,attribute_value):
    table = sf_object_name.lower()
   
    query = f"SELECT * FROM {table} WHERE {attribute_name} = ?"
    
    record = sql_execute_query(DB_FILE_PATH,
                               query,
                               password=appSecurity.db_sql_sf_pwd,
                               params=(attribute_value,))
    return record
    
def sql_get_object_by_sf_id(sf_object_name, sf_id):
    return sql_get_object_for_attribute(sf_object_name=sf_object_name, attribute_name="sf_id",attribute_value=sf_id)
    
def db_sf_get_account_by_id(sf_id):
    return sql_get_object_by_sf_id("Account",sf_id)
        
def db_sf_get_all_records_for_obj(sf_object_name, select_cols=['Name']):
    table = sf_object_name.lower()
    
    if len(select_cols)>0:
        query = f"SELECT DISTINCT {', '.join(select_cols)} FROM {table} ORDER BY Name ASC"
    else:
        query = f"SELECT Name FROM {table} ORDER BY Name ASC"
    
    record_names = sql_execute_query(DB_FILE_PATH,
                                     query,
                                     password=appSecurity.db_sql_sf_pwd)
    
    return record_names

def db_sf_get_all_distinct_values_for_obj(sf_object_name,field_name, add_fields_name=None):
    table = sf_object_name.lower()

    fields = [field_name]

    if add_fields_name:
        if isinstance(add_fields_name, (list, tuple)):
            fields.extend(add_fields_name)
        else:
            fields.append(add_fields_name)

    fields_str = ", ".join(fields)

    query = f"""
        SELECT DISTINCT {fields_str}
        FROM {table}
        WHERE {field_name} IS NOT NULL
        ORDER BY {field_name} ASC
    """

    records = sql_execute_query(DB_FILE_PATH,
                                query,
                                password=appSecurity.db_sql_sf_pwd)
    
    return records

def db_sf_find_accounts(account_name=None, account_country=None, account_type=None):
    query = "SELECT * FROM account WHERE 1=1"
    params = []

    if account_name:
        query += " AND (Name LIKE ? OR Brand__c LIKE ?)"
        like = f"%{account_name}%"
        params.extend([like, like])        

    if account_country:
        query += " AND BillingCountry like ?"
        params.append(account_country)

    if account_type:
        query += " AND EB_Account_Type__c like ?"
        params.append(account_type)

    records = sql_execute_query(DB_FILE_PATH,
                                query,
                                password=appSecurity.db_sql_sf_pwd,
                                params=params)
    
    return records

def db_sf_get_account_names(sf_id = False):
    
    if sf_id:
        select_cols=['Name','sf_id']
    else:
        select_cols=[]
        
    return db_sf_get_all_records_for_obj("Account",select_cols=select_cols)

def db_sf_get_account_brands(sf_id = False):
    
    if sf_id:
        select_cols=['Brand__c','sf_id','Name']
    else:
        select_cols=['Brand__c']
        
    return db_sf_get_all_records_for_obj("Account",select_cols=select_cols)
    
def db_sf_get_account_distinct_brands():
    return db_sf_get_all_distinct_values_for_obj("Account","Brand__c")
    
def db_sf_get_account_distinct_countries():
    return db_sf_get_all_distinct_values_for_obj("Account","BillingCountry")

def db_sf_get_account_distinct_countries_isocode():
    return db_sf_get_all_distinct_values_for_obj("Account",field_name="BillingCountryCode", add_fields_name="BillingCountry")
    
def db_sf_get_account_distinct_types():
    return db_sf_get_all_distinct_values_for_obj("Account","EB_Account_Type__c")

def db_sf_find_contact_from_email(email):
    return sql_get_object_for_attribute("Contact",attribute_name="Email",attribute_value=email)
    
def db_sf_find_contact(contact_name, account_name=None, contact_country=None, account_country=None, brand_name=None):
    
    if not contact_name: return []
    
    parts = contact_name.split()
    params = []

    base_query = "SELECT c.* FROM contact c"
    
    if account_name or account_country or brand_name:
        base_query += " JOIN account a ON c.AccountId = a.sf_id"
    
    where_clauses = []

    # Conditions sur le nom du contact
    if len(parts) == 1:
        where_clauses.append("(c.FirstName LIKE ? OR c.LastName LIKE ? OR c.Name LIKE ?)")
        #where_clauses.append("(LOWER(c.FirstName) LIKE LOWER(?) OR LOWER(c.LastName) LIKE LOWER(?) OR LOWER(c.Name) LIKE LOWER(?))")
        like = f"%{parts[0]}%"
        params.extend([like, like, like])
    else:
        where_clauses.append(
            "((c.FirstName LIKE ? AND c.LastName LIKE ?) OR (c.FirstName LIKE ? AND c.LastName LIKE ?) OR c.Name LIKE ?)"
        )
        params.extend([f"%{parts[0]}%", f"%{parts[1]}%",
                       f"%{parts[1]}%", f"%{parts[0]}%",
                       f"%{contact_name}%"])
    
    # Condition sur le nom de l'account
    if account_name and not brand_name:
        where_clauses.append("a.Name LIKE ?")
        params.append(f"%{account_name}%")
    elif brand_name and not account_name:
        where_clauses.append("a.Brand__c LIKE ?")
        params.append(f"%{brand_name}%")
    elif account_name and brand_name:
        where_clauses.append("(a.Name LIKE ? OR a.Brand__c LIKE ?)")
        params.extend([f"%{account_name}%", f"%{brand_name}%"])
        
    # Condition sur le pays du contact
    if contact_country:
        where_clauses.append("(c.MailingCountry LIKE ? OR c.MailingCountryCode LIKE ?)")
        params.extend([f"%{contact_country}%", f"%{contact_country}%"])

    if account_country:
        where_clauses.append("(a.BillingCountry LIKE ? OR a.BillingCountryCode LIKE ?)")
        params.extend([f"%{account_country}%", f"%{account_country}%"])
    
    query = f"{base_query} WHERE {' AND '.join(where_clauses)}"

    records = sql_execute_query(DB_FILE_PATH,
                                query,
                                password=appSecurity.db_sql_sf_pwd,
                                params=params)
    return records
    
def db_sf_find_account_from_name_country(account_name, account_country=None):
    account_name_clean    = account_name.strip()
    account_country_clean = account_country.strip() if account_country else None

    # Tentative 1 : match nom + pays
    filtered = db_sf_find_accounts(account_name=account_name_clean,account_country=account_country_clean)

    # Si rien trouvé, essayer juste avec le nom
    if not filtered:
        filtered = db_sf_find_accounts(account_name=account_name_clean)

    return clean_dataframe_nan(filtered)
opp = None
def get_sf_opportunity(id: str):

    global opp
    
    logger = setup_logger()
    print_debug = logger.debug
    
    print_debug(f"get_sf_opportunity start")
    
    if opp and opp["Id"] == id: return opp
    
    try:
        sf = Salesforce(
                instance_url=SF_LOGIN_URL,
                username=appSecurity.sf_usr_name,
                password=appSecurity.sf_usr_pwd,
                security_token=appSecurity.sf_usr_token,
                domain='test'
            )
    except Exception as e:
        print_debug(f"❌ Error at SalesForce connection : exception '{type(e).__name__}' raised with '{e}'")
        return None
        
    try:
        opp     = sf.Opportunity.get(id)
        opp['Stage'] = {"options":['Opportunity','RFI/RFQ','Price Indication','Offer Sent','Short List','Negotiated','Lost','LOI / POI received','PO accepted']}
        print_debug(f"get_sf_opportunity got opp")
    except Exception as e:
        print_debug(f"❌ Error for getting opportunity details : exception '{type(e).__name__}' raised with '{e}'")
        opp = None
        return None     

    try:
        account = sf.Account.get(opp["AccountId"])
        opp["AccountName"] = account['Name']
        print_debug(f"get_sf_opportunity AccountName={opp['AccountName']}")
    except Exception as e:
        print_debug(f"❌ Error for getting opportunity details : exception '{type(e).__name__}' raised with '{e}'")
        opp["AccountName"] = None
        pass  
        
    try:
        owner   = sf.User.get(opp["OwnerId"]) 
        opp["OwnerName"]   = owner['Name']
        print_debug(f"get_sf_opportunity OwnerName={opp['OwnerName']}")
    except Exception as e:
        print_debug(f"❌ Error for getting opportunity details : exception '{type(e).__name__}' raised with '{e}'")
        opp["OwnerName"] = None
        pass     
        
    print_debug(f"get_sf_opportunity done with AccountName={opp['AccountName']} OwnerName={opp['OwnerName']}")
    return opp
    
def oldF():
    try:
        opp     = sf.Opportunity.get(id)
        account = sf.Account.get(opp["AccountId"])
        owner   = sf.User.get(opp["OwnerId"]) 
        opp["AccountName"] = account['Name']
        opp["OwnerName"]   = owner['Name']
        print(opp["AccountName"])
        print(opp["OwnerName"])
        print_debug(f"get_sf_opportunity AccountName={opp['AccountName']} OwnerName={opp['OwnerName']}")
    except Exception as e:
        print_debug(f"❌ Error for getting opportunity details : exception '{type(e).__name__}' raised with '{e}'")
        opp = None
        return None 


def build_opportunity_queryold(schema, root_object="Opportunity", account_name_filter=None):
    """
    Génère une requête SQL qui récupère un objet racine (Opportunity) et tous les objets liés présents dans le schema.
    """
    joins = []
    select_cols = []

    # Table racine
    root_table = root_object.lower()
    select_cols.append(f"{root_table}.sf_id AS {root_table}_id")
    select_cols.append(f"{root_table}.Name AS {root_table}_name")

    visited = set()
    visited.add(root_object)

    def add_joins(obj_name, parent_table, parent_id_col):
        """
        Parcours les references et enfants pour générer SELECT + JOIN
        """
        relationships = schema[obj_name].get("relationships", {})
        # references
        for ref in relationships.get("references", []):
            ref_obj = ref["object"]
            if ref_obj not in schema:
                continue  # objet non présent
            ref_table = ref_obj.lower()
            fk_col = ref["field"]
            alias = ref_table
            # ajouter select
            select_cols.append(f"{alias}.sf_id AS {alias}_id")
            select_cols.append(f"{alias}.Name AS {alias}_name")
            # ajouter join
            joins.append(f"LEFT JOIN {ref_table} {alias} ON {parent_table}.{fk_col} = {alias}.sf_id")
            if ref_obj not in visited:
                visited.add(ref_obj)
                add_joins(ref_obj, alias, "sf_id")

        # children
        for child in relationships.get("children", []):
            child_obj = child["object"]
            if child_obj not in schema:
                continue
            child_table = child_obj.lower()
            fk_col = child["field"]
            alias = child_table
            # select minimal, juste ID et Name
            select_cols.append(f"{alias}.sf_id AS {alias}_id")
            select_cols.append(f"{alias}.Name AS {alias}_name")
            joins.append(f"LEFT JOIN {child_table} {alias} ON {alias}.{fk_col} = {parent_table}.sf_id")
            if child_obj not in visited:
                visited.add(child_obj)
                add_joins(child_obj, alias, "sf_id")

    # initial call
    add_joins(root_object, root_table, "sf_id")

    # requête de base
    sql = f"SELECT {', '.join(select_cols)} FROM {root_table}"
    if joins:
        sql += " " + " ".join(joins)

    # filtre sur Account si demandé
    if account_name_filter:
        sql += f" JOIN account a ON {root_table}.AccountId = a.sf_id WHERE a.Name LIKE '%{account_name_filter}%'"

    sql += f" ORDER BY {root_table}.sf_id"

    return sql


def build_opportunity_queryold2(schema, root_object="Opportunity", account_name_filter=None):
    """
    Génère une requête SQL pour récupérer un objet racine (Opportunity) et tous les objets liés présents dans le schema.
    Les colonnes et les JOIN utilisent des alias pour éviter les conflits.
    """
    joins = []
    select_cols = []

    # Table racine
    root_table = root_object.lower()
    root_alias = "r"  # alias racine
    select_cols.append(f"{root_alias}.sf_id AS {root_alias}_sf_id")
    select_cols.append(f"{root_alias}.Name AS {root_alias}_name")

    visited = set()
    visited.add(root_object)

    def add_joins(obj_name, parent_alias):
        """
        Parcours les references et enfants pour générer SELECT + JOIN
        """
        relationships = schema[obj_name].get("relationships", {})

        # references
        for ref in relationships.get("references", []):
            ref_obj = ref["object"]
            if ref_obj not in schema:
                continue  # objet non présent
            ref_table = ref_obj.lower()
            ref_alias = f"{ref_table[:1]}_{len(visited)}"  # alias unique
            fk_col = ref["field"]
            # ajouter select minimal
            select_cols.append(f"{ref_alias}.sf_id AS {ref_alias}_sf_id")
            select_cols.append(f"{ref_alias}.Name AS {ref_alias}_name")
            # ajouter join
            joins.append(f"LEFT JOIN {ref_table} {ref_alias} ON {parent_alias}.{fk_col} = {ref_alias}.sf_id")
            if ref_obj not in visited:
                visited.add(ref_obj)
                add_joins(ref_obj, ref_alias)

        # children
        for child in relationships.get("children", []):
            child_obj = child["object"]
            if child_obj not in schema:
                continue
            child_table = child_obj.lower()
            child_alias = f"{child_table[:1]}_{len(visited)}"
            fk_col = child["field"]
            select_cols.append(f"{child_alias}.sf_id AS {child_alias}_sf_id")
            select_cols.append(f"{child_alias}.Name AS {child_alias}_name")

def build_opportunity_query(schema, root_object="Opportunity", account_name_filter=None):
    """
    Génère une requête SQL robuste pour récupérer un objet racine (root_object)
    et tous les objets liés présents dans le schema.
    """
    joins = []
    select_cols = []

    root_table = root_object.lower()
    root_alias = "r"

    visited = set()
    visited.add(root_object)
    alias_counter = {"count": 0}

    def get_alias(table_name):
        alias_counter["count"] += 1
        return f"{table_name[:1]}_{alias_counter['count']}"

    def add_joins(obj_name, parent_alias):
        relationships = schema[obj_name].get("relationships", {})
        obj_fields = [list(f.keys())[0] for f in schema[obj_name]["fields"]]

        # Ajouter les colonnes de base pour cet objet
        select_cols.append(f"{parent_alias}.sf_id AS {parent_alias}_sf_id")
        if "Name" in obj_fields:
            select_cols.append(f"{parent_alias}.Name AS {parent_alias}_name")

        # === REFERENCES ===
        for ref in relationships.get("references", []):
            ref_obj = ref["object"]
            fk_col = ref["field"]
            if ref_obj not in schema:
                continue
            ref_fields = [list(f.keys())[0] for f in schema[ref_obj]["fields"]]
            if fk_col not in obj_fields:
                continue  # le champ de la table parent n'existe pas
            ref_table = ref_obj.lower()
            ref_alias = get_alias(ref_table)

            # Colonnes à sélectionner
            select_cols.append(f"{ref_alias}.sf_id AS {ref_alias}_sf_id")
            if "Name" in ref_fields:
                select_cols.append(f"{ref_alias}.Name AS {ref_alias}_name")

            joins.append(f"LEFT JOIN {ref_table} {ref_alias} ON {parent_alias}.{fk_col} = {ref_alias}.sf_id")

            if ref_obj not in visited:
                visited.add(ref_obj)
                add_joins(ref_obj, ref_alias)

        # === CHILDREN ===
        for child in relationships.get("children", []):
            child_obj = child["object"]
            fk_col = child["field"]
            if child_obj not in schema:
                continue
            child_fields = [list(f.keys())[0] for f in schema[child_obj]["fields"]]
            if fk_col not in child_fields:
                continue
            child_table = child_obj.lower()
            child_alias = get_alias(child_table)

            select_cols.append(f"{child_alias}.sf_id AS {child_alias}_sf_id")
            if "Name" in child_fields:
                select_cols.append(f"{child_alias}.Name AS {child_alias}_name")

            joins.append(f"LEFT JOIN {child_table} {child_alias} ON {child_alias}.{fk_col} = {parent_alias}.sf_id")

            if child_obj not in visited:
                visited.add(child_obj)
                add_joins(child_obj, child_alias)

        # === POLYMORPHIC REFERENCES ===
        for pref in relationships.get("polymorphic_references", []):
            ref_obj = pref["object"]
            fk_col = pref["field"]
            if ref_obj not in schema:
                continue
            ref_fields = [list(f.keys())[0] for f in schema[ref_obj]["fields"]]
            if fk_col not in obj_fields:
                continue
            ref_table = ref_obj.lower()
            ref_alias = get_alias(ref_table)
            select_cols.append(f"{ref_alias}.sf_id AS {ref_alias}_sf_id")
            if "Name" in ref_fields:
                select_cols.append(f"{ref_alias}.Name AS {ref_alias}_name")
            joins.append(f"LEFT JOIN {ref_table} {ref_alias} ON {parent_alias}.{fk_col} = {ref_alias}.sf_id")
            if ref_obj not in visited:
                visited.add(ref_obj)
                add_joins(ref_obj, ref_alias)

    # Lancer le parcours récursif à partir de la racine
    add_joins(root_object, root_alias)

    # Construire la requête finale
    sql = f"SELECT {', '.join(select_cols)} FROM {root_object.lower()} {root_alias}"
    if joins:
        sql += " " + " ".join(joins)

    # Filtre optionnel sur Account
    if account_name_filter:
        sql += f" JOIN account a ON {root_alias}.AccountId = a.sf_id WHERE a.Name LIKE '%{account_name_filter}%'"

    sql += f" ORDER BY {root_alias}.sf_id"
    return sql

def sql_execute_query(db_file, query, password=None, params=None):
    """
    Exécute une requête SQL sur la base et renvoie le résultat sous forme de liste de dictionnaires.
    """
    conn = sqlite.connect(db_file)
    cur = conn.cursor()

    if password:
        cur.execute(f"PRAGMA key = '{password}'")

    if not params:
        cur.execute(query)
    else:
        cur.execute(query,params)
        
    columns = [desc[0] for desc in cur.description]  # noms des colonnes
    rows = cur.fetchall()

    if len(columns) == 1:
        return [row[0] for row in rows]
    else:
        return [dict(zip(columns, row)) for row in rows]

    conn.close()
    return result

def db_sf_get_price_book(fields: str = "sf_id"):
    
    price_book='Standard Price Book'

    query = f"""
    SELECT {fields}
    FROM pricebook2
    WHERE Name = '{price_book}'
    """    
    rows = sql_execute_query(DB_FILE_PATH, query, password=appSecurity.db_sql_sf_pwd)
    
    return rows
    
def db_sf_get_price_book_entry(priceBookId: str, product2Id: str, currency: str,fields_to_select: str = "sf_id", active_product_only: bool = False):

    query = f"""
    SELECT {fields_to_select}
    FROM PricebookEntry
    WHERE Pricebook2Id = '{priceBookId}'
      AND Product2Id = '{product2Id}'
      AND CurrencyIsoCode = '{currency}'
    """
    
    if active_product_only:
        query += "AND IsActive = '1'"    
        
    rows = sql_execute_query(DB_FILE_PATH, query, password=appSecurity.db_sql_sf_pwd)
    
    return rows

def db_sf_get_product(product_item_name: str, product_item_family: str = None,fields_to_select: str = "sf_id", active_product_only: bool = False):

    query = f"SELECT {fields_to_select} FROM Product2 WHERE Name LIKE '%{product_item_name}%'"
    
    if active_product_only:
        query += "AND IsActive = '1'"
        
    if product_item_family:
        query += f" AND Family = '{product_item_family}'"

    records = sql_execute_query(DB_FILE_PATH,
                                query,
                                password=appSecurity.db_sql_sf_pwd)
    
    return records
   
def main(argv=None):
    import argparse
    
    global sf
    
    from context_manager import set_client_context, NO_SECRET

    set_client_context(-1,NO_SECRET,logger_debug,logger_debug,logger_debug,logger_debug,None)
    
    parser = argparse.ArgumentParser(description="APIs for accessing and make queries to local SQLite dabtabase. The local database is encrypted with a password.")

    parser.add_argument('--pwd', default=None, help='pwd for decrypting secrets in env file')
    
    if not argv:
        args = parser.parse_args()
    else:
        args = parser.parse_args(argv)
    
    print("start query test")

    appSecurity.set_env_security_variable(args.pwd)
    
    if not appSecurity.sf_usr_name:
        if not appSecurity.decrypt_credentials():
            if args.pwd is None:
                logger_debug("[DB_SF] No pwd provided! use option --pwd")
            return
        
    print(db_sf_get_account_distinct_countries_isocode())
    
    res = db_sf_find_account_from_name_country('jLr')
    
    for r in res:
        print(r['Name'],r['sf_id'])
    
    result = db_sf_find_contact('stephen',account_name="JlR",account_country="gb",brand_name='JLr') #United Kingdom
    
    for r in result:
        print(r['Name'],r['MailingCountry'], r['AccountId'])
        account = db_sf_get_account_by_id(r['AccountId'])
        account = account[0]
        print(account['Name'],account['BillingCity'], account['BillingCountryCode'])
    
    
    accounts = db_sf_get_account_names(sf_id=True)
    
    accounts_brand = db_sf_get_account_brands(sf_id=True)
    
    #print(accounts_brand)

    company_name  = fuzzy_match(accounts,'JLR', all_best=True)
    
    company_brand = fuzzy_match(accounts_brand,'JLR', all_best=True,value_key='Brand__c',extra_key='sf_id',extra_key2='Name')

    print(company_name)
    print(company_brand) 
    print("\n")
    sql = """
    SELECT sf_id, Name, Market_segment__c, Domain__c, Description, Family, Revenue_Model__c, Major_Product_Version__c
    FROM Product2
    WHERE Major_Product_Version__c LIKE '%tresos%';
    """
    sql = """
    SELECT *
    FROM Product2
    """
    rows = sql_execute_query(DB_FILE_PATH, sql, password=appSecurity.db_sql_sf_pwd)
    #for r in rows:
    #    print(r)
    #return 
    print("\n")

    price_book='Standard Price Book'
    product_item_name = "EB tresos AutoCore Generic 8 Ethernet Package"
    product_item_family =  'License'
    currency = "EUR"
    price_book = db_sf_get_price_book()
    print("price book: ",price_book)
    product = db_sf_get_product(product_item_name,product_item_family)
    print("\nproduct item: ",product)
    price_book_entry = db_sf_get_price_book_entry(price_book[0],product[0],currency,fields='*')
    print("\nprice_book_entry : ",price_book_entry[0])
    
    return
    
    rows = db_sf_get_account_names()
    
    #print(rows)
    
    rows = db_sf_get_account_distinct_countries()
    
    #print(rows)
    
    #print(db_sf_get_account_distinct_types())
    
        
    sql = """
    SELECT o.sf_id AS opportunity_id,
           o.Name AS opportunity_name,
           a.sf_id AS account_id,
           a.Name AS account_name
    FROM opportunity o
    LEFT JOIN account a ON o.AccountId = a.sf_id
    ORDER BY o.sf_id
    """

    #rows = sql_execute_query(DB_FILE_PATH, sql, password=appSecurity.db_sql_sf_pwd)
    #for r in rows:
    #    print(r['opportunity_id'], r['opportunity_name'], r['account_name'])
    
    print("build query")
    #query = build_opportunity_query(schema, root_object="Opportunity", account_name_filter="Mobileye")
    account_name_filter = "mobileye"  # le nom à rechercher

    query = f"""
    SELECT o.sf_id AS opportunity_id,
           o.name AS opportunity_name,
           a.sf_id AS account_id,
           a.name AS account_name
    FROM opportunity o
    JOIN account a ON o.accountid = a.sf_id
    WHERE LOWER(a.name) LIKE LOWER('%mobileye%')
    ORDER BY o.sf_id
    """    
    print(query)
    rows = sql_execute_query(DB_FILE_PATH,query,password=appSecurity.db_sql_sf_pwd)
    for r in rows:
        print(r['opportunity_id'], r['opportunity_name'], r['account_name'])
        
    query = """
        SELECT p.picklist_id, p.picklist_name, p.restrictedPicklist, p.dependentPicklist
        FROM picklists p
        WHERE p.object_name = 'Account'
        ORDER BY p.picklist_name
    """
    picklists = sql_execute_query(DB_FILE_PATH,query,password=appSecurity.db_sql_sf_pwd)

    print(picklists)
    print("db_sf_get_opportunities_for_contact")
    rows = db_sf_get_opportunities_for_contact('003Sd000005LT7OIAW')#0037T00000LxOkDQAV')
    for r in rows:
        print(r['opportunity_id'], r['opportunity_name'])
        
    print("db_sf_get_opportunities_with_lines_for_account")
    rows = db_sf_get_opportunities_with_lines_for_account('001D000000jjHiGIAU')
    for r in rows:
        print(r['opportunity_id'], r['opportunity_name'], r['Market_segment__c'])        
        
    query = "PRAGMA table_info(account);"
    rows = sql_execute_query(DB_FILE_PATH,query,password=appSecurity.db_sql_sf_pwd)
    for row in rows:
        print(row)
        
if __name__ == "__main__":       
    main()


if __name__ == "__tobedeleted__":
    db_sf_find_contact_by_name_and_account()
##
##
##

def db_sf_find_contact_by_name_and_account(contact_name, account_name=None):
    parts = contact_name.split()
    params = []

    base_query = "SELECT c.* FROM contact c"
    
    if account_name:
        base_query += " JOIN account a ON c.AccountId = a.sf_id"
    
    where_clauses = []

    if len(parts) == 1:
        where_clauses.append("(c.FirstName LIKE ? OR c.LastName LIKE ? OR c.Name LIKE ?)")
        like = f"%{parts[0]}%"
        params.extend([like, like, like])
    else:
        where_clauses.append(
            "((c.FirstName LIKE ? AND c.LastName LIKE ?) OR (c.FirstName LIKE ? AND c.LastName LIKE ?) OR c.Name LIKE ?)"
        )
        params.extend([f"%{parts[0]}%", f"%{parts[1]}%",
                       f"%{parts[1]}%", f"%{parts[0]}%",
                       f"%{contact_name}%"])
    
    if account_name:
        where_clauses.append("a.Name LIKE ?")
        params.append(f"%{account_name}%")
    
    query = f"{base_query} WHERE {' AND '.join(where_clauses)}"
    
    records = sql_execute_query(DB_FILE_PATH,
                                query,
                                password=appSecurity.db_sql_sf_pwd,
                                params=params)
    return records
    
def db_sf_find_contact_by_name(name):
    parts = name.split()
    if len(parts) == 1:
        query = """
            SELECT * FROM contact
            WHERE FirstName LIKE ? OR LastName LIKE ? OR Name LIKE ?
        """
        like   = f"%{parts[0]}%"
        params = (like, like, like)
    else:
        query = """
            SELECT * FROM contact
            WHERE (FirstName LIKE ? AND LastName LIKE ?)
               OR (FirstName LIKE ? AND LastName LIKE ?)
               OR Name LIKE ?
        """
        params = (f"%{parts[0]}%", f"%{parts[1]}%",
                  f"%{parts[1]}%", f"%{parts[0]}%",
                  f"%{name}%")
        
    records = sql_execute_query(DB_FILE_PATH,
                                query,
                                password=appSecurity.db_sql_sf_pwd,
                                params=params)        
    return records