from simple_salesforce import Salesforce
import json
import os
import sys
import requests
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import appSecurity
from tools import unix_path, load_json_file, setup_logger, save_json_to_file, sort_json, make_dir

logger       = setup_logger()
logger_debug = logger.debug

SF_LOGIN_URL = "https://elektrobit--partial.sandbox.lightning.force.com/"  # sandbox => test, prod => login

MODULE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = unix_path(MODULE_DIR, "./gen")

# Ensure output directory exists
make_dir(OUTPUT_DIR)

SF_SCHEMA_EXTRACT_FILE      = "sf_schema_extract.json"
SF_SCHEMA_INSTRUMENTED_FILE = "sf_schema_instrumented.json"
SF_PREFERENCES_FILE         = unix_path(MODULE_DIR,"sf_preferred_objects_and_fields.json")
SF_PREFERRED_OBJECTS_FILE   = "sf_preferred_objects_list.json"

SF_PREFERRED_OBJECTS_FILE_PATH = unix_path(OUTPUT_DIR, SF_PREFERRED_OBJECTS_FILE)

meta_keys_to_keep = [
                        "activateable", "custom", "customSetting", "deepCloneable",
                        "deprecatedAndHidden", "feedEnabled", "keyPrefix", "label",
                        "labelPlural", "layoutable", "mergeable", "mruEnabled", "queryable",
                        "replicateable", "retrieveable", "searchable", "triggerable",
                        "undeletable", "updateable", "urls_", "recordTypeInfos_",
                        "childRelationships_","preferred","lastExtract","refreshFrequency"
                    ]

fields_keys_to_keep = [
                        "id","name","type","defaultValue","preferred","label","inlineHelpText","required","sqlType","picklist_id","compoundFieldName"
                      ]
                    
SF_TO_SQLITE = {
    "string"            : "TEXT",
    "textarea"          : "TEXT",
    "phone"             : "TEXT",
    "url"               : "TEXT",
    "email"             : "TEXT",
    "address"           : "TEXT",
    "complexvalue"      : "TEXT",
    "anyType"           : "TEXT",
    "combobox"          : "TEXT",
    "long"              : "INTEGER",
    "picklist"          : "TEXT",
    "multipicklist"     : "TEXT",
    "boolean"           : "INTEGER",
    "int"               : "INTEGER",
    "double"            : "REAL",
    "currency"          : "REAL",
    "percent"           : "REAL",
    "date"              : "TEXT",      # format ISO: YYYY-MM-DD
    "datetime"          : "TEXT",  # format ISO: YYYY-MM-DDTHH:MM:SSZ
    "time"              : "TEXT",      # format ISO: HH:MM:SS
    "reference"         : "TEXT",
    "id"                : "TEXT",
    "base64"            : "BLOB",
    "encryptedstring"   : "TEXT",
    "location"          : "TEXT",   # ou 2 colonnes lat/lon
    "json"              : "TEXT"
}
                    
# ---------------------------------------------------
# Load preferences file SF_PREFERENCES_FILE
# ---------------------------------------------------
def load_preferences(preferences_file=SF_PREFERENCES_FILE):
    if os.path.exists(preferences_file):
        logger_debug("[SF_SCHEMA_GEN] loading preferences file...")
        return load_json_file(preferences_file,defaultVal={})
        
    logger_debug(f"[SF_SCHEMA_GEN] ❌ Error file {preferences_file} not found !!")
    
    return {}

def build_limited_meta(desc: dict) -> dict:
    meta_data = desc.get("_meta", {}).copy()
    
    if not meta_data:
        return {}
    
    meta = {k: meta_data.get(k) for k in meta_keys_to_keep if k in meta_data}
    
    return meta

def object_fields(schema, object_name, visited=None, expand=False, output_dir=OUTPUT_DIR,requiredOnly=True):
    if visited is None:
        visited = set()
    if object_name in visited:
        return {"object": object_name, "circularReference": True}
    visited.add(object_name)

    obj = schema.get(object_name)
    if not obj:
        return {"object": object_name, "notFound": True}

    meta_out = build_limited_meta(obj)
    
    relationships_data = obj.get("relationships", {}).copy()
    
    picklists_data = obj.get("picklists", {}).copy()

    fields = []
    fieldsName = []
    for field_name, field_data in obj.get("fields", {}).items():
        
        fieldsName.append(field_name)        
        
        required = field_data["required"]
        preferred = field_data["preferred"]
        
        if requiredOnly and not required and not preferred: continue
        
        entry = {k: field_data.get(k) for k in fields_keys_to_keep if k in field_data}
        
        entry["children"] =[]
        
        ftype = field_data.get("type")
        
        if ftype == "reference":
            refs = field_data.get("referenceTo", [])
            if refs:
                ref_obj = refs[0]
                entry["referenceTo"] = ref_obj
                if expand:
                    entry["children"] = object_fields(schema, ref_obj, visited.copy(), expand, output_dir,requiredOnly)
                else:
                    filename = f"sf_{ref_obj}_fields.json"
                    entry["childrenFile"] = unix_path(output_dir, filename)
                    entry["children"] = []

        fields_info = {}
        fields_info[entry["name"]] = entry

        fields.append(fields_info)

    return {
        "object": object_name,
        "_meta": meta_out,
        "fields": fields,
        "fieldsName": fieldsName,
        "relationships":relationships_data,
        "picklists": picklists_data
    }

def sort_dict_keys(obj):
    if isinstance(obj, dict):
        return {k: sort_dict_keys(obj[k]) for k in sorted(obj)}
    elif isinstance(obj, list):
        return [sort_dict_keys(i) for i in obj]
    else:
        return obj

def export_fields(schema, root_object, expand=False, output_dir=OUTPUT_DIR,requiredOnly=True):
    
    make_dir(output_dir)
    
    obj_json = object_fields(schema, root_object, expand=expand, output_dir=output_dir,requiredOnly=requiredOnly)

    filepath = unix_path(output_dir, f"sf_{root_object}_light.json")
    
    save_json_to_file(sort_json(obj_json),filepath,sort_keys=True)

    logger_debug(f"[SF_SCHEMA_GEN] ✅ File generated for {root_object} >> {filepath}")
    return obj_json, filepath
    
def export_object_fields(schema,expand=False, output_dir=OUTPUT_DIR,requiredOnly=True):
    
    table = {}
    
    for obj_name, obj_data in schema.items():

        if schema[obj_name]["_meta"]["preferred"]:
            data, filePath = export_fields(schema,obj_name,expand=expand,output_dir=output_dir,requiredOnly=requiredOnly)
            table[obj_name] = filePath
        
    obj_json = {
        "objects": table
    }
    
    save_json_to_file(sort_json(obj_json),SF_PREFERRED_OBJECTS_FILE_PATH,sort_keys=True)

    logger_debug(f"[SF_SCHEMA_GEN] ✅ File generated for objects table >> {SF_PREFERRED_OBJECTS_FILE_PATH}")    
    
def getPickListId(obj_name,field_name):
    return f"{obj_name}{field_name}"
    
# ---------------------------------------------------
# Apply preferences to schema
# ---------------------------------------------------
def apply_preferences(schema, preferences):
    warnings = []

    for obj_name, obj_data in schema.items():
        pref_obj = preferences.get(obj_name, {})
        obj_pref = pref_obj.get("preferred", False)

        # Add preferred flag at object level
        #schema[obj_name].setdefault("_meta", {})
        schema[obj_name]["_meta"]["preferred"] = obj_pref
        # Refresh frequency (default: weekly)
        schema[obj_name]["_meta"]["refreshFrequency"] = pref_obj.get("refreshFrequency", "weekly")

        #raise flag for mandatory fields
        for f_name, f_data in obj_data.get("fields", {}).items():
            ftype = f_data.get("type")
            f_data["sqlType"] = SF_TO_SQLITE[ftype]
            if ftype == "picklist":
                f_data["picklist_id"]=getPickListId(obj_name,f_name)
            if not f_data.get("nillable", True):
                f_data["required"] = True

        # If all fields should be preferred
        if pref_obj.get("allFieldsArePreferred", False):
            for f_name, f_data in obj_data.get("fields", {}).items():
                f_data["preferred"] = True
            continue

        # Explicit preferred fields
        for pf in pref_obj.get("preferredFields", []):
            if pf in obj_data["fields"]:
                obj_data["fields"][pf]["preferred"] = True
            else:
                warnings.append(f"[{obj_name}] field missing in schema: {pf}")

        # Required fields automatically preferred
        if pref_obj.get("allRequiredArePreferred", False):
            for f_name, f_data in obj_data["fields"].items():
                if not f_data.get("nillable", True):
                    f_data["preferred"] = True

        # Preferred by field type (reference, picklist, etc.)
        for f_name, f_data in obj_data["fields"].items():
            if "preferredTypes" in pref_obj and f_data.get("type") in pref_obj["preferredTypes"]:
                f_data["preferred"] = True

        # Warning if object is absent from preferences
        #if obj_name not in preferences:
        #    warnings.append(f"[{obj_name}] object not listed in {SF_PREFERENCES_FILE}")

    return schema, warnings

def prepare_schema(schema):
    
    logger_debug(f"[SF_SCHEMA_GEN] preparing schema...")
    
    for obj_name, obj_data in schema.items():

        schema[obj_name]["_meta"].setdefault("label", obj_name)
        schema[obj_name]["_meta"].setdefault("preferred", False)
        schema[obj_name]["_meta"].setdefault("refreshFrequency", "weekly")
        #schema[obj_name]["_meta"].setdefault("lastExtract", now)

        # --- CHAMPS ---
        for f_name, f_data in obj_data.get("fields", {}).items():
            schema[obj_name]["fields"][f_name].setdefault("preferred", False)
            schema[obj_name]["fields"][f_name].setdefault("required", False)
            schema[obj_name]["fields"][f_name].setdefault("sqlType", "TEXT")
            #schema[obj_name]["fields"][f_name].setdefault("lastExtract", now)
            
        # --- RELATIONS ENFANTS, RECORD TYPES, URLS ---
        record_types = schema[obj_name]["_meta"]["recordTypeInfos"]
        urls = schema[obj_name]["_meta"]["urls"]

        schema[obj_name].setdefault("relationships", {})
        schema[obj_name]["relationships"].setdefault("children", [])                   # objects that reference this one as parents
        schema[obj_name]["relationships"].setdefault("parents", [])                    # objects that reference this one as parents
        schema[obj_name]["relationships"].setdefault("references", [])                 # simple lookups
        schema[obj_name]["relationships"].setdefault("polymorphic_references", [])     # multi-object lookups
        schema[obj_name]["relationships"].setdefault("referencedBy", [])
        schema[obj_name]["relationships"].setdefault("referencedByPolymorphism", [])
        schema[obj_name]["relationships"].setdefault("recordTypeInfos", record_types)
        schema[obj_name]["relationships"].setdefault("urls", urls)

        schema[obj_name].setdefault("picklists", {})
        
    schema, warnings = analyze_relationships(schema)
    schema = collect_picklists(schema)
    
    logger_debug(f"[SF_SCHEMA_GEN] ✅ schema prepared")
    
    return schema, warnings

def analyze_relationships(schema):
    warnings = []
    
    # --- First pass: initialize structure ---
    for obj_name  in schema:
        
        schema[obj_name]["relationships"].setdefault("children", [])                   # objects that reference this one as parents
        schema[obj_name]["relationships"].setdefault("parents", [])                    # objects that reference this one as parents
        schema[obj_name]["relationships"].setdefault("references", [])                 # simple lookups
        schema[obj_name]["relationships"].setdefault("polymorphic_references", [])     # multi-object lookups
        schema[obj_name]["relationships"].setdefault("referencedBy", [])
        schema[obj_name]["relationships"].setdefault("referencedByPolymorphism", [])
    
    # --- Second pass: fill relationships ---
    for obj_name, obj_data in schema.items():

        # --- Children (direct childRelationships) ---
        relations = obj_data.get("childRelationships", [])
        for rel in relations:
            child_obj = rel.get("childSObject")
            field = rel.get("field")
            relationshipName = rel.get("relationshipName")

            if not child_obj or not field:
                continue
                
            schema[obj_name]["relationships"]["children"].append({
                                                                    "object":      child_obj,
                                                                    "field":            field,
                                                                    "relationshipName": relationshipName
                                                                })

            if child_obj not in schema:
                warnings.append(f"⚠️ Child object '{child_obj}' not found in schema while processing parent '{obj_name}'")
                continue
            
            schema[child_obj]["relationships"]["parents"].append({
                                                                    "object":      obj_name,
                                                                    "field":            field,
                                                                    "relationshipName": relationshipName
                                                                })

        # 2. References (fields)
        for fname, f_data in obj_data.get("fields", {}).items():
            if "type" not in schema[obj_name]["fields"][fname]:
                continue
            if schema[obj_name]["fields"][fname]["type"] != "reference":
                continue
            if "referenceTo" not in schema[obj_name]["fields"][fname]:
                continue            
            ref_to = schema[obj_name]["fields"][fname]["referenceTo"]

            if not ref_to:
                continue

            if len(ref_to) > 1:
                # Polymorphic
                schema[obj_name]["relationships"]["polymorphic_references"].append({
                    "field": fname,
                    "objects": ref_to
                })
            
                # Inverse: referencedByPolymorphism on each target
                for target in ref_to:
                    
                    if target not in schema:
                        warnings.append(f"⚠️ Target object '{target}' not found in schema while processing parent '{obj_name}'")
                        continue
                        
                    schema[target]["relationships"]["referencedByPolymorphism"].append({
                        "object": obj_name,
                        "field": fname
                    })

            else:
                # Simple reference
                target = ref_to[0]
                schema[obj_name]["relationships"]["references"].append({
                    "field": fname,
                    "object": target
                })

                if target not in schema:
                    warnings.append(f"⚠️ Target object '{target}' not found in schema while processing parent '{obj_name}'")
                    continue
                        
                # Inverse: referencedBy on the target
                schema[target]["relationships"]["referencedBy"].append({
                    "object": obj_name,
                    "field": fname
                })                                                        
            
    logger_debug(f"[SF_SCHEMA_GEN] ✅ relationships analysed!")
    
    return schema, warnings
    
def collect_picklists(schema):
    
    # --- First pass: initialize structure ---
    for obj_name  in schema:
        schema[obj_name].setdefault("picklists", {})
    
    # --- Second pass: collect picklists ---
    for obj_name, obj_data in schema.items():
        for fname, f_data in obj_data.get("fields", {}).items():
            
            if f_data.get("type") != "picklist":
                continue           
            
            global_name = f_data.get("valueSet", {}).get("valueSetName", "")
            if not global_name:
                global_name = f_data.get("valueSetName", "")
                
            picklistValues = f_data.get("picklistValues", [])
            
            if not picklistValues:
                continue
                
            picklist = {}
            
            picklist["picklist_id"]=getPickListId(obj_name,fname)
            picklist["picklist_name"]=fname
            picklist["global_name"]=global_name
            picklist["restrictedPicklist"]=schema[obj_name]["fields"][fname]["restrictedPicklist"]
            picklist["dependentPicklist"]=schema[obj_name]["fields"][fname]["dependentPicklist"]
            values = []
            for v in picklistValues:
                value = {}
                value["value_id"]=f"{fname}{v['value']}"
                value["value"]=v["value"]
                value["label"]=v["label"]
                value["active"]=v["active"]
                values.append(value)

            picklist["values"]=values         
            
            schema[obj_name]["picklists"][picklist["picklist_id"]]=picklist                                 
            
    return schema
    
# ---------------------------------------------------
# Mode 1: From existing schema file
# ---------------------------------------------------
def run_from_file(schema_file=SF_SCHEMA_EXTRACT_FILE,objects_filter=None, preferences_file=SF_PREFERENCES_FILE):
    
    logger_debug(f"[SF_SCHEMA_GEN] Instrumentation performed on existing SF extract file : {schema_file}")
    
    schema = load_json_file(schema_file,defaultVal={})

    schema, warnings = prepare_schema(schema)
    
    for w in warnings:
        logger_debug(f"[SF_SCHEMA_GEN] ⚠️ {w}")
        
    preferences = load_preferences(preferences_file)
    
    if preferences:
        schema, warnings = apply_preferences(schema, preferences)

        out_file = unix_path(OUTPUT_DIR, SF_SCHEMA_INSTRUMENTED_FILE)

        save_json_to_file(schema,out_file)

        logger_debug(f"[SF_SCHEMA_GEN] ✅ Preferred schema generated: {out_file}")
        for w in warnings:
            logger_debug(f"[SF_SCHEMA_GEN] ⚠️ {w}")
            
        export_object_fields(schema,expand=False, output_dir=OUTPUT_DIR,requiredOnly=True)
        
        logger_debug(f"[SF_SCHEMA_GEN] ✅ Instrumantation from file done!")

# ---------------------------------------------------
# Mode 2: From Salesforce directly
# ---------------------------------------------------
def run_from_salesforce(objects_filter=None, preferences_file=SF_PREFERENCES_FILE, sfextractonly=False):
    
    logger_debug(f"[SF_SCHEMA_GEN] Instrumentation from SalesForce Schema...")
    
    sf = Salesforce(
                    instance_url=SF_LOGIN_URL,
                    username=appSecurity.sf_usr_name,
                    password=appSecurity.sf_usr_pwd,
                    security_token=appSecurity.sf_usr_token,
                    domain='test')
    schema = {}
    
    now = datetime.utcnow().strftime("%Y-%m-%d")
    
    all_objects = sf.describe()["sobjects"]
    
    logger_debug(f"[SF_SCHEMA_GEN] ✅ Got Saleforce objects list!")
    
    if objects_filter:
        target_objects = [obj for obj in all_objects if obj["name"] in objects_filter]
    else:
        target_objects = all_objects

    logger_debug(f"[SF_SCHEMA_GEN] Get description for each SF object...")
    
    for obj in target_objects:
        obj_name = obj["name"]

        try:
            desc = getattr(sf, obj_name).describe()
        except Exception as e:
            logger_debug(f"[SF_SCHEMA_GEN] ⚠️ Impossible to describe {obj_name}: {e}")
            continue

        # --- META objet ---
        object_meta = desc.copy()
        if "fields" in object_meta:
            del object_meta["fields"]
        object_meta["lastExtract"] = now
        # --- CHAMPS ---
        fields_info = {}
        for field in desc["fields"]:
            field_data = field.copy()  # on garde toutes les métadonnées SF
            field_data["lastExtract"] = now
            fields_info[field["name"]] = field_data

        schema[obj_name] = {
                            "_meta": object_meta,
                            "fields": fields_info,
                            }

    logger_debug(f"[SF_SCHEMA_GEN] ✅ SF Objects description done! saving SF schema...")
    
    out_file = unix_path(OUTPUT_DIR, SF_SCHEMA_EXTRACT_FILE)
    
    save_json_to_file(schema,out_file)        
        
    schema, warnings = prepare_schema(schema)

    for w in warnings:
        logger_debug(f"[SF_SCHEMA_GEN] ⚠️ {w}")
        
    if sfextractonly: return
    
    preferences = load_preferences(preferences_file)
    
    logger_debug(f"[SF_SCHEMA_GEN] Applying instrumentation...")
    
    if preferences:
        schema, warnings = apply_preferences(schema, preferences)

        out_file = unix_path(OUTPUT_DIR, SF_SCHEMA_INSTRUMENTED_FILE)
        
        save_json_to_file(schema,out_file)
        
        logger_debug(f"[SF_SCHEMA_GEN] ✅ Preferred schema generated from Salesforce: {out_file}")
        for w in warnings:
            logger_debug(f"[SF_SCHEMA_GEN] ⚠️ {w}")
            
        export_object_fields(schema,expand=False, output_dir=OUTPUT_DIR,requiredOnly=True)
        
        logger_debug(f"[SF_SCHEMA_GEN] ✅ Instrumentation from SalesForce Schema done!")

def main(argv=None):
    import argparse
    
    from context_manager import set_client_context, NO_SECRET

    set_client_context(-1,NO_SECRET,logger_debug,logger_debug,logger_debug,logger_debug,None)
    
    default_file_path = unix_path(OUTPUT_DIR, SF_SCHEMA_EXTRACT_FILE)
    
    parser = argparse.ArgumentParser(description="Generate preferred Salesforce schema")
    
    parser.add_argument(
        "--mode",
        choices=["file", "sf"],
        default="file",
        help="Mode to run the script: 'file' = from local schema, 'sf' = from Salesforce"
    )
    parser.add_argument(
        "--schema",
        default=default_file_path,
        help="Path to local schema file (used if mode=file)"
    )
    parser.add_argument(
        "--pwd",
        default=None,
        help="pwd for decrypting secrets in env file"
    )    
    parser.add_argument(
        "--preferences",
        default=SF_PREFERENCES_FILE,
        help="Path to preferences file"
    )
    parser.add_argument(
        "--objects",
        nargs="+",
        help="List of objects to process (optional)"
    )
    
    parser.add_argument(
        "--sfextractonly",
        action='store_true',
        help="Extract only the SF schema from server, no instrumentalisation."
    )

    if not argv:
        args = parser.parse_args()
    else:
        args = parser.parse_args(argv)
    
    if args.mode == "file":
        run_from_file(schema_file=args.schema,objects_filter=args.objects, preferences_file=args.preferences)
    else:
        appSecurity.set_env_security_variable(args.pwd)
        
        if not appSecurity.sf_usr_name:
            if not appSecurity.decrypt_credentials():
                if not args.pwd:
                    logger_debug("[SF_SCHEMA_GEN] No pwd provided! use option --pwd")
                return
                
        run_from_salesforce(
            objects_filter=args.objects,
            preferences_file=args.preferences,
            sfextractonly=args.sfextractonly
        )
        
# ---------------------------------------------------
# Example execution
# ---------------------------------------------------
if __name__ == "__main__":
    main()
