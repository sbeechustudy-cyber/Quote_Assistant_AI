import os
import json
if __name__ == "__main__":
    from sf_schema_generation import SF_PREFERRED_OBJECTS_FILE_PATH
else:
    from utils.sf.sf_schema_generation import SF_PREFERRED_OBJECTS_FILE_PATH
from tools import unix_path, load_json_file, setup_logger

MODULE_DIR = os.path.dirname(__file__)
logger = setup_logger()
all_objects = {}

sf_schema = None

opp_mapping= {
    "Opportunity": {
        "sf_opp_role" : "Opportunity",
        "sf_object"   : "Opportunity"
    },
    "PrimaryContact" : {
        "sf_opp_role" : "PrimaryContact",
        "sf_object"   : "Contact",
        "sf_relationship_path": [
            {"object": "OpportunityContactRole","field": "ContactId","relation_type": "referencedBy"},
            {"object": "Opportunity","field": "ContactId","relation_type": "referencedBy"}
        ]
    },
    "Account": {
        "sf_opp_role" : "Account",
        "sf_object"   : "Account",
        "sf_relationship_path": [
            {"object": "Contact", "field": "AccountId", "relation_type": "references"},
            {"object": "Opportunity","field": "ContactId","relation_type": "referencedBy"}
        ]
    },
    "PrimaryContactRole": {
        "sf_opp_role" : "PrimaryContactRole",
        "sf_object"   : "OpportunityContactRole",
        "sf_relationship_path": [
            {"object": "Contact","field": "ContactId","relation_type": "referencedBy"},
            {"object": "Opportunity","field": "OpportunityId","relation_type": "referencedBy"}
        ]
    },
    "ECU": {
        "sf_opp_role": "ECU",                        
        "sf_object"  : "SF42_ECU__c",
        "sf_relationship_path": [
            {"object": "Opportunity","field": "SF42_ECU__c","relation_type": "referencedBy"}
        ]
    },
    "OEM": {
        "sf_opp_role": "OEM", 
        "sf_object"  : "Account",
        "sf_relationship_path": [
            {"object": "Opportunity","field": "SF42_OEM__c","relation_type": "referencedBy"}
        ]
    },
    "CarPlatform": {
        "sf_opp_role": "CarPlatform", 
        "sf_object"  : "SF42_Platform__c",
        "sf_relationship_path": [
            {"object": "Opportunity","field": "Car_Platform__c","relation_type": "referencedBy"}
        ]
    }
}

def get_sf_object_type_for_opp_role(sf_opp_role):
    if sf_opp_role in opp_mapping:
        return opp_mapping[sf_opp_role]["sf_object"]

    logger.debug(f"[SF_OBJ_DESCRIPTOR] ❌ sf_opp_role '{sf_opp_role}' not present in opp_mapping!")
    
    return None
    
def load_objects(root_file=SF_PREFERRED_OBJECTS_FILE_PATH):
    global all_objects
    
    all_objects = {}
    
    data = load_json_file(root_file, defaultVal={})
    
    if data:
        objs = data.get("objects")

        for obj_name, obj_filepath in objs.items():
            logger.debug(f"[SF_OBJ_DESCRIPTOR] processing SF object \"{obj_name}\" from path {obj_filepath}...")
            path = unix_path(MODULE_DIR,obj_filepath)
            
            obj = load_json_file(path, defaultVal={})
            
            all_objects[obj_name] = obj
        
    return all_objects

def get_field_for_object(obj_name, field_name, schema = None):
    global sf_schema
    
    if not sf_schema:
        sf_schema = load_objects()
    
    if not schema: schema = sf_schema

    if obj_name in schema:
        if 'fields' in schema[obj_name]:
            fields = schema[obj_name]['fields']
            for f_data in fields:
                if field_name in f_data:
                    return f_data[field_name]
            logger.debug(f"[SF_OBJ_DESCRIPTOR] ❌ For obj_name '{obj_name}' field '{field_name}' not present in schema!")
        else:
            logger.debug(f"[SF_OBJ_DESCRIPTOR] ❌ For obj_name '{obj_name}' 'fields' not present in schema! field_name={field_name}")
    else:
        logger.debug(f"[SF_OBJ_DESCRIPTOR] ❌ obj_name '{obj_name}' not present in schema! field_name = {field_name}")
    
    return None
    
def get_type_for_field_in_object(obj_name, field_name, schema = None):
    field = get_field_for_object(obj_name,field_name,schema=schema)
    return field['type'] if field else None

def get_label_for_field_in_object(obj_name, field_name, schema = None):
    field = get_field_for_object(obj_name,field_name,schema=schema)
    return field['label'] if field else None
    
def get_inlineHelp_for_field_in_object(obj_name, field_name, schema = None):
    field = get_field_for_object(obj_name,field_name,schema=schema)
    return field['inlineHelpText'] if field else None
    
def get_default_value_for_field_in_object(obj_name, field_name, schema = None):
    field = get_field_for_object(obj_name,field_name,schema=schema)
    return field['defaultValue'] if field else None
    
def is_mandatory_field_in_object(obj_name, field_name, schema = None) -> bool:
    field = get_field_for_object(obj_name,field_name,schema=schema)
    return field['required'] if field else None    

def is_picklist_field_in_object(obj_name, field_name, schema = None) -> bool:
    field = get_field_for_object(obj_name,field_name,schema=schema)
    return ('picklist_id' in field)    
    
def get_picklist_data_for_field_in_object(obj_name, field_name, schema = None):
    global sf_schema
    
    field = get_field_for_object(obj_name,field_name,schema=schema)
    if 'picklist_id' in field:
        picklistId = field['picklist_id']
        if not schema: schema = sf_schema
        if 'picklists' in schema[obj_name]:
            if picklistId in schema[obj_name]['picklists']:
                return schema[obj_name]['picklists'][picklistId]
                
    return None

def get_picklist_labels(picklist):
    if picklist:
        if 'values' in picklist:
            labels = []
            values = picklist['values']
            for v in values:
                if v['active']:
                    labels.append(v['label'])
                    
            
            return labels

    return None 

def get_picklist_labels_for_field_in_object(obj_name, field_name, schema = None):
    picklist = get_picklist_data_for_field_in_object(obj_name,field_name,schema=schema)
    return get_picklist_labels(picklist)

def get_picklist_values(picklist):
    if picklist:
        if 'values' in picklist:
            labels = []
            values = picklist['values']
            for v in values:
                if v['active']:
                    labels.append(v['value'])
                    
            
            return labels
    
    return None 

def get_picklist_values_for_field_in_object(obj_name, field_name, schema = None):
    picklist = get_picklist_data_for_field_in_object(obj_name,field_name,schema=schema)
    return get_picklist_values(picklist)
    
def is_restricted_picklist(picklist) -> bool:
    if picklist:
        if 'restrictedPicklist' in picklist:
            return picklist['restrictedPicklist']
    
    return False 
    
def is_restricted_picklist_for_field_in_object(obj_name, field_name, schema = None) -> bool:
    picklist = get_picklist_data_for_field_in_object(obj_name,field_name,schema=schema)
    return is_restricted_picklist(picklist)
    
def get_all_fields_for_obj(objName):
    fields = {}
    
    if objName in all_objects:
        
        obj = all_objects.get(objName)
        
        fields = obj.get("fieldsName",{})

    return fields

def get_preferred_fields_for_obj(objName):
    pref_fields = []
    
    if objName in all_objects:
        obj = all_objects.get(objName)

        fields = obj.get("fields",{})

        for field_entry in fields:
            for f_name in field_entry:
                f_data = field_entry[f_name]
                if(f_data['preferred']):
                    pref_fields.append(f_name)

    return pref_fields
    
def get_required_fields_for_obj1(objName):
    pref_fields = []
    
    if objName in all_objects:
        obj = all_objects.get(objName)

        fields = obj.get("fields",{})

        for field_entry in fields:
            for f_name in field_entry:
                f_data = field_entry[f_name]
                if(f_data['required']):
                    pref_fields.append(f_name)

    return pref_fields
    
def get_required_fields_for_obj(objName):
    pref_fields = {}
    
    if objName in all_objects:
        obj = all_objects.get(objName)

        fields = obj.get("fields",{})

        for field_entry in fields:
            for f_name in field_entry:
                f_data = field_entry[f_name]
                if(f_data['required']):
                    key = {
                        "name": f_name,
                        "sqlType": f_data["sqlType"],
                    }
                    pref_fields[f_name]=key

    return pref_fields
    
if __name__ == "__main__":
    schema = load_objects()
    print(schema["Opportunity"])
    for field in schema["Opportunity"]["fields"]:
        #print(field)
        for f_name, f_data in field.items():
            print(f_name)
            print(f_data["sqlType"])
    key_fields = schema["Opportunity"]["fields"]
    #filtered_rec = {k: rec.get(k, "") for k in key_fields}
    #print(filtered_rec)
    #print(json.dumps(schema, indent=2))
    print(get_all_fields_for_obj('OpportunityFieldHistory'))
    print(get_required_fields_for_obj('Opportunity'))
    
    print(get_type_for_field_in_object("Opportunity","MicrocontrollerManufacturer__c"))
    print(get_default_value_for_field_in_object("Opportunity","MicrocontrollerManufacturer__c"))
    print(is_mandatory_field_in_object("Opportunity","MicrocontrollerManufacturer__c"))
    picklist=get_picklist_data_for_field_in_object("Opportunity","MicrocontrollerManufacturer__c")
    print(get_picklist_labels_for_field_in_object("Opportunity","MicrocontrollerManufacturer__c"))
    print(get_picklist_values(picklist))
    print(is_restricted_picklist(picklist))
    
    
