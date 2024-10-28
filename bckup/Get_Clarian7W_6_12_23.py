import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.common.exceptions import TimeoutException
import json
import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning
import threading
import pandas as pd
import os
import urllib.parse
import configparser
from requests import Session, exceptions

# Define path to the config file
config_path = os.path.join(os.path.dirname(__file__), 'configuration', 'config.ini')

# Read the config file
config = configparser.ConfigParser()
config.read(config_path)

# Access the variables
url_link = config['DEFAULT']['url_link']
api_token = config['DEFAULT']['api_token']
host = config['DEFAULT']['host']
PAUSE_TIME = int(config['DEFAULT']['PAUSE_TIME'])
Between_threads = int(config['DEFAULT']['Between_threads'])

warnings.filterwarnings('ignore', category=InsecureRequestWarning)

class LoginTests:
    def __init__(self):
        self.drivers = []  # List to store all driver instances

    def login_with_params(self, username_login, password_login, headless):
        options = webdriver.FirefoxOptions()
        if headless:
            options.add_argument('-headless')
        driver = webdriver.Firefox(options=options)
        self.drivers.append(driver)
        driver.maximize_window()
        wait = WebDriverWait(driver, PAUSE_TIME)

        driver.get(url_link + 'login')
        start_loading_time = time.time()
        WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Sign in"))
        loading_time = time.time() - start_loading_time

        username = wait.until(
            EC.visibility_of_element_located((By.XPATH, '/html/body/div/section/div/form/div[1]/div[1]/input')))
        username.clear()
        username.send_keys(username_login)

        password = wait.until(
            EC.visibility_of_element_located((By.XPATH, '/html/body/div/section/div/form/div[1]/div[2]/span[2]/input')))
        password.clear()
        password.send_keys(password_login)

        btn_login = wait.until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div/section/div/form/div[3]/span/button')))
        btn_login.click()

        try:
            btn_ok = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, '/html/body/div[3]/div/div[2]/div/div[2]/div/div/div[2]/button[2]')))
            btn_ok.click()

            time.sleep(PAUSE_TIME)
        except TimeoutException:
            print("The 'OK' button was not found. Continuing without clicking it.")

        return loading_time, driver, wait

    def login_ok(self, username_login, password_login, writer, loading_time, driver, wait):
        start_time = time.time()
        page_inner_html = driver.execute_script("return document.body.innerHTML")
        if "Investigation Dashboard" in page_inner_html:
            result = "Passed"
            print(f'{username_login} Login Test {result}')
            login_time = time.time() - start_time
            writer.writerow([username_login, 'Login Test', result, loading_time, login_time])
            return True
        else:
            result = "Failed"
            print(f'{username_login} Login Test {result}')
            writer.writerow([username_login, 'Login Test', result, loading_time, ''])
            return False

class LoadPages:
    def __init__(self, drivers):
        self.drivers = drivers

    def wait_for_page_load(self, driver):
        WebDriverWait(driver, 15).until(lambda d: d.execute_script('return document.readyState') == 'complete')

    def click_button(self, driver, wait, click, selector):
        start_time = time.time()
        try:
            if selector.upper() == 'XPATH':
                button = wait.until(EC.element_to_be_clickable((By.XPATH, click)))
                button.click()
                self.wait_for_page_load(driver)
            elif selector.upper() == 'CSS':
                button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, click)))
                button.click()
                self.wait_for_page_load(driver)
            elif selector.upper() == 'URL':
                self.browse_url(driver, click)  # Assuming 'click' is the URL in this case
            else:
                raise ValueError(f'Unsupported selector type: {selector}')

            self.wait_for_page_load(driver)
            time.sleep(PAUSE_TIME)

            return True, time.time() - start_time
        except TimeoutException:
            return False, time.time() - start_time

    def browse_url(self, driver, url):
        driver.get(url)

    def verify_page_content(self, driver, content):
        page_inner_html = driver.execute_script("return document.body.innerHTML")
        if "ant-notification" in page_inner_html.lower():
            return False, "Failed with error"
        elif "something went wrong" in page_inner_html.lower():
            return False, "Passed with some error"
        if content in page_inner_html:
            return True, ""
        return False, ""

class AccessTokenManager:
    def __init__(self):
        self.access_tokens = {}  # Dictionary to store access tokens

    def fetch_and_store_access_token(self, username, password):
        url = url_link + api_token
        payload = f"username={username}&password={password}&remember_me=N&doCaptchaValidation=null&captcha=undefined&grant_type=password"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Content - Length": "80",
            "Connection": "keep-alive",
            "Accept": "application/json, text/plain, */*",
            "Referer": url_link + "login",
            "Host": host,
        }
        try:
            response = requests.post(url, headers=headers, data=payload, verify=False)
            if response.status_code == 200:
                access_token = response.json().get('access_token')
                self.access_tokens[username] = access_token
            elif response.status_code == 401:
                pass
                # print(f"User {username} does not exist or password is incorrect.")
            elif response.status_code == 409:  # Handle the 409 status code
                # Send the required request
                release_url = url_link + "/api/v2/auth/token/revoke"
                release_headers = {
                    #"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "Authorization": "[object Object]",
                    "Origin": url_link,
                    "Connection": "keep-alive",
                    "Referer": url_link
                }
                release_response = requests.delete(release_url, headers=release_headers, data="{}",
                                  verify=False)  # Sending delete release request
                print(f"{username} Release response status code: {release_response.status_code}")

                time.sleep(3)  # Pausing for 5 seconds
                # Retry the original request
                payload = f"username={username}&password={password}&remember_me=N&doCaptchaValidation=null&captcha=undefined&grant_type=password"
                response = requests.post(url, headers=headers, data=payload, verify=False, timeout=30)
                if response.status_code == 200:
                    access_token = response.json().get('access_token')
                    self.access_tokens[username] = access_token
                elif response.status_code == 401:
                    pass
            else:
                print(response.text)  # print out the response text for debugging
                raise Exception(f"Failed to fetch access token for user {username}. HTTP {response.status_code}")
        except requests.exceptions.SSLError as e:
            print(f"SSL error occurred: {e}")

    def get_access_token(self, username):
        return self.access_tokens.get(username)


    def fetch_and_store_all_tokens(self, credentials_file):
        with open('configuration/user_credentials.csv', 'r') as credentials_file:
            reader = csv.reader(credentials_file)
            for row in reader:
                if len(row) >= 2:
                    username = row[0].strip()
                    password = row[1].strip()
                    self.fetch_and_store_access_token(username, password)

    def validate_api_response(self, access_token, request_url, search_term):
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get(request_url, headers=headers, verify=False, timeout=30)
        if response.status_code == 200:
            json_response = response.json()
            if "resultList" in json_response:
                print(json_response["resultList"])  # Print the resultList part of the response
                for item in json_response["resultList"]:
                    if any(search_term.lower() in str(value).lower() for value in item.values()):
                        return True, json_response
        return False, None

class Main:
    def __init__(self):
        self.login_tests = LoginTests()
        self.load_pages = LoadPages(self.login_tests.drivers)
        self.token_manager = AccessTokenManager()

        with open('configuration/test_data1.json', 'r') as f:
            data = json.load(f)
            self.test_data = data.get('tests', [])  # Get the 'tests' list

        # Replace the placeholder in test_data
        for test in self.test_data:
            if "click" in test and "{url_link}" in test["click"]:
                test["click"] = test["click"].replace("{url_link}", url_link)

    def run_page_test(self, writer, driver, wait, username, test_name, click, selector, expected_content):
        click_result, loading_time = self.load_pages.click_button(driver, wait, click, selector)
        verification_result, error_msg = self.load_pages.verify_page_content(driver, expected_content)

        if click_result and verification_result:
            print(f'{username} {test_name} Passed')
            writer.writerow([username, test_name, 'Passed', '', loading_time - PAUSE_TIME, selector])
        else:
            if error_msg == "Failed with error":
                print(f'{username} {test_name} {error_msg}')
                writer.writerow([username, test_name, error_msg, '', '', selector])
            elif error_msg == "Passed with some error":
                print(f'{username} {test_name} {error_msg}')
                writer.writerow([username, test_name, error_msg, '', '', selector])
            else:
                print(f'{username} {test_name} Failed')
                writer.writerow([username, test_name, 'Failed', '', '', selector])

    def run_api_test(self, writer, username, test):
        access_token = self.token_manager.get_access_token(username)
        endpoint = test["endpoint"]
        params_string = json.dumps(test["params"])
        encoded_params = urllib.parse.quote(params_string)
        request_url = f"{url_link}{endpoint}?params={encoded_params}"
        search_term = test["params"]["filters"]["searchWords"]
        test_name_and_search = f"{test['test_name']} {search_term}"
        start_time = time.time()

        is_valid_response, json_response = self.token_manager.validate_api_response(access_token, request_url, search_term)
                                                                                    
        end_time = time.time()

        # Calculate the response time
        response_time = end_time - start_time
        writer.writerow(
            [username, test_name_and_search, 'Passed' if is_valid_response else 'Failed', '', response_time, ''])
        print(
            f'{username} {test_name_and_search} Passed' if is_valid_response else f'{username} {test_name_and_search} Failed')

    def run_tests_for_user(self, row, writer):
        username = row[0].strip()
        password = row[1].strip()
        browser = row[2].strip()
        headless = True if browser.lower() == 'browser no' else False
        loading_time, driver, wait = self.login_tests.login_with_params(username, password, headless)

        if not self.login_tests.login_ok(username, password, writer, loading_time, driver, wait):
            return

        access_token = self.token_manager.get_access_token(username)
        print(username, access_token)

        for test in self.test_data:
            if test["type"] == "api":
                self.run_api_test(writer, username, test)
            elif test["type"] == "page":
                self.run_page_test(writer, driver, wait, username, test['test_name'], test['click'], test['selector'],
                                   test['content'])

    def sort_csv(self, csv_path):
        # Read the CSV file
        df = pd.read_csv(csv_path)
        # Sort first by 'Username' and then by 'Test Case'
        df_sorted = df.sort_values(by=['Username', 'Test Case'])
        # Write the sorted data back to the CSV file
        df_sorted.to_csv(csv_path, index=False)

    def summarize_test_results(self, csv_path):
        # Read the CSV file
        df = pd.read_csv(csv_path)

        # Group by 'Test Case' and calculate the count, pass count, fail count and average response time
        summary = df.groupby('Test Case').agg(
            Total=('Result', 'size'),
            Passed=('Result', lambda x: (x == 'Passed').sum()),
            Failed=('Result', lambda x: (x == 'Failed').sum()),
            Average_Response_Time=('Response Time', lambda x: pd.to_numeric(x, errors='coerce').mean()),
            Min_Response_Time=('Response Time', 'min'),  # Minimum response time
            Max_Response_Time=('Response Time', 'max'),  # Maximum response time
            Common_Selector=('Selector', lambda x: x.mode()[0] if not x.mode().empty else ' ')
        ).reset_index()

        # Round the response time columns to three decimal places
        for col in ['Average_Response_Time', 'Min_Response_Time', 'Max_Response_Time']:
            summary[col] = summary[col].round(3)
        # Save the summary to a new CSV file
        summary_csv_path = csv_path.replace('.csv', '_summary.csv')
        summary.to_csv(summary_csv_path, index=False)
        print(f"Summary has been saved to {summary_csv_path}")

    def run_tests(self):
        print(f'******************* Start TESTING ****************************_on lab {host}')
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')

        # Step 1: Ensure 'UF_Results' directory exists.
        results_dir = 'UF_Results'
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        # Step 2: Create a sub-directory with the timestamp.
        current_run_dir = os.path.join(results_dir, f'{timestamp}__{host}')
        os.makedirs(current_run_dir)

        # Modify paths for CSV files to be inside the timestamped directory.
        csv_file_path = os.path.join(current_run_dir, f'results_{timestamp}.csv')
        audit_file_path = os.path.join(current_run_dir, f'audit_{timestamp}.csv')

        with open(csv_file_path, 'w', newline='') as csvfile, \
                open(audit_file_path, 'w', newline='') as auditfile:

            writer = csv.writer(csvfile)
            audit_writer = csv.writer(auditfile)
            audit_writer.writerow(['Event', 'Time'])

            writer.writerow(
                ['Username', 'Test Case', 'Result', 'Loading Time Login Page', 'Response Time', 'Selector'])

            start_time = datetime.now()
            audit_writer.writerow([f"Start testing", start_time.strftime('%Y-%m-%d %H:%M:%S')])

            with open('configuration/user_credentials.csv', 'r') as credentials_file:
                # Fetch and store all access tokens
                credentials_file.seek(0)  # Reset the file pointer to the beginning
                self.token_manager.fetch_and_store_all_tokens(credentials_file)
                reader = csv.reader(credentials_file)
                threads = []

                for row in reader:
                    if len(row) >= 3:  # Update condition to check for 3 columns
                        t = threading.Thread(target=self.run_tests_for_user, args=(row, writer))
                        t.start()
                        threads.append(t)
                        time.sleep(Between_threads)
                for thread in threads:
                    thread.join()

        # Close all driver instances after all iterations

        for driver in self.login_tests.drivers:
            time.sleep(5)
            driver.quit()

        # Call the sorting function on the newly created CSV file
        self.sort_csv(csv_file_path)
        # Call the summarization function on the sorted CSV file
        self.summarize_test_results(csv_file_path)
        with open(audit_file_path, 'a', newline='') as auditfile:  # open file in append mode
            audit_writer = csv.writer(auditfile)
            end_time = datetime.now()
            audit_writer.writerow([f"Stop testing", end_time.strftime('%Y-%m-%d %H:%M:%S')])

            # Calculate and add total testing time
            total_time = end_time - start_time
            audit_writer.writerow([f"Total testing time", total_time])

        print("*********************** Stop TESTING ********************************")

if __name__ == "__main__":
    m = Main()
    m.run_tests()
