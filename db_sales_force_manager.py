import os
#import sqlite3 as sqlite
from sqlcipher3 import dbapi2 as sqlite
from datetime import datetime, timedelta
from simple_salesforce import Salesforce, SalesforceMalformedRequest
import pandas as pd
import re
from utils.sf.sf_schema_generation import SF_PREFERRED_OBJECTS_FILE_PATH
from utils.sf.sf_objects_description import load_objects
from tools import setup_logger, clean_dataframe_nan, unix_path,module_dir,delete_file, save_json_to_file,normalize_date_iso, end_of_month_plus_n_days, compute_first_delivery_date
import appSecurity
import db_price_list_if as dbpl_if

# ========================
# Consts
# ========================

MODULE_DIR = module_dir(__file__)

SF_LOGIN_URL  = "https://elektrobit--partial.sandbox.lightning.force.com/"  # sandbox => test, prod => login

DB_FILE_PATH = unix_path(MODULE_DIR, 'databases','db_sf.db')
DB_COL_INDEX = unix_path(MODULE_DIR, 'databases','.db_sf_index.json')
DB_SF_DICT   = unix_path(MODULE_DIR, 'databases','.db_sf_dict.json')

OBJECT_KEY_FIELDS = {
    "Account": ["Name", "BillingCountry", "BillingCity"],
    "Contact": ["Name", "Email"],
    "Opportunity": ["Name", "AccountId"]
}

DEFAULT_OPP_PROBABILITY = '10'

# ========================
# Global variables
# ========================

sf           = None
logger       = setup_logger()
logger_debug = logger.debug
sf_dict_list ={}

# ========================
# SQLite Management
# ========================
    
########################################################

def build_sql_database(db_file, password,schema):

    if not delete_file(db_file):
        logger_debug("[DB_SF_MANAGER] ❌ db deletion error")
        return
    
    conn = sqlite.connect(db_file)
    cur = conn.cursor()
    
    conn.isolation_level = None
    
    cur.execute(f"PRAGMA key = '{password}'")

    # PRAGMA fast import
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=OFF")
    cur.execute("PRAGMA temp_store=MEMORY")
    cur.execute("PRAGMA cache_size=-2000")

    # Table creation for picklist
    create_sql = f"""    
    CREATE TABLE IF NOT EXISTS picklists (
        picklist_id TEXT PRIMARY KEY,
        picklist_name TEXT,
        object_name TEXT,
        restrictedPicklist BOOLEAN,
        dependentPicklist BOOLEAN
    );
    """
    cur.execute(create_sql)
    create_sql = f"""  
    CREATE TABLE IF NOT EXISTS picklist_values (
        value_id TEXT PRIMARY KEY,
        picklist_id TEXT,
        value TEXT,
        label TEXT,
        active BOOLEAN,
        FOREIGN KEY(picklist_id) REFERENCES picklists(picklist_id)
    );
    """
    cur.execute(create_sql)
    
    for sf_object in schema.keys():
        create_table_from_schema(cur,sf_object,schema)
        logger_debug(f"[DB_SF_MANAGER] ✅ Table created for {sf_object.lower()}")

    insert_picklists(cur,schema)
    
    # Index creation after insertion
    #cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sf_id ON opportunity(sf_id)")
    #cur.execute("CREATE INDEX IF NOT EXISTS idx_key ON opportunity(key)")
    #cur.execute("CREATE INDEX IF NOT EXISTS idx_account_date ON opportunity(account_id, close_date)")
    #conn.commit()

    # PRAGMA put back
    cur.execute("PRAGMA synchronous=NORMAL")
    conn.commit()
    conn.close()
    
def create_table_from_schema(cur, object_name, schema):
    fields = schema[object_name]["fields"]
    relationships = schema[object_name].get("relationships", {})
    references = relationships.get("references", []) + relationships.get("parents", [])
    
    columns = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    fk_constraints = []
    
    for field in fields:
        name, props    = list(field.items())[0]
        sql_type       = props["sqlType"]
        sf_obj_type    = props["type"]
        picklistValues = props.get("picklistValues", [])
        picklist_id    = props.get("picklist_id")
        
        if name == "Id":  # Salesforce Id
            col_def = f"sf_id {sql_type} UNIQUE"
        elif sf_obj_type == "picklist" and picklist_id:
            col_def = f"{name} {sql_type}"
            #col_def = f"FOREIGN KEY({name}) REFERENCES picklist_values(value_id)"
            fk_constraints.append(f"FOREIGN KEY({name}) REFERENCES picklist_values(value)")            
        else:
            col_def = f"{name} {sql_type}"
            
        ref = next((r for r in references if r["field"] == name), None)
        if ref and ref["object"] in schema:  
            #col_def += f' REFERENCES {ref["object"]}(sf_id)'
            fk_constraints.append(f"FOREIGN KEY({name}) REFERENCES {ref['object'].lower()}(sf_id)")
            
        columns.append(col_def)

    columns += [
        "SyncAction TEXT DEFAULT 'NONE'",   # NONE | INSERT | UPDATE | DELETE
        "SyncStatus TEXT DEFAULT 'DONE'",   # DONE | PENDING | IN_PROGRESS | ERROR
        "LastSync TEXT",                    # Last synchro SQL→SF
        "LastExtract TEXT",                 # Last synchro SF→SQL
        "RefreshPeriod INTEGER"             # refresh interval
    ]
    
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {object_name.lower()} (
        {', '.join(columns)}
        {',' if fk_constraints else ''}
        {', '.join(fk_constraints)}
    )
    """
    cur.execute(create_sql)
    return create_sql
    
def insert_picklists(cur, schema):
    """
    Insère toutes les picklists d'un schema dans les tables picklists et picklist_values
    """

    for obj_name, obj_data in schema.items():
        for picklist_id, picklist in obj_data.get("picklists", {}).items():
            # --- Insert picklist ---
            cur.execute("""
                INSERT OR IGNORE INTO picklists (
                    picklist_id, picklist_name, object_name, restrictedPicklist, dependentPicklist
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                picklist["picklist_id"],
                picklist["picklist_name"],
                obj_name,
                int(picklist.get("restrictedPicklist", False)),
                int(picklist.get("dependentPicklist", False))
            ))

            # --- Insert values ---
            for val in picklist["values"]:
                cur.execute("""
                    INSERT OR IGNORE INTO picklist_values (
                        value_id, picklist_id, value, label, active
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    val["value_id"],
                    picklist["picklist_id"],
                    val["value"],
                    val.get("label", val["value"]),
                    int(val.get("active", True))
                ))
    
def load_sf_to_sql(db_file, schema, sf, password=None, use_sqlcipher=True, limit_per_object=100000):
    global sf_dict_list
    
    sf_dict_list={}
    
    if use_sqlcipher:
        import sqlcipher3 as sqlite
    else:
        import sqlite3 as sqlite

    conn = sqlite.connect(db_file)
    cur = conn.cursor()
    if use_sqlcipher and password:
        cur.execute(f"PRAGMA key = '{password}'")

    # PRAGMA speedup import
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=OFF")
    cur.execute("PRAGMA temp_store=MEMORY")
    cur.execute("PRAGMA cache_size=-2000")

    for sf_object, obj_schema in schema.items():
        table_name = sf_object.lower()
        # If not yet done, create tables for objects
        create_table_from_schema(cur, sf_object, schema)
        
        # Set fields to fetch from SF
        fields = [list(f.keys())[0] for f in obj_schema['fields']]
        soql = f"SELECT {', '.join(fields)} FROM {sf_object} LIMIT {limit_per_object}"
       
        logger_debug(f"[DB_SF_MANAGER] Fetching object {sf_object}...")
        # Insertions
        counter = 0
        for record in fetch_records_paged(sf, soql):
            columns = []
            values = []
            counter+=1
            for field in fields:
                col_name = "sf_id" if field == "Id" else field
                columns.append(col_name)
                values.append(normalize_sf_value(sf_object,field,record.get(field)))
            placeholders = ",".join("?" for _ in values)
            sql = f"INSERT OR REPLACE INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            #values = [normalize_sf_value(record.get(field)) for field in fields]

            cur.execute(sql, values)

        if counter >= limit_per_object:
            logger_debug(f"[DB_SF_MANAGER] ⚠️ {table_name}: {counter} records loaded, limit is reached!! ({limit_per_object}).")    
        else:
            logger_debug(f"[DB_SF_MANAGER] ✅ {table_name}: {counter} records loaded (limit is {limit_per_object}).")

    for k,v in sf_dict_list.items():
        logger_debug(f"[DB_SF_MANAGER] ⚠️ In object {k} following field(s) {v['fields']} is/are a dict or list.")
    
    conn.commit()
    cur.execute("PRAGMA synchronous=NORMAL")
    create_indexes(conn,schema)
    generate_column_index(conn,schema)
    conn.close()
    
    save_json_to_file(sf_dict_list,DB_SF_DICT)


def normalize_sf_value(sf_object,field,v):
    import json
    from datetime import date, datetime
    from decimal import Decimal
    global sf_dict_list

    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (dict, list)):
        if sf_object not in sf_dict_list:
            sf_dict_list[sf_object]={"fields":[field],"structure":[v]}
        elif field not in sf_dict_list[sf_object]["fields"]:
            sf_dict_list[sf_object]["fields"].append(field)
            sf_dict_list[sf_object]["structure"].append(v)
            
        if isinstance(v, dict) and "Name" in v:
            return v["Name"]
        return json.dumps(v, ensure_ascii=False)
    return str(v) if not isinstance(v, (int, float)) else v

def fetch_records_paged(sf,soql, batch_size=2000):
    """
    Generator to fetch Salesforce records page by page.
    """
    result = sf.query(soql)

    while True:
        for record in result["records"]:
            yield record  # one record at a time

        if not result.get("nextRecordsUrl"):
            break  # no more pages

        result = sf.query_more(result["nextRecordsUrl"], True)
        
def create_indexes(conn, schema):
    cursor = conn.cursor()
    for table, definition in schema.items():
        fields = [list(f.keys())[0] for f in definition["fields"]]

        # Index sur tous les champs qui finissent par "Id" sauf la PK "Id"
        for f in fields:
            if f.endswith("Id") and f != "Id":
                idx_name = f"idx_{table}_{f}"
                cursor.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}"("{f}")')

        # Index sur quelques champs fréquents
        if "Name" in fields:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table}_Name" ON "{table}"("Name")')
        if "Email" in fields:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table}_Email" ON "{table}"("Email")')
        if "LastModifiedDate" in fields:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table}_LastModifiedDate" ON "{table}"("LastModifiedDate")')
            
        if table == 'Product2':
            print("index Product2")
            cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_product2_name_family ON Product2 (Name, Family);')
        elif table == 'PricebookEntry':
            print("index PricebookEntry")
            cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_pricebookentry_main ON PricebookEntry (Pricebook2Id, Product2Id, CurrencyIsoCode);')

    conn.commit()
    
def generate_column_index(conn, schema):

    cursor = conn.cursor()
    indexes = {}
    
    for sf_object, obj_schema in schema.items():
        table_name = sf_object.lower()

        cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
        col_names = [desc[0] for desc in cursor.description]
        col_index_mapping = {name: idx for idx, name in enumerate(col_names)}
        
        indexes[table_name] = col_index_mapping

    save_json_to_file(indexes,DB_COL_INDEX)

def refresh_table_from_sf(conn, table_name, records, schema):
    """
    Recharge une table avec les données SF.
    - conn: connexion SQLite déjà ouverte
    - table_name: ex "Opportunity"
    - records: liste de dicts Salesforce
    - schema: dict du schéma JSON
    """

    cur = conn.cursor()

    # SF Fields
    sf_fields = [list(f.keys())[0] for f in schema[table_name]["fields"]]

    # SQL DB Technical attributs
    technical_fields = ["SyncAction", "SyncStatus", "LastSync", "LastExtract", "RefreshPeriod"]

    # On construit dynamiquement l’UPDATE/INSERT
    placeholders = ", ".join("?" for _ in sf_fields)
    insert_sql = f"""
        INSERT INTO {table_name} ({", ".join(sf_fields)})
        VALUES ({placeholders})
        ON CONFLICT(sf_id) DO UPDATE SET
        {", ".join([f"{col}=excluded.{col}" for col in sf_fields if col != "sf_id"])}
    """

    # Insert SF data into SQL base
    for rec in records:
        values = [rec.get(f, None) for f in sf_fields]
        cur.execute(insert_sql, values)

    # Update LastExtract for all records
    cur.execute(f"""
        UPDATE {table_name}
        SET LastExtract = ?
        WHERE LastExtract IS NULL OR LastExtract != ?
    """, (datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))

    conn.commit()
    
def sync_sql_to_sf(conn, table_name, sf_object, sf_conn):

    cur = conn.cursor()

    # Select pending records to be updated in SF
    cur.execute(f"""
        SELECT * FROM {table_name}
        WHERE SyncStatus='PENDING'
    """)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    if not rows:
        print(f"[{table_name}] Rien à synchroniser.")
        return

    for row in rows:
        record = dict(zip(columns, row))
        sf_id = record.get("sf_id")
        action = record.get("SyncAction")

        try:
            if action == "INSERT":
                # Remove internal attributs
                payload = {k: v for k, v in record.items() 
                           if k not in ["sf_id","SyncAction","SyncStatus","LastSync","LastExtract","RefreshPeriod"] and v is not None}
                result = sf_conn.__getattr__(sf_object).create(payload)
                new_id = result["id"]

                # Mettre à jour en SQL
                cur.execute(f"""
                    UPDATE {table_name}
                    SET sf_id=?, SyncStatus='DONE', SyncAction='NONE', LastSync=?
                    WHERE rowid=?
                """, (new_id, datetime.utcnow().isoformat(), record["rowid"]))

            elif action == "UPDATE" and sf_id:
                payload = {k: v for k, v in record.items() 
                           if k not in ["sf_id","SyncAction","SyncStatus","LastSync","LastExtract","RefreshPeriod"] and v is not None}
                sf_conn.__getattr__(sf_object).update(sf_id, payload)

                cur.execute(f"""
                    UPDATE {table_name}
                    SET SyncStatus='DONE', SyncAction='NONE', LastSync=?
                    WHERE rowid=?
                """, (datetime.utcnow().isoformat(), record["rowid"]))

            elif action == "DELETE" and sf_id:
                sf_conn.__getattr__(sf_object).delete(sf_id)
                cur.execute(f"""
                    DELETE FROM {table_name}
                    WHERE rowid=?
                """, (record["rowid"],))

            else:
                print(f"[WARN] Record {record} ignoré (action={action}, sf_id={sf_id})")

        except Exception as e:
            print(f"[ERREUR] {e}")
            cur.execute(f"""
                UPDATE {table_name}
                SET SyncStatus='ERROR'
                WHERE rowid=?
            """, (record["rowid"],))

    conn.commit()

def main(argv=None):
    import argparse
    
    global sf
    
    from context_manager import set_client_context, NO_SECRET

    set_client_context(-1,NO_SECRET,logger_debug,logger_debug,logger_debug,logger_debug,None)
    
    parser = argparse.ArgumentParser(description="Create a SQLite database from scratch based on SF schema and fetch SF database. The local database is encrypted with a password defined into env file.")
    parser.add_argument('--pwd', default=None, help='pwd for decrypting secrets in env file')
    
    if not argv:
        args = parser.parse_args()
    else:
        args = parser.parse_args(argv)
    
    logger_debug("[DB_SF_MANAGER]  Loading SF objects descriptor")
    
    schema = load_objects(SF_PREFERRED_OBJECTS_FILE_PATH)
    
    if not schema:
        logger_debug("[DB_SF_MANAGER] No schema available!")
        return
            
    try:

        logger_debug("[DB_SF_MANAGER] Loading SF objects descriptor")
        
        appSecurity.set_env_security_variable(args.pwd)
        
        if not appSecurity.sf_usr_name:
            if not appSecurity.decrypt_credentials():
                if not args.pwd:
                    logger_debug("[DB_SF_MANAGER] No pwd provided! use option --pwd")
                return
                
        logger_debug("[DB_SF_MANAGER] Building DB...")
        build_sql_database(DB_FILE_PATH,
                           appSecurity.db_sql_sf_pwd,
                           schema)
    
        logger_debug("[DB_SF_MANAGER] Fetching data from SF db...")
        
        sf = Salesforce(instance_url=SF_LOGIN_URL,
                        username=appSecurity.sf_usr_name,
                        password=appSecurity.sf_usr_pwd,
                        security_token=appSecurity.sf_usr_token,
                        domain='test')
               
        load_sf_to_sql(DB_FILE_PATH,
                       schema,
                       sf,
                       password=appSecurity.db_sql_sf_pwd)
                       
        logger_debug("[DB_SF_MANAGER] SF Import done, SQL base built!")
        
    except (SalesforceMalformedRequest, AttributeError, Exception) as e:
        logger_debug(f"[DB_SF_MANAGER] ❌ Error exception '{type(e).__name__}' raised with '{e}'")
        return False   

def create_opportunity(sf_account_id,sf_contact_id,opp_info, oppContactRole_info, product_items,print_func) -> str:

    external_id = "customer123_requestABC"
    sf_id       = '0069K00000N0M89QAF'
    
    if not opp_info or sf_account_id == -1:
        logger_debug("[DB_SF_MANAGER] ⚠️ unable to create opportunity, no account id")
        return None
    
    print_func(f"<strong>Saleforce operations:</strong>")
    
    opp_info['AccountId']   = sf_account_id
    opp_info['Probability'] = DEFAULT_OPP_PROBABILITY
    opp_info['ECU_Domain__c'] = 'Cross-Domain'
    opp_info['Sub_D__c'] = 'Gateway'
    
    print_func(f"- Connecting to Server ongoing...")
    
    sf = Salesforce(instance_url=SF_LOGIN_URL,
                    username=appSecurity.sf_usr_name,
                    password=appSecurity.sf_usr_pwd,
                    security_token=appSecurity.sf_usr_token,
                    domain='test')

    ##existing = sf.query(f"SELECT * FROM Opportunity WHERE Id = '{sf_id}' LIMIT 1")
    
    opp_info['UpdateSchedule__c']="Adapt schedule"

    existing = None
    
    try:
        existing = sf.Opportunity.get(sf_id)
    
        logger_debug(f"[DB_SF_MANAGER] Opportunity '{sf_id}' is being {'updated' if existing else 'created'}...") 
        print_func(f"- Opportunity '{sf_id}' is being {'updated' if existing else 'created'} with Salesforce...")

        logger_debug(f"[DB_SF_MANAGER] Opportunity parameters: {opp_info}")
        
        if existing:
            opp_id = existing['Id']
            # UPDATE existing opportunity
            old_roles = sf.query(f"SELECT Id FROM OpportunityContactRole WHERE OpportunityId='{opp_id}'")
            for r in old_roles['records']:
                sf.OpportunityContactRole.delete(r['Id'])
            
            sf.Opportunity.update(opp_id, opp_info)
            opportunity = sf.Opportunity.get(opp_id)
        else:
            # CREATE new opportunity
            opportunity = sf.Opportunity.create(opp_info)
    except (SalesforceMalformedRequest, AttributeError) as e:
        logger_debug(f"[DB_SF_MANAGER] ❌ SF Error while {'updating' if existing else 'creating'} SF opportunity: exception '{type(e).__name__}' raised with {e}")
        return None    
    except Exception as e:
        logger_debug(f"[DB_SF_MANAGER] ❌ Error wile {'updating' if existing else 'creating'} SF opportunity : exception '{type(e).__name__}' raised with {e}")
        return None    
    
    logger_debug(f"[DB_SF_MANAGER] ✅ Fields for opportunity '{opportunity['Id']}' has been {'updated' if existing else 'created'} successfuly.")
    print_func(f"-> ✅ Fields for opportunity '{opportunity['Id']}' has been {'updated' if existing else 'created'} successfuly.")
        
    if sf_contact_id != -1:
        
        logger_debug(f"[DB_SF_MANAGER] Updating Opportunity's contact role...")
        print_func(f"- Updating Opportunity's contact role...")
        
        try:
            oppContactRole_info['OpportunityId'] = sf_id
            oppContactRole_info['ContactId']     = sf_contact_id
            oppContactRole_info['IsPrimary']     = True
            
            sf.OpportunityContactRole.create(oppContactRole_info)
            
            logger_debug(f"[DB_SF_MANAGER] ✅ Opportunity's contact role updated!")
            print_func(f"-> ✅ Opportunity's contact role updated!")
            
        except Exception as e:
            logger_debug(f"[DB_SF_MANAGER] ❌ Error wile creating SF opportunity contact role: exception '{type(e).__name__}' raised with '{e}'")
            return None         
    else:
        logger_debug("[DB_SF_MANAGER] ⚠️ unable to create opportunity contact role, no contact id!")

    logger_debug(f"[DB_SF_MANAGER] Collecting previous product items to delete...")
    print_func(f"- Collecting previous product items to delete...")
    
    prev_itemLines = sf.query(f"SELECT Id FROM OpportunityLineItem WHERE OpportunityId='{opp_id}'")
    
    if prev_itemLines and len(prev_itemLines['records']) > 0:
        logger_debug(f"[DB_SF_MANAGER] Deleting previous product items (nb={len(prev_itemLines['records'])}) and associated revenue schedules...") 
        
        oli_ids = [r["Id"] for r in prev_itemLines["records"]]

        if oli_ids:
            
            logger_debug(f"[DB_SF_MANAGER] Collecting previous revenue schedules to delete...")
            
            ids_str = "','".join(oli_ids)

            schedule_query = f"""
                SELECT Id
                FROM OpportunityLineItemSchedule
                WHERE OpportunityLineItemId IN ('{ids_str}')
            """

            schedules = sf.query(schedule_query)
            schedule_ids = [r["Id"] for r in schedules["records"]]

            def chunk(lst, size=200):
                for i in range(0, len(lst), size):
                    yield lst[i:i + size]

            if schedule_ids:
                logger_debug(f"[DB_SF_MANAGER] Deleting previous revenue schedules...")
                for batch in chunk(schedule_ids):
                    if batch:
                        payload = [{"Id": i} for i in batch]
                        sf.bulk.OpportunityLineItemSchedule.delete(payload)

            logger_debug(f"[DB_SF_MANAGER] Deleting previous product items...")
            for batch in chunk(oli_ids):
                if batch:
                    payload = [{"Id": i} for i in batch]
                    sf.bulk.OpportunityLineItem.delete(payload)
            
            logger_debug(f"[DB_SF_MANAGER] ✅ Previous product items with associated revenue schedules have been deleted!")
            print_func(f"-> ✅ Previous product items with associated revenue schedules have been deleted!")
        else:
            logger_debug(f"[DB_SF_MANAGER] ❌ Error wile creating SF product items list!'")
    else:
        logger_debug(f"[DB_SF_MANAGER] ✅ No product items to delete!")
        print_func(f"-> ✅ No product items to delete!")
        
    """
    for r in prev_itemLines['records']:
        prev_itemScheduleLines = sf.query(f"SELECT Id FROM OpportunityLineItemSchedule WHERE OpportunityLineItemId = '{r['Id']}'")

        for record in prev_itemScheduleLines['records']:
            sf.OpportunityLineItemSchedule.delete(record['Id'])
        sf.OpportunityLineItem.delete(r['Id'])
    """
    
    if product_items:
        opp_info2={}
        opp_info2['Pricebook2Id']=product_items[0][dbpl_if.TABLE_IDX_SF_PRICE_BOOK]
        sf.Opportunity.update(opp_id, opp_info2)

        logger_debug(f"[DB_SF_MANAGER] Updating Opportunity's product items...")
        print_func(f"- Updating Opportunity's product items...")
        
        service_date = normalize_date_iso(compute_first_delivery_date(opp_info['CloseDate']))
        
        oli_payload = []
        
        for product in product_items:
            logger_debug(f"[DB_SF_MANAGER] Adding product item '{product[dbpl_if.TABLE_IDX_PRODUCT_ITEM_NAME]}' / '{product[dbpl_if.TABLE_IDX_LICENSE_TYPE_NAME]}'...")
            
            item_data = {
                "OpportunityId"    : sf_id,
                "Product2Id"       : product[dbpl_if.TABLE_IDX_SF_PRODUCT_ID],
                "ServiceDate"      : service_date,
                "Quantity"         : product[dbpl_if.TABLE_IDX_QUANTITY],
                "UnitPrice"        : 0,
                "CurrencyIsoCode"  : product[dbpl_if.TABLE_IDX_AAV_CURRENCY],   # facultatif, selon org multi-devise
                "PricebookEntryId" : product[dbpl_if.TABLE_IDX_SF_PRICE_BOOK_ENTRY], #'01u7T000000kyxSQAQ',      # à utiliser si ta Pricebook est gérée manuellement
                "Description"      : product[dbpl_if.TABLE_IDX_PRODUCT_ITEM_NAME] + ' / ' + product[dbpl_if.TABLE_IDX_LICENSE_TYPE_NAME]
            }
            oli_payload.append(item_data)
            
        logger_debug(f"[DB_SF_MANAGER] Creating Opportunity's product items by bulk...") 
        oli_results = sf.bulk.OpportunityLineItem.insert(
            oli_payload,
            bypass_results=False,
            use_serial=True
        )
        
        logger_debug(f"[DB_SF_MANAGER] ✅ Product items have been created!")
        print_func(f"-> ✅ Product items have been created!")
        
        logger_debug(f"[DB_SF_MANAGER] Cleaning revenue schedule at 0...") 
        
        oli_ids = [res["id"] for res in oli_results if res.get("success")]
        
        auto_sched = sf.query(f"""
            SELECT Id
            FROM OpportunityLineItemSchedule
            WHERE OpportunityLineItemId IN ('{"','".join(oli_ids)}')
            AND Revenue = 0
        """)

        auto_ids = [r["Id"] for r in auto_sched["records"]]

        if auto_ids:
            payload = [{"Id": i} for i in auto_ids]
            sf.bulk.OpportunityLineItemSchedule.delete(
                payload,
                bypass_results=True,
                use_serial=True
            )            

        schedule_payload = []

        nb_due_dates = 4

        for oli_res, product in zip(oli_results, product_items):
            if not oli_res.get("success"):
                continue

            oli_id = oli_res["id"]
            total = product[dbpl_if.TABLE_IDX_UNIT_PRICE]
            amount = total / nb_due_dates

            for i in range(nb_due_dates):
                schedule_payload.append({
                    "OpportunityLineItemId": oli_id,
                    "Revenue": amount,
                    "ScheduleDate": end_of_month_plus_n_days(
                        service_date,
                        default_offset=90 * i
                    ),
                    "Type": "Revenue"
                })
                logger_debug(f"[DB_SF_MANAGER] Adding revenue schedule at {service_date} + {i*90} days for product item '{product[dbpl_if.TABLE_IDX_PRODUCT_ITEM_NAME]}' / '{product[dbpl_if.TABLE_IDX_LICENSE_TYPE_NAME]}'...")

        def chunk(lst, size=200):
            for i in range(0, len(lst), size):
                yield lst[i:i + size]

        logger_debug(f"[DB_SF_MANAGER] Creating Opportunity's revenue schedule by bulk...") 
        print_func(f"- Creating Opportunity's revenue schedule by bulk...") 
        
        for batch in chunk(schedule_payload):
            sf.bulk.OpportunityLineItemSchedule.insert(
                batch,
                bypass_results=True,
                use_serial=True
            )
        
        logger_debug(f"[DB_SF_MANAGER] ✅ Revenue Schedule have been created!")
        print_func(f"-> ✅ Revenue Schedule have been created!")
        
        """
        for product in product_items:
            try:
                logger_debug(f"[DB_SF_MANAGER] Adding product item '{product[dbpl_if.TABLE_IDX_PRODUCT_ITEM_NAME]}' / '{product[dbpl_if.TABLE_IDX_LICENSE_TYPE_NAME]}'...")
                
                item_data = {
                    "OpportunityId"    : sf_id,
                    "Product2Id"       : product[dbpl_if.TABLE_IDX_SF_PRODUCT_ID],
                    "ServiceDate"      : service_date,
                    "Quantity"         : product[dbpl_if.TABLE_IDX_QUANTITY],
                    "UnitPrice"        : 0,
                    "CurrencyIsoCode"  : product[dbpl_if.TABLE_IDX_AAV_CURRENCY],   # facultatif, selon org multi-devise
                    "PricebookEntryId" : product[dbpl_if.TABLE_IDX_SF_PRICE_BOOK_ENTRY], #'01u7T000000kyxSQAQ',      # à utiliser si ta Pricebook est gérée manuellement
                    "Description"      : product[dbpl_if.TABLE_IDX_PRODUCT_ITEM_NAME] + ' / ' + product[dbpl_if.TABLE_IDX_LICENSE_TYPE_NAME]
                }    
                oli = sf.OpportunityLineItem.create(item_data)
                oli = sf.OpportunityLineItem.get(oli['id'])

                total = product[dbpl_if.TABLE_IDX_UNIT_PRICE] #oli['TotalPrice']
                nb_due_dates = 4
                amount = total / nb_due_dates
                
                schedules = []

                for i in range(nb_due_dates):
                    schedules.append({
                        'OpportunityLineItemId': oli['Id'],
                        'Revenue': amount,
                        'ScheduleDate': end_of_month_plus_n_days(service_date,default_offset=90*i),
                        'Type': 'Revenue'
                    })

                logger_debug(f"[DB_SF_MANAGER] Creating revenue schedule for product item '{product[dbpl_if.TABLE_IDX_PRODUCT_ITEM_NAME]}' / '{product[dbpl_if.TABLE_IDX_LICENSE_TYPE_NAME]}'...")
                # Insertion
                for s in schedules:
                    sf.OpportunityLineItemSchedule.create(s)

            except Exception as e:
                logger_debug(f"[DB_SF_MANAGER] ❌ Error wile adding product item '{product[dbpl_if.TABLE_IDX_PRODUCT_ITEM_NAME]}' / '{product[dbpl_if.TABLE_IDX_LICENSE_TYPE_NAME]}' exception '{type(e).__name__}' raised with '{e}'")
                pass
            """
    else:
        logger_debug(f"[DB_SF_MANAGER] No product items to create for opportunity!") 
        
    logger_debug(f"[DB_SF_MANAGER] ✅ Opportunity '{sf_id}' has been {'updated' if existing else 'created'} successfuly.") 
    print_func(f"-> ✅ Opportunity '{sf_id}' has been {'updated' if existing else 'created'} successfuly.") 
    
    return sf_id


def create_opportunity_old(sf_account_obj, sf_contact_obj, opp_name,opp_desc, opp_stage='Opportunity',business_type='New Opportunity',invoicing_entity='EB-DE',opp_currency='EUR'):
    """
    •	Opportunity Name
    •	Account Name
    •	Opportunity Currency
    •	Stage
    •	Request Date
    •	Request Deadline
    •	Business Type
    •	Close Date
    •	Invoicing Entity
    """
    external_id = "customer123_requestABC"
    sf_id = '0069K00000N0M89QAF'
    
    sf = Salesforce(instance_url=SF_LOGIN_URL,
                    username=appSecurity.sf_usr_name,
                    password=appSecurity.sf_usr_pwd,
                    security_token=appSecurity.sf_usr_token,
                    domain='test')

    request_date = datetime.utcnow()                  # datetime object
    request_deadline = request_date + timedelta(days=7)
    close_date = request_date + timedelta(days=90)   # pour 3 mois ≈ 90 jours

    # Formater en yyyy-mm-dd pour SF
    request_date_str     = request_date.strftime("%Y-%m-%d")
    request_deadline_str = request_deadline.strftime("%Y-%m-%d")
    close_date_str       = close_date.strftime("%Y-%m-%d")
    
    opp_info = {
        "Name"                     : opp_name,
        "StageName"                : opp_stage,
        "SF42_Request_Date__c"     : request_date_str,
        "SF42_Request_Deadline__c" : request_deadline_str,
        "CloseDate"                : close_date_str,
        "AccountId"                : sf_account_obj['sf_id'],
        #"ContactId"                : sf_contact_obj['sf_id'],
        "Business_Type__c"         : business_type,
        "Invoicing_Entity__c"      : invoicing_entity,
        "CurrencyIsoCode"          : opp_currency,
        "Description"              : f'AI Quote Assistant creation.\n{opp_desc}'#,
        #'External_Link__c'           : external_id
    }

    pp_contact_role = {
        'OpportunityId': sf_id,
        'ContactId'    : sf_contact_obj['sf_id'],
        'Role'         : 'Decision Maker',
        'IsPrimary'    : True
    }
            
    ##existing = sf.query(f"SELECT * FROM Opportunity WHERE Id = '{sf_id}' LIMIT 1")
    existing = sf.Opportunity.get(sf_id)
    
    if existing:
        opp_id = sf_id#existing['records'][0]['Id']
        # UPDATE existing opportunity
        old_roles = sf.query(f"SELECT Id FROM OpportunityContactRole WHERE OpportunityId='{opp_id}'")
        for r in old_roles['records']:
            sf.OpportunityContactRole.delete(r['Id'])
        
        sf.Opportunity.update(opp_id, opp_info)
        opportunity = sf.Opportunity.get(opp_id)
    else:
        # CREATE new opportunity
        opportunity = sf.Opportunity.create(opp_info)
        
    if opportunity:
        print(opportunity['Id'])
    else:
        print('No Opp created!!')

    sf.OpportunityContactRole.create({
        'OpportunityId': sf_id,
        'ContactId': sf_contact_obj['sf_id'],
        'Role': 'Decision Maker',
        'IsPrimary': True
    })


if __name__ == "__main__":        
    main()

if __name__ == "__tobedeleted__":        

#soql = "SELECT Id, Name, BillingCountry, BillingCity FROM Account"
#soql = "SELECT Id, Name, AccountId, LastName, FirstName, Email FROM Contact WHERE LastName = 'Jones'"   
#soql = "SELECT Id, * FROM Account"
    """  opportunity_fields = [list(field.keys())[0] for field in schema["Account"]["fields"]]
    soql = f"SELECT {', '.join(opportunity_fields)} FROM Account LIMIT 10"
    print(soql)
    for record in fetch_records_paged(sf,soql):
    print(record["Id"], record["Name"])
    #print(record)
    # 👉 Ici tu peux directement écrire dans SQLite au fil de l’eau    
    """
    
def refresh_sf_cache(object_name, soql, key_fields, force=False):
    global sf, logger_debug
    
    """
    Refresh local SQLite cache for a Salesforce object
    - object_name: table name in SQLite
    - soql: SOQL query string to fetch records
    - key_fields: list of fields to keep in SQLite
    - force: force refresh even if recent
    """
    conn = sqlite.connect(DB_FILE_PATH)
    cursor = conn.cursor()

    # Check last update
    cursor.execute(f"SELECT MAX(LastUpdated) FROM {object_name}")
    result = cursor.fetchone()
    last_updated = result[0] if result else None
    refresh_needed = force

    if last_updated:
        last_date = datetime.fromisoformat(last_updated)
        if datetime.now() - last_date > timedelta(days=7):
            refresh_needed = True
    else:
        refresh_needed = True

    if refresh_needed:
        logger_debug(f"(DB_SF_MANAGER] Refreshing {object_name} cache from Salesforce...")
        records = sf.query_all(soql)["records"]

        for rec in records:
            filtered_rec = {k: rec.get(k, "") for k in key_fields}
            filtered_rec["LastUpdated"] = datetime.now()
            upsert_record_sqlite(object_name, filtered_rec)
    conn.close()
    
def upsert_record_sqlite(table_name, record):
    conn = sqlite.connect(DB_SF_MANAGER_PATH)
    cursor = conn.cursor()

    columns_sql = []
    for k, v in record.items():
        if isinstance(v, int):
            col_type = "INTEGER"
        elif isinstance(v, float):
            col_type = "REAL"
        elif isinstance(v, datetime):
            col_type = "TEXT"
            record[k] = v.isoformat()
        else:
            col_type = "TEXT"
        col_def = f"{k} {col_type}" + (" PRIMARY KEY" if k == "Id" else "")
        columns_sql.append(col_def)

    create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_sql)})"
    cursor.execute(create_sql)

    keys = ", ".join(record.keys())
    placeholders = ", ".join("?" for _ in record)
    updates = ", ".join(f"{k}=excluded.{k}" for k in record.keys() if k != "Id")

    sql = f"""
        INSERT INTO {table_name} ({keys})
        VALUES ({placeholders})
        ON CONFLICT(Id) DO UPDATE SET {updates}
    """
    cursor.execute(sql, tuple(record.values()))
    conn.commit()
    conn.close()

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
        logger_debug(f"[DB_SF_MANAGER] ❌ Error in get_or_create_record for {object_name}: exception '{type(e).__name__}' raised with '{e}'")
        return None

def update_record(object_name, record_id, fields_dict):
    global sf, logger_debug
    
    try:
        sf_object = getattr(sf, object_name)
        sf_object.update(record_id, fields_dict)
        # Update cache
        fields_dict["Id"] = record_id
        fields_dict["LastUpdated"] = datetime.now()
        table_name = object_name.lower() + "s"
        upsert_record_sqlite(table_name, fields_dict)
        return True
    except (SalesforceMalformedRequest, AttributeError, Exception) as e:
        logger_debug(f"[DB_SF_MANAGER] ❌ Error updating {object_name} {record_id}: exception '{type(e).__name__}' raised with '{e}'")
        return False

def get_paginated_records(table_name, page=1, per_page=100):
    conn = sqlite.connect(DB_SF_MANAGER_PATH)
    cursor = conn.cursor()

    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total = cursor.fetchone()[0]

    offset = (page - 1) * per_page
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY Id LIMIT ? OFFSET ?", (per_page, offset))

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    conn.close()

    records = [dict(zip(columns, r)) for r in rows]
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "records": records
    }

