import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
import time
import json
import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning
import threading
import pandas as pd
import os
import urllib.parse
import configparser
import subprocess
from requests.exceptions import SSLError
import customtkinter as ctk
from tkinter import messagebox

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
Wait_Driver = int(config['DEFAULT']['Wait_Driver'])
number_of_cycles = config['DEFAULT']['number_of_cycles']

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
        wait = WebDriverWait(driver, Wait_Driver)

        driver.get(url_link + 'login')
        WebDriverWait(driver, Wait_Driver).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        start_loading_time = time.time()
        WebDriverWait(driver, Wait_Driver).until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Sign in"))
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
            time.sleep(2)
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
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
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
        WebDriverWait(driver, PAUSE_TIME).until(lambda d: d.execute_script('return document.readyState') == 'complete')

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
        #WebDriverWait(driver, PAUSE_TIME).until(lambda d: d.execute_script('return document.readyState') == 'complete')

        if page_inner_html is None:
            print("Warning: Page content is None.")
            return False, "Page content not found"
        page_inner_html_lower = page_inner_html.lower()  # Lowercase the HTML content for consistent searching
        if "ant-notification" in page_inner_html_lower:
            return False, "Failed with error"
        elif "something went wrong" in page_inner_html_lower:
            return False, "Passed with some error"
        if content in page_inner_html:
            return True, ""
        return False, ""

class AccessTokenManager:
    def __init__(self):
        self.access_tokens = {}  # Dictionary to store access tokens

    def fetch_and_store_all_tokens(self, credentials_file, writer):
        with open('configuration/user_credentials.csv', 'r') as credentials_file:
            reader = csv.reader(credentials_file)
            for row in reader:
                if len(row) >= 2:
                    username = row[0].strip()
                    password = row[1].strip()
                    self.fetch_and_store_access_token(username, password, writer)

    def fetch_and_store_access_token(self, username, password, writer):
        url = f"{url_link}{api_token}"
        payload = f"username={username}&password={password}&remember_me=N&doCaptchaValidation=null&captcha=undefined&grant_type=password"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{url_link}login",
            "Host": host
        }
        try:
            start_time = time.time()
            response = requests.post(url, headers=headers, data=payload, verify=False)
            if response.status_code == 200:
                access_token = response.json().get('access_token')
                if access_token:
                    self.access_tokens[username] = access_token
                    end_time = time.time()
                    response_time = end_time - start_time
                    writer.writerow([username, 'Fetch and Store Access Token', 'Passed', '', response_time, 'api'])
                else:
                    writer.writerow([username, 'Fetch and Store Access Token', 'Failed', '', '', 'Empty access token'])
            else:
                writer.writerow(
                    [username, 'Fetch and Store Access Token', 'Failed', '', '', f'HTTP {response.status_code}'])
        except SSLError as e:
            writer.writerow([username, 'Fetch and Store Access Token', 'Error', '', '', f'SSL Error: {e}'])

    def get_access_token(self, username):
        return self.access_tokens.get(username)

    def validate_api_response(self, access_token, request_url, search_term, operator):
        search_url = f"{url_link}api/federated-search"
        params = {
            "filters": {
                "pageIndex": 1,
                "pageSize": 15,
                "searchWords": search_term,
                "operator": operator,
                "langCode": "enUS"
            }
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Authorization": f"Bearer {access_token}",
            "Connection": "keep-alive",
            "Referer": f"{url_link}organizationManagement",
        }

        response = requests.get(search_url, headers=headers, params={'params': json.dumps(params)}, verify=False)
        print("status code:", response.status_code)
        if response.status_code == 200:
            json_response = response.json()
            first_word = search_term.split(',')[0]
            #print("Json response:", json_response)
            is_first_word_present = any(
                first_word.lower() in str(value).lower() for item in json_response.get("resultList", []) for value in
                item.values()
            )
            return is_first_word_present, json_response
        else:
            return False, None

    def get_events_filter(self, access_token, test_params):
        base_url = f"{url_link}api/analytics"
        params = {
            "filters": test_params["filters"]
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Prepare the request details for printing
        prepared_request = requests.Request('GET', base_url, headers=headers,
                                            params={'params': json.dumps(params)}).prepare()

        # Send the request
        session = requests.Session()
        response = session.send(prepared_request, verify=False)

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, None
        #response = requests.get(base_url, headers=headers, params={'params': json.dumps(params)}, verify=False)

class Summarize:
    def close_firefox_processes(self):
        result = None
        try:
            if os.name == 'nt':  # for Windows
                result = subprocess.run(['taskkill', '/F', '/IM', 'firefox.exe'], capture_output=True, text=True)
            elif os.name == 'posix':  # for Unix-like systems, including macOS
                result = subprocess.run(['killall', 'firefox'], capture_output=True, text=True)
        except Exception as e:
            print(f"Error occurred in closing Firefox processes: {e}")

        if result and "The process \"firefox.exe\" not found" in result.stderr:
            print("Info: The process \"firefox.exe\" is not found.")
        elif result and result.stderr:
            print(f"Error: {result.stderr}")

    def sort_csv(self, csv_path):
        df = pd.read_csv(csv_path)
        # Ensure "Login Test" and "exit" are present in the dataframe
        if "Login Test" in df["Test Case"].values and "exit" in df["Test Case"].values:
            # Separate the special cases
            login_test_df = df[df["Test Case"] == "Login Test"]
            exit_test_df = df[df["Test Case"] == "exit"]
            rest_df = df[(df["Test Case"] != "Login Test") & (df["Test Case"] != "exit")]

            # Sort the rest of the dataframe
            rest_df_sorted = rest_df.sort_values(by=['Username', 'Test Case'])

            # Concatenate in the desired order
            df_sorted = pd.concat([login_test_df, rest_df_sorted, exit_test_df])
        else:
            df_sorted = df.sort_values(by=['Username', 'Test Case'])
        df_sorted.to_csv(csv_path, index=False)

    def summarize_test_results(self, csv_path):
        df = pd.read_csv(csv_path)

        # Original summary calculations
        summary = df.groupby('Test Case').agg(
            Total=('Result', 'size'),
            Passed=('Result', lambda x: (x == 'Passed').sum()),
            Failed=('Result', lambda x: ((x == 'Failed') | (x == 'Failed with error') | (x == 'Error')).sum()),
            Average_Response_Time=('Response Time', lambda x: pd.to_numeric(x, errors='coerce').mean()),
            Min_Response_Time=('Response Time', 'min'),
            Max_Response_Time=('Response Time', 'max'),
            Common_Selector=('Selector', lambda x: x.mode()[0] if not x.mode().empty else ' ')
        ).reset_index()

        # Rounding response times
        for col in ['Average_Response_Time', 'Min_Response_Time', 'Max_Response_Time']:
            summary[col] = summary[col].round(3)

        # Saving the updated summary
        summary_csv_path = csv_path.replace('.csv', '_summary.csv')
        summary.to_csv(summary_csv_path, index=False)
        print(f"Summary has been saved to {summary_csv_path}")

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
        try:
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
        except (WebDriverException, TimeoutException, NoSuchElementException) as e:
            print(f'Error occurred in run_page_test for {username}: {e}')
            writer.writerow([username, test_name, 'Error', str(e), '', selector])

    def run_api_test(self, writer, username, test):
        access_token = self.token_manager.get_access_token(username)
        endpoint = test["endpoint"]
        params_string = json.dumps(test["params"])
        encoded_params = urllib.parse.quote(params_string)
        request_url = f"{url_link}{endpoint}?params={encoded_params}"
        search_term = test["params"]["filters"]["searchWords"]
        operator = test["params"]["filters"]["operator"]
        test_name_and_search = f"{test['test_name']} {search_term}"
        start_time = time.time()

        is_valid_response, json_response = self.token_manager.validate_api_response(access_token, request_url, search_term, operator)
        end_time = time.time()

        # Calculate the response time
        response_time = end_time - start_time
        writer.writerow([username, test_name_and_search, 'Passed' if is_valid_response else 'Failed', '', response_time, 'api'])
        print(
            f'{username} {test_name_and_search} Passed' if is_valid_response else f'{username} {test_name_and_search} Failed')

    def run_events_filter_test(self, writer, username, test, access_token):
        start_time = time.time()
        success, response = self.token_manager.get_events_filter(access_token, test["params"])

        result = 'Failed'
        total_events = 0  # Initialize total_events

        if success and 'events' in response:
            total_events = response['events'].get('total', 0)
            if total_events > 0:
                result = 'Passed'

        end_time = time.time()
        response_time = end_time - start_time
        test_name = test['test_name']

        # Print and write the results
        print(f'{username} {test_name} {result}')
        writer.writerow([username, test_name, result, '', response_time, 'api' if success else 'Failed'])

    def run_tests_for_user(self, row, writer):
        username = row[0].strip()
        password = row[1].strip()
        browser = row[2].strip()
        headless = True if browser.lower() == 'browser no' else False
        attempt = 0
        max_attempts = 1  # Set to 2 to allow for one retry
        driver = None  # Initialize driver to None
        while attempt < max_attempts:
            try:

                # 1. Login Test
                loading_time, driver, wait = self.login_tests.login_with_params(username, password, headless)
                if not self.login_tests.login_ok(username, password, writer, loading_time, driver, wait):
                    return
                # 2. Test Execution for "page"
                for test in self.test_data:
                    if test["type"] == "page":
                        self.run_page_test(writer, driver, wait, username, test['test_name'], test['click'],
                                           test['selector'], test['content'])
                if driver:
                    driver.quit()
                    driver = None

                # 3. Access Token Retrieval
                self.token_manager.fetch_and_store_access_token(username, password, writer)
                access_token = self.token_manager.get_access_token(username)
                if not access_token:
                    print(f"Failed to get access token for {username}")
                    return  # or handle the error as needed
                # 4. Test Execution for "api"
                for test in self.test_data:
                    if test["type"] == "api":
                        self.run_api_test(writer, username, test)  # Updated to use the access token
                        if test["test_name"] == "Federated Search name":
                            success, response = self.token_manager.get_events_filter(access_token, test["params"])
                    elif test["type"] == "events_filter":
                        self.run_events_filter_test(writer, username, test, access_token)

                break  # Break the loop if successful
            except (WebDriverException, TimeoutException, NoSuchElementException) as e:
                print(f'Error occurred during testing for user {username}: {e}')
                writer.writerow([username, 'Login or Setup', 'Error', str(e), '', ''])
                attempt += 1
                if attempt == max_attempts:
                    print(f"Maximum retry attempts reached for user {username}")
            finally:
                # Ensure the driver is quit after each attempt
                if 'driver' in locals() and driver:
                    driver.quit()

    def run_tests(self):
        global number_of_cycles
        number_of_cycles = int(number_of_cycles)  # Convert to integer
        print("Running tests with:", url_link, host, number_of_cycles)

        total_cycles_run = 0  # Counter for the actual number of cycles run
        users_set = set()  # Set to keep track of unique users
        summarize = Summarize()
        # Initialize file paths
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        results_dir = 'UF_Results'
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        current_run_dir = os.path.join(results_dir, f'{timestamp}__{host}')
        if not os.path.exists(current_run_dir):
            os.makedirs(current_run_dir)

        csv_file_path = os.path.join(current_run_dir, f'results_{timestamp}.csv')
        audit_file_path = os.path.join(current_run_dir, f'audit_{timestamp}.csv')
        try:
            summarize.close_firefox_processes()
            print(f'******************* Start TESTING ****************************_on lab {host}')
            print(f'Total Cycles Requested is {number_of_cycles}')

            for cycle in range(number_of_cycles):
                with open(csv_file_path, 'a', newline='') as csvfile, \
                        open(audit_file_path, 'a', newline='') as auditfile:

                    writer = csv.writer(csvfile)
                    audit_writer = csv.writer(auditfile)
                    if cycle == 0:
                        writer.writerow(
                            ['Username', 'Test Case', 'Result', 'Loading Time Login Page', 'Response Time', 'Selector'])
                        audit_writer.writerow(['Event', 'Time'])

                    start_time = datetime.now()
                    audit_writer.writerow([f"Start cycle {cycle + 1}", start_time.strftime('%Y-%m-%d %H:%M:%S')])

                    with open('configuration/user_credentials.csv', 'r') as credentials_file:
                        reader = csv.reader(credentials_file)
                        threads = []

                        for row in reader:
                            if len(row) >= 2:
                                users_set.add(row[0].strip())  # Add username to the set
                                t = threading.Thread(target=self.run_tests_for_user, args=(row, writer))
                                t.start()
                                threads.append(t)
                                time.sleep(Between_threads)
                        for thread in threads:
                            thread.join()
                    total_cycles_run += 1  # Increment the actual cycles run counter

                    end_cycle_time = datetime.now()
                    audit_writer.writerow([f"End cycle {cycle + 1}", end_cycle_time.strftime('%Y-%m-%d %H:%M:%S')])
        except Exception as e:
            print(f"An error occurred: {e}")
        # Additional specific error handling can go here

        finally:
        # This block ensures that all methods in the Summarize class are called
        # regardless of how the script terminates
            try:
                if os.path.exists(csv_file_path):
                    summarize.sort_csv(csv_file_path)
                    summarize.summarize_test_results(csv_file_path)

                if os.path.exists(audit_file_path):
                    with open(audit_file_path, 'a', newline='') as auditfile:
                        audit_writer = csv.writer(auditfile)
                        audit_writer.writerow(['Total Cycles Requested', number_of_cycles])
                        audit_writer.writerow(['Total Cycles Actually Run', total_cycles_run])
                        audit_writer.writerow(['Number of Unique Users', len(users_set)])

            except Exception as e:
                print(f"Error in summarizing results: {e}")

            print("*********************** Stop TESTING ********************************")
            try:
                summarize.close_firefox_processes()
            except Exception as e:
                print(f"Error in closing Firefox processes: {e}")


class TestRunnerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Test Runner")
        self.geometry("500x400")
        self.label = ctk.CTkLabel(self, text="Welcome to the Clarian UF automation", font=("Ariel", 16))
        self.label.pack(pady=10)

        self.url_link_var = ctk.StringVar()
        self.host_entry_var = ctk.StringVar()
        self.number_of_cycles_var = ctk.StringVar()

        self.create_widgets()
        self.load_config()

    def create_widgets(self):
        # URL Link Label and Entry in a Frame
        url_link_frame = ctk.CTkFrame(self)
        url_link_frame.pack(pady=5, fill='x')
        self.url_link_label = ctk.CTkLabel(url_link_frame, text="URL Link:")
        self.url_link_label.pack(side='left', padx=10)
        self.url_link_entry = ctk.CTkEntry(url_link_frame, textvariable=self.url_link_var, placeholder_text="URL Link")
        self.url_link_entry.pack(side='left')

        # Host Label and Entry in a Frame
        host_frame = ctk.CTkFrame(self)
        host_frame.pack(pady=5, fill='x')
        self.host_label = ctk.CTkLabel(host_frame, text="Host:")
        self.host_label.pack(side='left', padx=10)
        self.host_entry = ctk.CTkEntry(host_frame, textvariable=self.host_entry_var, placeholder_text="Host")
        self.host_entry.pack(side='left')

        # Number of Cycles Label and Entry in a Frame
        number_of_cycles_frame = ctk.CTkFrame(self)
        number_of_cycles_frame.pack(pady=5, fill='x')
        self.number_of_cycles_label = ctk.CTkLabel(number_of_cycles_frame, text="Number of Cycles:")
        self.number_of_cycles_label.pack(side='left', padx=10)
        self.number_of_cycles = ctk.CTkEntry(number_of_cycles_frame, textvariable=self.number_of_cycles_var,
                                             placeholder_text="Number of Cycles")
        self.number_of_cycles.pack(side='left')

        self.save_button = ctk.CTkButton(self, text="Save to Config.ini", command=self.save_config)
        self.save_button.pack(pady=20)

        self.run_button = ctk.CTkButton(self, text="Run UF Automation", command=self.run_tests,
                                        fg_color="#0A1172",  # Darker color for the button face
                                        hover_color="#5C5C5C",  # Slightly lighter color on hover
                                        corner_radius=10)  # Rounded corners
        self.run_button.pack(pady=10)

        self.footer_label = ctk.CTkLabel(self, text="Tool by Load Team", font=("Ariel", 12))
        self.footer_label.pack(pady=10, side='left')

    def load_config(self):
        # Read the config file
        self.config = configparser.ConfigParser()
        self.config.read(config_path)

        # Set the values in StringVars
        self.url_link_var.set(self.config['DEFAULT']['url_link'])
        self.host_entry_var.set(self.config['DEFAULT']['host'])
        self.number_of_cycles_var.set(self.config['DEFAULT']['number_of_cycles'])

    def save_config(self):
        # Update the config values using StringVars
        self.config['DEFAULT']['url_link'] = self.url_link_var.get()
        self.config['DEFAULT']['host'] = self.host_entry_var.get()
        self.config['DEFAULT']['number_of_cycles'] = self.number_of_cycles_var.get()

        # Write the updated config to file
        with open(config_path, 'w') as configfile:
            self.config.write(configfile)
        messagebox.showinfo("Info", "Configuration saved to config.ini")
        # Reload the configuration before running tests
        self.reload_config()
    def run_tests(self):
        # Change the button's appearance to indicate tests are running
        self.run_button.configure(text="Running UF Automation...", state="disabled", fg_color="#0A1172")

        # Running the tests in a separate thread to prevent GUI freezing
        thread = threading.Thread(target=self.execute_tests, daemon=True)
        thread.start()

    def execute_tests(self):
        global url_link, host, number_of_cycles  # Declare global variables

        try:
            m = Main()
            m.run_tests()
            messagebox.showinfo("Success", "Tests completed successfully!")
            self.close_gui()  # Close the GUI after the message box
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.run_button.configure(text="Run Tests", state="normal", fg_color="#0A1172")

    def reload_config(self):
        global url_link, host, number_of_cycles  # Declare global variables

        self.config.read(config_path)

        # Update StringVar attributes with the new values
        self.url_link_var.set(self.config['DEFAULT']['url_link'])
        self.host_entry_var.set(self.config['DEFAULT']['host'])
        self.number_of_cycles_var.set(self.config['DEFAULT']['number_of_cycles'])

        # Update global variables with the new values
        url_link = self.config['DEFAULT']['url_link']
        host = self.config['DEFAULT']['host']
        number_of_cycles = self.config['DEFAULT']['number_of_cycles']

    def close_gui(self):
        self.destroy()  # Closes the GUI window

if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), 'configuration', 'config.ini')

    app = TestRunnerGUI()
    app.mainloop()



