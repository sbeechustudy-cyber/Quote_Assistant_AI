# encrypt_secrets.py
# Usage:
#   python encrypt_secrets.py
#
# It will prompt for a password and then for JSON secrets.
# Output: single base64 string containing salt|nonce|ciphertext which you can copy.

import json
import base64
import getpass
import os
import sys
import argparse
from typing import Union
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
if __name__ == "__main__":
    from secret_definition import ENV_PATH, APP_CREDENDIALS_KEY, check_expectations, check_expectations, get_json_sample, get_empty_json_dict
else:
    from utils.secret_definition import ENV_PATH, APP_CREDENDIALS_KEY, check_expectations, check_expectations, get_json_sample, get_empty_json_dict
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tools import unix_path, setup_logger, load_json_file, read_file, save_json_to_file, delete_file

MODULE_DIR = os.path.dirname(__file__)
DEFAULT_SECRETFILE_TO_ENCRYPT = 'secret.json'
DEFAULT_SECRETFILE_TO_ENCRYPT_PATH = unix_path(MODULE_DIR, DEFAULT_SECRETFILE_TO_ENCRYPT)

logger = setup_logger()

def derive_key(password: bytes, salt: bytes, iterations=200_000):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password)

def derive_key2(pwd: str, privacy_secret: str) -> bytes:
    salt = privacy_secret.encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(pwd.encode("utf-8")))
    return key
    
def encrypt(secrets: Union[str, bytes], password: str,decode_utf = True) -> Union[str, bytes]:
    
    return_str = isinstance(secrets, str)
    if return_str:
        data = secrets.encode("utf-8") 
    else:
        data = secrets   
    
    password_b = password.encode("utf-8")
    salt = os.urandom(16)
    key = derive_key(password_b, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, data, None)
    blob = salt + nonce + ct
    return base64.urlsafe_b64encode(blob).decode("utf-8") if decode_utf else blob

def main(argv=None):

    from context_manager import set_client_context, NO_SECRET

    set_client_context(-1,NO_SECRET,print,print,print,print,None)

    jsonHlp = f"Json file use for getting secrets to encrypt (by default it is '{DEFAULT_SECRETFILE_TO_ENCRYPT}' in the same folder). If absent, will read from stdin."
    
    parser = argparse.ArgumentParser(description="Encrypt secrets then generate env file.")
    parser.add_argument("--json", action='store_true', help=jsonHlp)
    parser.add_argument('--pwd', default=None, help='pwd for protecting secrets')
    
    if not argv:
        args = parser.parse_args()
    else:
        args = parser.parse_args(argv)
    
    data= None
    values = None
    if args.json:
        
        if not os.path.exists(DEFAULT_SECRETFILE_TO_ENCRYPT_PATH):
            print(f"No {DEFAULT_SECRETFILE_TO_ENCRYPT} file provided, an empty one has been created for you ! ")
            secrets = get_empty_json_dict()
            save_json_to_file(secrets,DEFAULT_SECRETFILE_TO_ENCRYPT_PATH)
            return
        else:
            try:
                # optional validation
                secrets=load_json_file(DEFAULT_SECRETFILE_TO_ENCRYPT_PATH)
                plainTextSecret = read_file(DEFAULT_SECRETFILE_TO_ENCRYPT_PATH)
            except Exception as e:
                logger.debug("Invalid JSON:", e)
                logger.debug(f"example of use: {get_json_sample()}")
                return
    else:
        print("Paste your secrets as valid JSON (one line or multiple). End with EOF (Ctrl+Z then Enter on Windows).")
        print(f"example of use: {get_json_sample()}")
        plainTextSecret = sys.stdin.read()
        if not plainTextSecret.strip():
            logger.debug("No input provided. Exiting.")
            return
        try:
            # optional validation
            secrets = json.loads(plainTextSecret)
        except Exception as e:
            logger.debug("Invalid JSON:", e)
            return

    if not args.pwd:
        password = getpass.getpass("Password to encrypt with: ")
        password2 = getpass.getpass("Confirm password: ")
        if password != password2:
            print("Passwords do not match. Exiting.")
            return
    else:
        password = args.pwd

    sanityCheckKo = False

    if not check_expectations(secrets,'Encrypt'):
        logger.debug(f"[Encrypt] 🚨 Warning please provide required secret to encrypt!")
        return

    cipher = encrypt(plainTextSecret, password)
    
    if cipher:

        print("\nEncrypted ciphertext (copy this string):\n")
        print(cipher)
        print("\nKeep that ciphertext safe. It does NOT contain the password; you will need the password to decrypt.")

        with open(ENV_PATH, "w") as f:
            for k,v in secrets.items():
                f.write(f"{k}={encrypt(v, password)}\n")
            f.write(f"{APP_CREDENDIALS_KEY}={cipher}\n")
            
        if args.json: 
            print("It is advised to delete your secret file for now.\nDo you confirm the deletion? \n(Y)es or (N)o.")
            response = sys.stdin.readline().strip()
            if not response or 'y' not in response.lower():
                print("No file deleted, don't let your secret file on your disk!")
            else:
                if delete_file(DEFAULT_SECRETFILE_TO_ENCRYPT_PATH):
                    print(f"Input file {DEFAULT_SECRETFILE_TO_ENCRYPT} has been deleted !")
                else:
                    print(f"Deletion error! Input file {DEFAULT_SECRETFILE_TO_ENCRYPT} still present !")

if __name__ == "__main__":
    main()
