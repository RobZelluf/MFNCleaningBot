import datetime
import json
import logging
from time import sleep

import schedule

import requests
import yaml


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


class CleaningBot:
    def __init__(self):
        secrets = yaml.safe_load(open("secrets.yaml"))

        self.token = secrets["token"]
        self.group_id = secrets["group_id"]

        config = yaml.safe_load(open("configs.yaml"))

        self.users = config["users"]
        self.tasks = config["tasks"]

        self.last_msg_id = None
        self.logger = self.get_logger()

    @staticmethod
    def get_logger():
        logger = logging.getLogger("CleaningBot")
        logger.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        return logger

    def _get_base_url(self):
        return f"https://api.telegram.org/bot{self.token}"

    def _get_command_url(self):
        return f"{self._get_base_url()}/setMyCommands"

    def _get_updates_url(self):
        return f"{self._get_base_url()}/getUpdates"

    def _get_message_url(self):
        return f"{self._get_base_url()}/sendMessage"

    def _assign_tasks(self):
        week_number = (datetime.date.today().toordinal() - 1) // 7
        task = week_number % len(self.users)
        assigned_task = {}

        for p in self.users:
            assigned_task[p] = task
            task = (task + 1) % len(self.users)

        return assigned_task

    def get_updates(self):
        updates_url = self._get_updates_url()

        if self.last_msg_id is not None:
            updates_url = f"{updates_url}?offset={self.last_msg_id + 1}"

        res = req_get(updates_url)
        updates = res.json() if res else None

        return updates

    @non_blocking
    def send_message(self, chat_id, text):
        self.logger.debug(f"Sending message to {chat_id}")

        message_url = self._get_message_url()
        res = requests.get(f"{message_url}?chat_id={chat_id}&text={text}")

        return res.status_code if res else None

    def build_jobs_msg(self):
        assigned_task = self._assign_tasks()
        msg = "Cleaning Tasks for this weekend:\n"

        for p, j in assigned_task.items():
            msg += f"- {p}: {self.tasks[j]}\n"

        return msg

    def process_message(self, msg):
        if msg["text"] == "/get_tasks":
            chat_id = msg["chat"]["id"]
            self.send_message(chat_id, self.build_jobs_msg())

    def process_updates(self, updates):
        last_id = None

        for update in updates:
            if "message" in update:
                self.process_message(update["message"])

            last_id = update["update_id"]

        return last_id

    def set_commands(self):
        commands = [{"command": "get_tasks", "description": "Show assigned tasks"}]
        res = req_get(f"{self._get_command_url()}?commands={json.dumps(commands)}")

        if not res:
            print(f"ERROR: Unable to set bot commands!")
        elif getattr(res, 'status_code', None) != 200:
            print(f"ERROR: Unable to set bot commands! Status: {getattr(res, 'status_code', 'unknown')}")

    def check_updates(self):
        self.logger.debug(f"Checking for updates... (last_msg_id={self.last_msg_id})")

        updates = self.get_updates()

        if updates and updates["ok"]:
            msg_id = self.process_updates(updates["result"])

            if msg_id is not None:
                self.last_msg_id = msg_id

    def send_saturday_message(self):
        self.logger.info(f"Sending Saturday message to {self.group_id}")

        msg = self.build_jobs_msg()
        self.send_message(self.group_id, msg)

    def send_sunday_message(self):
        self.logger.info(f"Sending Sunday message to {self.group_id}")

        msg = f"REMINDER\n{self.build_jobs_msg()}"
        self.send_message(self.group_id, msg)


def main():
    bot = CleaningBot()
    bot.set_commands()

    scheduler = schedule.Scheduler()
    scheduler.every(5).seconds.do(bot.check_updates)

    # Send Saturday message every Saturday morning at 10:00
    scheduler.every().saturday.at("10:00").do(bot.send_saturday_message)

    # Send Sunday reminder message every Sunday morning at 10:00
    scheduler.every().sunday.at("10:00").do(bot.send_sunday_message)

    while True:
        scheduler.run_pending()
        sleep(1)


if __name__ == "__main__":
    main()
