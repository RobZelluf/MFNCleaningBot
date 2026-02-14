import time
import requests
import pprint
import datetime
import json
from yaml import load, YAMLError

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def read_yaml_file_and_check_for_items(file_path, required_items):
    try:
        with open(file_path, "r") as f:
            yaml_contents = load(f, Loader)
            yaml_keys = yaml_contents.keys()
            for req_item in required_items:
                if req_item not in yaml_keys:
                    print(f"ERROR: Yaml file {file_path} does not contain item {req_item}")
                    exit(1)
            return yaml_contents
    except OSError as e:
        print(f"ERROR: Unable to open yaml configuration file!\n{e}")
        exit(1)
    except YAMLError as e:
        print(f"ERROR: Unable to parse yaml configuration file!\n{e}")
        exit(1)


def get_telegram_configs():
    configs = read_yaml_file_and_check_for_items("secrets.yaml", ["token", "group_id"])
    return configs["token"], configs["group_id"]


# Telegram stuffö
API_TOKEN, GROUP_ID = get_telegram_configs()
BASE_URL = f"https://api.telegram.org/bot{API_TOKEN}"
SEND_MESSAGE_URL = f"{BASE_URL}/sendMessage"
GET_UPDATES_URL = f"{BASE_URL}/getUpdates"
SET_COMMANDS_URL = f"{BASE_URL}/setMyCommands"


def non_blocking(handler):
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception:
            return None
    return wrapper


@non_blocking
def req_get(*args, **kwargs):
    return requests.get(*args, **kwargs)


def get_updates(offset=None):
    if offset is None:
        res = req_get(f"{GET_UPDATES_URL}")
    else:
        res = req_get(f"{GET_UPDATES_URL}?offset={offset+1}")

    updates = res.json() if res else None
    return updates


def send_message(user, text):
    res = req_get(f"{SEND_MESSAGE_URL}?chat_id={user}&text={text}")
    return res.status_code if res else None


def get_week_number():
    # Compute the weeknumber from today (the -1 is so that a week starts from monday and not sunday)
    return (datetime.date.today().toordinal() - 1) // 7


class CleaningSchedules:
    def __init__(self, config_file_path):
        configs = read_yaml_file_and_check_for_items(config_file_path, ["users", "tasks"])
        self.job_list = configs["tasks"]
        self.users_list = configs["users"]

    def build_jobs_msg(self):
        assigned_task = self._assign_tasks()
        msg = "Cleaning Tasks for this weekend:\n"

        for p, j in assigned_task.items():
            msg += f"- {p}: {self.job_list[j]}\n"

        return msg

    def _assign_tasks(self):
        week_number = get_week_number()
        task = week_number % len(self.users_list)
        assigned_task = {}

        for p in self.users_list:
            assigned_task[p] = task
            task = (task + 1) % len(self.users_list)

        return assigned_task


def get_wakeup_datetime():
    wake_up_day = datetime.date.today().toordinal() + 1
    wake_up_time = datetime.timedelta(hours=8)

    return datetime.datetime.fromordinal(wake_up_day) + wake_up_time


def process_message(msg, schedules):
    if msg["text"] == "/get_tasks":
        pprint.pprint(msg)
        chat_id = msg["chat"]["id"]
        send_message(chat_id, schedules.build_jobs_msg())


def process_updates(updates, schedules):
    last_id = None

    for update in updates:
        if "message" in update:
            process_message(update["message"], schedules)
        last_id = update["update_id"]

    return last_id


def set_commands():
    commands = [{"command": "get_tasks", "description": "Show assigned tasks"}]
    res = req_get(f"{SET_COMMANDS_URL}?commands={json.dumps(commands)}")

    if not res or res.status_code != 200:
        print(f"ERROR: Unable to set bot commands!\n{res.text}")


def main():
    cleaning_schedules = CleaningSchedules("configs.yaml")

    set_commands()
    wakeup_datetime = datetime.datetime.fromordinal(1)
    last_update_id = None

    while True:
        if datetime.datetime.now() > wakeup_datetime:
            today = datetime.date.today().isoweekday()

            print(f"Processing day {today}!")
            if today == 6:
                send_message(GROUP_ID, cleaning_schedules.build_jobs_msg())

            elif today == 7:
                text = f"REMINDER!\n{cleaning_schedules.build_jobs_msg()}"
                send_message(GROUP_ID, text)

            wakeup_datetime = get_wakeup_datetime()

        if datetime.datetime.now().second % 3600 < 90:
            updates = get_updates(last_update_id)
            if updates and updates["ok"]:
                id = process_updates(updates["result"], cleaning_schedules)
                if id is not None:
                    last_update_id = id
            else:
                print(f"ERROR: Failed to get updates from telegram!\n{updates}")

        time.sleep(60)


if __name__ == '__main__':
    main()
