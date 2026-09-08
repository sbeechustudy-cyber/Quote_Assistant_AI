import os
from cryptography.exceptions import InvalidTag
from tools import setup_logger
import utils.secret_definition as sd
from utils.decrypt_secret import get_credentials_from_env, decrypt
from utils.encrypt_secret import encrypt
import secrets
from context_manager import get_current_client, get_context, NO_SECRET

appPwd = os.environ.get("APP_AI_ASSISTANT_KEY")

NO_SECRET            = NO_SECRET

sf_usr_name          = None
sf_usr_pwd           = None
sf_usr_token         = None
jira_usr_name        = None
jira_usr_token       = None
ai_data_pwd          = None
db_sql_sf_pwd        = None
db_sql_pricelist_pwd = None

app_credentials = None

logger = setup_logger()

def generate_secret():
    return secrets.token_hex(16)
    
def get_client_secret():
    
    cid = get_current_client()
    ctx = get_context(cid)
    
    client_secret = ctx["client_secret"] if ctx else NO_SECRET   
    
    return client_secret
    
def is_private_mode():
    return get_client_secret() != NO_SECRET    

def set_env_security_variable(pwd: str):
    global appPwd
    
    if pwd:
        os.environ["APP_AI_ASSISTANT_KEY"] = pwd
        appPwd = pwd
        logger.debug("[AppSecurity] 🔒 Environment set with pwd from cmd line!")
                    
def decrypt_credentials():
    global appPwd, sf_usr_name, sf_usr_pwd, sf_usr_token,jira_usr_name, jira_usr_token, logger, app_credentials, ai_data_pwd, db_sql_sf_pwd

    if not appPwd:
        logger.debug("[AppSecurity] 🚨 Error environnement variable \"APP_AI_ASSISTANT_KEY\" is not set !!")
        return False
    
    if not sf_usr_name:
        app_credentials = get_credentials_from_env(appPwd)
    else:
        logger.debug("[AppSecurity] 🔓 Secrets already got!!")

    if app_credentials is None:
        logger.debug("[AppSecurity] 🚨 Error no secret available !! check your env file or use encrypt_secret script.")
        return False
    else:
        logger.debug("[AppSecurity] 🔓 Got secrets !!")

    for key in sd.secret_keys:
        globals()[key.lower()] = app_credentials[key]

    return True
    
def decrypt_func(dataToDecrypt,decode_utf,clientSecret=None):
    global ai_data_pwd
    
    data = None
    
    if not ai_data_pwd:
        if not decrypt_credentials(): raise ValueError("Pwd required for decryption!")

    if not dataToDecrypt:
        logger.warning(f"[AppSecurity] 🔒 Warning no data to decrypt!!")
        raise ValueError("No data to decrypt!")
    
    try:
        pwd=f"{ai_data_pwd}_{clientSecret}"
        data = decrypt(dataToDecrypt,pwd,decode_utf=decode_utf)
    except InvalidTag as e:
        if clientSecret:
            logger.warning(f"[AppSecurity] 🔒 Invalitag with customer secret, let's try without...")
            return decrypt_func(dataToDecrypt,decode_utf,clientSecret=None)
        else:
            logger.error("[AppSecurity] ❌ InvalidTag: authentication failed.")
            raise        
    except Exception as e:
        logger.error(f"[AppSecurity] ❌ ERROR decrypting data, exception '{type(e).__name__}' raised with {e}")
        raise  
    
    return data

def encrypt_func(dataToEncrypt,decode_utf):
    global ai_data_pwd
    
    data = None
    
    if not ai_data_pwd:
        if not decrypt_credentials(): raise ValueError("Pwd required for encryption!")
    
    if not dataToEncrypt:
        logger.warning(f"[AppSecurity] 🔒 Warning no data to encrypt!!")
        raise ValueError("No data to encrypt!")

    try:
        client_secret = get_client_secret()
        pwd=f"{ai_data_pwd}_{client_secret}"
        data = encrypt(dataToEncrypt,pwd,decode_utf=decode_utf)
    except Exception as e:
        logger.error(f"[AppSecurity] ❌ ERROR encrypting data, exception '{type(e).__name__}' raised with {e}")
        raise  
    
    return data
