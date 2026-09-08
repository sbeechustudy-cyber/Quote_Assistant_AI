import sys
import os
import io
import pandas as pd
import argparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import tools
import appSecurity
from context_manager import set_client_context

MODULE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = tools.unix_path(MODULE_DIR, "./gen")

logger       = tools.setup_logger()
logger_debug = logger.debug

def main(argv=None):
    tools.make_dir(OUTPUT_DIR)
    secret = appSecurity.generate_secret()

    set_client_context(-1,secret,logger_debug,logger_debug,logger_debug,logger_debug,None)

    parser = argparse.ArgumentParser(description="Purpose of this script is to test encryption & decryption of files")
    parser.add_argument('--pwd', default=None, help='pwd for decrypting secrets in env file')
    
    if not argv:
        args = parser.parse_args()
    else:
        args = parser.parse_args(argv)

    appSecurity.set_env_security_variable(args.pwd)
    
    if not appSecurity.ai_data_pwd:
        if not appSecurity.decrypt_credentials():
            if not args.pwd:
                logger_debug("[ENCRYP_NON_REG_TEST] No pwd provided! use option --pwd")
            return False

    logger_debug("[ENCRYP_NON_REG_TEST] Step 1 load json")
    data = tools.load_json_file(tools.unix_path(MODULE_DIR,"../test/questionnaire-output.json"),decrypt_func_cb=appSecurity.decrypt_func,clientSecret=secret)
    #logger_debug("[ENCRYP_NON_REG_TEST]  json plain text: ",data)
    logger_debug("[ENCRYP_NON_REG_TEST] Step 2 encrypt json")
    tools.save_json_to_file(data,tools.unix_path(OUTPUT_DIR,"./test_encrypt.json"),encrypt_func_cb=appSecurity.encrypt_func)
    logger_debug("[ENCRYP_NON_REG_TEST] Step 3 load encrypted json")
    data = tools.load_json_file(tools.unix_path(OUTPUT_DIR,"./test_encrypt.json"),decrypt_func_cb=appSecurity.decrypt_func,clientSecret=secret)
    #logger_debug("[ENCRYP_NON_REG_TEST]  json plain text: ",data)
    logger_debug("[ENCRYP_NON_REG_TEST] Step 4 save paintext json")
    tools.save_json_to_file(data,tools.unix_path(OUTPUT_DIR,"./test_pain_text.json"))
    df = pd.read_csv(tools.unix_path(MODULE_DIR,"../test/price_indication.csv"), sep=";")
    logger_debug("[ENCRYP_NON_REG_TEST] Step 5 save encrypted csv")
    set_client_context(-1,appSecurity.NO_SECRET,logger_debug,logger_debug,logger_debug,logger_debug,None)
    tools.save_df_table(df,tools.unix_path(OUTPUT_DIR,"./test_encrypt.csv"),csv_format=True,encrypt_func_cb=appSecurity.encrypt_func)
    set_client_context(-1,secret,logger_debug,logger_debug,logger_debug,logger_debug,None)

    logger_debug("[ENCRYP_NON_REG_TEST] Step 6 read encrypted csv")

    decrypted_file = tools.read_file(tools.unix_path(OUTPUT_DIR,"./test_encrypt.csv"),
                                      decrypt_func_cb=appSecurity.decrypt_func,
                                      bytesIo = True,
                                      clientSecret=secret)

    logger_debug("[ENCRYP_NON_REG_TEST] Step 7 save paintext csv")
    tools.save_data_to_file(decrypted_file,tools.unix_path(OUTPUT_DIR,"./test_pain_text.csv"))

    logger_debug("[ENCRYP_NON_REG_TEST] Step 8 save encrypted xlsx")
    tools.save_df_table(df,tools.unix_path(OUTPUT_DIR,"./test_encrypt.xlsx"),csv_format=False,encrypt_func_cb=appSecurity.encrypt_func)

    logger_debug("[ENCRYP_NON_REG_TEST] Step 9 read encrypted xlsx")

    decrypted_file = tools.read_file(tools.unix_path(OUTPUT_DIR,"./test_encrypt.xlsx"),
                                     decrypt_func_cb=appSecurity.decrypt_func,
                                     bytesIo = True,
                                     clientSecret=secret)
                               
    logger_debug("[ENCRYP_NON_REG_TEST] Step 10 save paintext xlsx")
    tools.save_data_to_file(decrypted_file,tools.unix_path(OUTPUT_DIR,"./test_pain_text.xlsx"))
    
    return True

if __name__ == "__main__":
    main()