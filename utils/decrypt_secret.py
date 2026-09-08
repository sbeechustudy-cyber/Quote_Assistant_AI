# decrypt_and_set_env.py
# Usage:
#   python decrypt_and_set_env.py
#   Then paste the base64 ciphertext and press Enter (or provide via --cipher TEXT)
#
# It prompts for the password, decrypts, then spawns a new cmd with vars set.

import os
import sys
import json
import base64
import getpass
import argparse
import subprocess
from typing import Union
from dotenv import load_dotenv, dotenv_values
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
if __name__ == "__main__":
    from secret_definition import ENV_PATH, SECRET_KEY_NAMES, APP_CREDENDIALS_KEY, check_expectations, check_expectations, get_empty_json_dict
else:
    from utils.secret_definition import ENV_PATH, SECRET_KEY_NAMES, APP_CREDENDIALS_KEY, check_expectations, check_expectations, get_empty_json_dict
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tools import unix_path, setup_logger

logger = setup_logger()

MODULE_DIR = os.path.dirname(__file__)
            
def derive_key(password: bytes, salt: bytes, iterations=200_000):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password)

def decrypt(b64blob: Union[str, bytes], password: str,decode_utf = True) -> Union[str, bytes]:
    
    return_str = isinstance(b64blob, str)
    
    if return_str:
        try:
            blob = base64.urlsafe_b64decode(b64blob)
        except Exception:
            raise ValueError("Invalid base64 ciphertext")
    elif isinstance(b64blob, (bytes, bytearray)):
        blob = bytes(b64blob)
    else:
        raise TypeError("blob must be str or bytes")
        
    if len(blob) < 16 + 12 + 16:
        raise ValueError("Ciphertext too short / corrupted")

    salt = blob[0:16]
    nonce = blob[16:28]
    ct = blob[28:]
    key = derive_key(password.encode("utf-8"), salt)
    aesgcm = AESGCM(key)
    try:
        pt = aesgcm.decrypt(nonce, ct, None)
    except InvalidTag as e:
        logger.error("[Decrypt] ❌ InvalidTag: authentication failed (wrong password or corrupted data).")
        raise        
    except Exception as e:
        logger.error(f"[Decrypt] ❌ aesgcm decrypt call raised: {type(e).__name__} {e}")
        raise
        
    return pt.decode("utf-8") if decode_utf else pt
        

def spawn_cmd_with_env(secrets: dict):
    # Build command that sets variables and drops to cmd interactive shell.
    # We'll build a single string with multiple 'set' commands then 'cmd' to open sub-shell.
    # Use 'cmd /k' to keep shell open after executing commands.
    # Avoid writing to disk; do everything via command line.
    set_cmds = []
    for k, v in secrets.items():
        # sanitize: only simple env var names
        if not k or any(c in k for c in ('=', '\n', '\r')):
            continue
        # ensure value is str
        sval = str(v)
        # For safety, escape ^ and % in value for cmd:
        sval = sval.replace("^", "^^").replace("%", "%%")
        set_cmds.append(f'set "{k}={sval}"')
    # join with " & " so cmd executes sequentially
    full = " & ".join(set_cmds)
    # open interactive cmd with those variables already set by using cmd /k "<sets>"
    if not full:
        logger.warning("No variables to set. Launching cmd normally.")
        subprocess.call(["cmd"])
    else:
        subprocess.call(["cmd", "/k", full])

def get_credentials_from_env(password,envfile=ENV_PATH):
    envconf=dotenv_values(envfile)
    return get_credentials(b64_cypher=None,pwd=password,envconf=envconf)
    
def get_credentials(b64_cypher, pwd="azerty", envconf=None):

    secrets = None
    
    if not b64_cypher and not envconf:
        logger.debug("No ciphertext provided. Exiting.")
        return None
        
    if b64_cypher and not envconf:
        
        try:
            plaintext = decrypt(b64_cypher, pwd)
        except Exception as e:
            logger.error(f"[Decrypt] ❌ ERROR decrypting app credentials: {e}")
            return None

        try:
            secrets = json.loads(plaintext)
            if not check_expectations(secrets):
                return None
            else:
                logger.debug(f"[Decrypt] 🔓 App keys have been unlocked!")

        except Exception as e:
            logger.error("[Decrypt] ❌ ERROR: decrypted payload is not valid JSON:", e)
            return None
    else:
        
        if envconf[APP_CREDENDIALS_KEY]:
            secrets = get_credentials(envconf[APP_CREDENDIALS_KEY],pwd=pwd,envconf=None)
            
        if not secrets:
            secrets = get_empty_json_dict()
            for key in SECRET_KEY_NAMES:
                if key in envconf:
                    try:
                        secrets[key] = decrypt(envconf[key], pwd)
                        logger.debug(f"[Decrypt] 🔓 {key} has been unlocked!")
                    except Exception as e:
                        logger.error(f"[Decrypt] 🔒 ERROR decrypting {key}: {e}")
                else:
                    logger.debug(f"[Decrypt] ⚠️ {key} not found in envconf")
            if not check_expectations(secrets):
                return None
            else:
                logger.debug(f"[Decrypt] 🔓 App keys have been unlocked!")
 
    return secrets

def main():
    
    from context_manager import set_client_context, NO_SECRET

    set_client_context(-1,NO_SECRET,print,print,print,print,None)
    
    parser = argparse.ArgumentParser(description="Decrypt secrets and spawn cmd with env vars for the session.")
    parser.add_argument("--cipher", help="Base64 ciphertext string (optional). If absent, will read from stdin.")
    parser.add_argument("--envfile", action='store_true', help="Env file use for getting ciphertext strings. If absent, will read from stdin.")
    parser.add_argument('--pwd', default=None, help='pwd for decrypting secrets')
    
    args = parser.parse_args()

    config = None
    b64    = None
    if args.envfile:
        #load_dotenv(ENV_PATH)
        config = dotenv_values(ENV_PATH)
        try:
            b64 = config[APP_CREDENDIALS_KEY]
        except Exception as e:
            logger.debug("env file key not found, using separate keys:", e)
    elif args.cipher:
        b64 = args.cipher.strip()
    else:
        print("Paste base64 ciphertext then press ENTER (or Ctrl+Z then ENTER to finish input):")
        b64 = sys.stdin.read().strip()
    if not b64 and not config:
        logger.debug("No ciphertext provided. Exiting.")
        return

    if not args.pwd:
        password = getpass.getpass("Password to decrypt: ")
    else:
        password = args.pwd
        
    secrets = get_credentials(b64,pwd=password,envconf=config)

    # Optionally print masked keys summary
    if secrets:
        logger.debug("[Decrypt] 📜 Decrypted secret: %s", ", ".join(f"{k}={v[:6]}..." if 'pwd' not in k.lower() and v else f"{k}=***" if v else f"{k}=void" for k, v in secrets.items()))
        # spawn cmd with env vars set only for that session
        #spawn_cmd_with_env(secrets)
    else:
        logger.debug("[Decrypt] 🔒 missing secret!! check logs fir further details.")
if __name__ == "__main__":
    main()
