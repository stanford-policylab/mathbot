import os
import tempfile
import pandas as pd

curr_dir_path = os.path.dirname(os.path.realpath(__file__))


def read_txt(filename):
    df = pd.read_csv(os.path.join(curr_dir_path, filename), sep=" ", header=None)
    return df.loc[:, 0].tolist()

class BaseConfig:
    # session secret key
    SECRET_KEY = 'YOUR_SECRET_KEY'
    curr_dir_path = os.path.dirname(os.path.realpath(__file__))
    # server_config = json.load(open(os.path.join(curr_dir_path, "server_config.json")))
    # quiz_config = json.load(open(os.path.join(curr_dir_path, "static/resources/json/quiz.json"), encoding='utf-8'))

    APP_ROOT = os.path.dirname(os.path.abspath(__file__))

    DATABASE = os.path.join(APP_ROOT, 'exp_data.db')

    # Mturk related
    EXTERNAL_SUBMIT_URL = "https://www.mturk.com/mturk/externalSubmit" \
        # if ( server_config['sandbox_or_real'] == "real") else "https://workersandbox.mturk.com/mturk/externalSubmit"

    # EXP_DB_TABLE = 'test'

    # EXP_DB_FIELDS = os.path.join(APP_ROOT, 'config', server_config['fields'])

    # Group name
    GROUP_NAME = ["MathBot", "Khan Video"]

    # Conversation saving directory
    CONV_SAVE_DIR = os.path.join(APP_ROOT, 'saved_conversation')

    # Heatmap saving directory
    HEATMAP_SAVE_DIR = os.path.join(APP_ROOT, 'saved_heatmap')

    DEBUG = True
    APP_LOG_PATH = os.path.join(APP_ROOT, 'app.log')

    # Database
    DB_PATH = "exp.db"  # todo: Fix this
    DB_DEBUG = True

    # Context Table
    CONTEXT_TABLE = "context"
    CONTEXT_SCHEMA = ['time_since_starting_lesson', 'next_test_question', 'skipped_last_question', 'isomorphed_last_question', 'num_attempts_last_question', 'last_test_question_time', 'unique_user_id', 'type_speed', 'which_policy', 'pre_q']

    # Reward Table
    REWARD_TABLE = "reward"
    REWARD_SCHEMA = ['test_question', 'unique_user_id', 'reward']
    
    # Action Table
    ACTION_TABLE = "action"
    ACTION_SCHEMA = ['test_question', 'unique_user_id', 'isomorph', 'skip_concept']

    # Experiments table
    EXP_TABLE = "exp"
    EXP_SCHEMA = read_txt("exp_form_fields.txt")

    # User list
    BLACKLIST = set()#read_txt("user_blocklist.txt"))
    WHITELIST = set()#read_txt("user_allowlist.txt"))


class TestConfig(BaseConfig):
    # session secret key
    SECRET_KEY = 'YOUR_SECRET_KEY'
    curr_dir_path = os.path.dirname(os.path.realpath(__file__))
    # server_config = json.load(open(os.path.join(curr_dir_path, "server_config.json")))
    # quiz_config = json.load(open(os.path.join(curr_dir_path, "static/resources/json/quiz.json"), encoding='utf-8'))

    APP_ROOT = tempfile.gettempdir()

    DATABASE = os.path.join(APP_ROOT, 'exp_data.db')

    # Mturk related
    EXTERNAL_SUBMIT_URL = "https://www.mturk.com/mturk/externalSubmit" \
        # if ( server_config['sandbox_or_real'] == "real") else "https://workersandbox.mturk.com/mturk/externalSubmit"

    # EXP_DB_TABLE = 'test'

    # EXP_DB_FIELDS = os.path.join(APP_ROOT, 'config', server_config['fields'])

    # Group name
    GROUP_NAME = ["MathBot", "Khan Video"]

    # Conversation saving directory
    CONV_SAVE_DIR = os.path.join(APP_ROOT, 'saved_conversation')

    # Heatmap saving directory
    HEATMAP_SAVE_DIR = os.path.join(APP_ROOT, 'saved_heatmap')

    DEBUG = True
    APP_LOG_PATH = os.path.join(APP_ROOT, 'app.log')

    # Database
    DB_PATH = "exp.db"  # todo: Fix this
    DB_DEBUG = True
    
    # Context Table
    CONTEXT_TABLE = "context"
    CONTEXT_SCHEMA = ['time_since_starting_lesson', 'next_test_question', 'skipped_last_question', 'isomorphed_last_question', 'num_attempts_last_question', 'last_test_question_time', 'unique_user_id', 'type_speed']

    # Reward Table
    REWARD_TABLE = "reward"
    REWARD_SCHEMA = ['test_question', 'unique_user_id', 'reward']
    
    # Action Table
    ACTION_TABLE = "action"
    ACTION_SCHEMA = ['test_question', 'unique_user_id', 'isomorph', 'skip_concept']

    # Experiments table
    EXP_TABLE = "exp"
    EXP_SCHEMA = read_txt("exp_form_fields.txt")

    # User list
    BLACKLIST = set()#(read_txt("user_blocklist.txt"))
    WHITELIST = set()#(read_txt("user_allowlist.txt"))


# Debug purpose
if __name__ == "__main__":
    BLACKLIST = set(read_txt("user_blocklist.txt"))
    print(BLACKLIST)
