from requests.exceptions import SSLError
import csv
import requests
import os
import configparser
import warnings
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime
import json

# Define path to the config file
config_path = os.path.join(os.path.dirname(__file__), 'configuration', 'config.ini')

# Read the config file
config = configparser.ConfigParser()
config.read(config_path)

# Access the variables
url_link = config['DEFAULT']['url_link']
api_token = config['DEFAULT']['api_token']
host = config['DEFAULT']['host']
warnings.filterwarnings('ignore', category=InsecureRequestWarning)


class Main:
    def __init__(self):
        self.access_tokens = {}
        self.Add_users = Add_users()  # Assuming this is your class for adding users
        self.Remove_users = Remove_users()

    def fetch_and_store_access_token(self, username, password):
        url = f"{url_link}{api_token}"
        payload = f"username={username}&password={password}&remember_me=N&doCaptchaValidation=null&captcha=undefined&grant_type=password"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{url_link}login",
            "Host": host
        }
        try:
            response = requests.post(url, headers=headers, data=payload, verify=False)
            if response.status_code == 200:
                access_token = response.json().get('access_token')
                self.access_tokens[username] = access_token
            elif response.status_code == 401:
                raise Exception(f"Unauthorized: Incorrect username or password for user {username}.")
            else:
                print(response.text)  # print out the response text for debugging
                raise Exception(f"Failed to fetch access token for user {username}. HTTP {response.status_code}")
        except SSLError as e:
            print(f"SSL error occurred: {e}")

    def get_access_token(self, username):
        return self.access_tokens.get(username)

    def add_users_from_csv(self, access_token):
        base_url = url_link  # Use url_link from the config as the base_url
        csv_file_path = os.path.join(os.path.dirname(__file__), 'configuration', 'new_users.csv')
        user_responses = []

        with open(csv_file_path, mode='r') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                purpose = row.get('purpose', '').lower()  # Safely get the purpose with default to empty string
                if purpose == 'add':
                    if self.Add_users.validate_login(access_token, base_url, row['login']):
                        user_data = {
                            'name': row['name'],
                            'login': row['login'],
                            'userDocument': row['userDocument'],
                            'email': row['email'],
                            'password': row['password'],
                            'passwordConfirm': row['passwordConfirm'],
                            'leas': row['leas'],
                            'departments': row['departments'],
                            'teams': row['teams']
                        }
                        login, status_code = self.Add_users.add_new_user(access_token, base_url, **user_data)
                        status_message = 'added successfully' if status_code == 200 else f'failed with status {status_code}'
                        user_responses.append((login, status_message))
                    else:
                        user_responses.append((row['login'], 'user already exists'))
                elif purpose == 'remove':
                    user_id = self.Remove_users.search_user_id(access_token, base_url, row['login'])
                    if user_id:
                        if self.Remove_users.delete_user(access_token, base_url, row['login']):
                            user_responses.append((row['login'], 'user removed successfully'))
                        else:
                            user_responses.append((row['login'], 'failed to remove user'))
                    else:
                        user_responses.append((row['login'], 'user does not exist'))  # Record if user does not exist
                else:
                    skip_message = f"Skipping user {row['login']} - invalid or missing purpose"
                    print(skip_message)
                    user_responses.append((row['login'], skip_message))

        return user_responses

    def write_add_users(self, user_responses):
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        print(f"Add/Remove Users Started cycle_{timestamp}")
        results_dir = 'Results_Add_Users'
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        current_run_dir = os.path.join(results_dir, timestamp)
        os.makedirs(current_run_dir)

        csv_file_path = os.path.join(current_run_dir, f'results_add_users_{timestamp}.csv')
        with open(csv_file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['login', 'response_status'])

            for login, status in user_responses:
                writer.writerow([login, status])
        print(f"Results saved in {csv_file_path}")

class Add_users:
    def validate_login(self, access_token, base_url, login):
        validate_url = f"{base_url}/api/v2/user/bff/user/validate-login/{login}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Origin": url_link,
            "Connection": "keep-alive",
            "Referer": url_link + "/organizationManagement"
        }

        response = requests.post(validate_url, headers=headers, json={}, verify=False)
        print("Response Status Code:", response.status_code, "Response Body:", response.text)
        # Assuming 'false' in response.text indicates user exists
        if response.status_code == 200 and 'false' in response.text:
            print(f"user already exist {login}")
            return False  # User already exists
        else:
            print(f"{login}. HTTP {response.status_code}: {response.text}")
        return True  # User can be added or other validation error

    def add_new_user(self, access_token, base_url, **user_data):
        request_url = f"{base_url}/api/v2/user/bff/user/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        # Create your JSON payload with additional default values
        json_payload = {
            "passwordConfirm": user_data["passwordConfirm"],
            "image": None,
            "imageName": None,
            "name": user_data["name"],
            "login": user_data["login"],
            "status": "A",
            "ipAddress": "",
            "userDocument": user_data["userDocument"],
            "email": user_data["email"],
            "phone": "",
            "cellPhone": "",
            "password": user_data["password"],
            "emailAlert": "S",
            "smsAlert": "S",
            "forceResetPassword": "N",
            "leas": json.loads(user_data["leas"]) if user_data["leas"] else [],
            "extraPermissions": "",
            "extraPermissionsLevels": "",
            "revokedPermissions": "",
            "roleIds": "1",
            "departments": user_data["departments"],
            "teams": user_data["teams"]
        }
        # Print request details
        # print(f"Request Payload: {json_payload}")
        # Send the user data to the API
        response = requests.post(request_url, headers=headers, json=json_payload, verify=False, timeout=30)
        # print(f"Login: {user_data['login']}, Response: {response.status_code}, Body: {response.text}")  # Debug print
        return user_data['login'], response.status_code

class Remove_users:
    def __init__(self):
        self.user_ids = {}  # Dictionary to store user IDs

    def search_user_id(self, access_token, base_url, login):
        search_url = f"{base_url}/api/federated-search"
        params = {
            "filters": {
                "pageIndex": 1,
                "pageSize": 15,
                "searchWords": login,
                "operator": "and",
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
            "Referer": f"{base_url}/organizationManagement"
        }
        # Print the request details
        print("Sending Request:")
        print("URL:", search_url)
        print("Headers:", json.dumps(headers, indent=4))
        print("Parameters:", json.dumps(params, indent=4))

        response = requests.get(search_url, headers=headers, params={'params': json.dumps(params)}, verify=False)
        print("status code:", response.status_code)
        if response.status_code == 200:
            data = response.json()

            for result in data.get('resultList', []):
                if 'agentId' in result:
                    self.user_ids[login] = result['agentId']
                    return result['agentId']

        print(f"User {login} does not exist.")  # Print only once if the user does not exist
        return None

    def delete_user(self, access_token, base_url, login):
        user_id = self.user_ids.get(login)
        if user_id:
            delete_url = f"{base_url}/api/v2/user/bff/user/{user_id}/null"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Authorization": f"Bearer {access_token}",
                "Origin": f"{base_url}",
                "Connection": "keep-alive",
                "Referer": f"{base_url}/organizationManagement"
            }

            response = requests.delete(delete_url, headers=headers, verify=False)
            if response.status_code == 200:
                print(f"User {login} deleted successfully.")
                return True
            else:
                print(f"Failed to delete user {login}. HTTP {response.status_code}: {response.text}")
        else:
            print(f"User ID for {login} not found.")
        return False

if __name__ == "__main__":
    m = Main()
    m.fetch_and_store_access_token(username='emil2', password='12345678')
    access_token = m.get_access_token('emil2')
    # If an access token is successfully retrieved
    if access_token:
        # Process users from the CSV file based on their purpose (add/remove)
        user_responses = m.add_users_from_csv(access_token)
        # Write the user processing results to a CSV file
        m.write_add_users(user_responses)
        print("User processing is complete.")
    else:
        # If the access token retrieval fails, print an error message
        print("Failed to retrieve access token.")
