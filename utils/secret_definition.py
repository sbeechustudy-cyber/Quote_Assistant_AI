import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tools import unix_path, setup_logger, make_dir

logger = setup_logger()

MODULE_DIR = os.path.dirname(__file__)
ENV_PATH = unix_path(MODULE_DIR, "./gen/.env")

APP_CREDENDIALS_KEY  = 'APP_CREDENDIALS'

SECRET_KEY_NAMES = {"SF_USR_NAME"          : "me@example.com", 
                    "SF_USR_PWD"           : "SuperSecretPwd!", 
                    "SF_USR_TOKEN"         : "xyz123", 
                    "JIRA_USR_NAME"        : "me@example.com",
                    "JIRA_USR_TOKEN"       : "xyz123",
                    "AI_DATA_PWD"          : 'mysuperpwdforaiassistantoutput',
                    "DB_SQL_SF_PWD"        : "SuperSecret!!",
                    "DB_SQL_PRICELIST_PWD" : 'mysuperpwdfordb'}
                    
secret_keys = list(SECRET_KEY_NAMES.keys())

make_dir(ENV_PATH)

def check_expectations(secrets,prefix="Decrypt"):
    sanityCheckOk = True

    if not secrets or all(v in (None, '') for v in secrets.values()):
       logger.debug(f"[{prefix}] 🔓 No secret provided !")
       return False

    for k in SECRET_KEY_NAMES:
        if k not in secrets:
            sanityCheckOk = False
            logger.debug(f"[{prefix}] 🚨 Warning key:{k} is missing from input!")
        elif secrets[k]=='' or secrets[k] is None:
            logger.debug(f"[{prefix}] 🚨 Warning empty secret for key:{k}")
            sanityCheckOk = False
        else:
            logger.debug(f"[{prefix}] 📜 Got secret for key:{k}")

    return sanityCheckOk
        
def get_empty_json_dict():
    empty_secret = {}
    for k in SECRET_KEY_NAMES:
        empty_secret[k]=''
        
    return empty_secret

def get_json_sample():
    sample = "{"
    last_key = list(SECRET_KEY_NAMES.keys())[-1]
    for k,v in SECRET_KEY_NAMES.items():
        sample = sample + f"\"{k}\": \"{v}\""
        if k != last_key:
            sample = sample + ','
        else:
            sample = sample + '}'
            
    return sample