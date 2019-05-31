import requests
import json
import time
import getpass
import sys
import argparse


class AutoBuyer:
    def __init__(self, first_name, last_name, email, password):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password = password
        self.cookie = '_harmoney_session_id=12616d4df15594f40882d9396c125b78'


    def set_cookie(self, cookie):
        self.cookie = '_harmoney_session_id={}'.format(cookie)


    def send_login_request(self):
        response = requests.post(
            'https://app.harmoney.com/accounts/sign_in',
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0',
                'Accept': 'application/json',
                'Referer': 'https://www.harmoney.co.nz/sign-in',
                'content-type': 'application/json',
                'Connection': 'keep-alive',
                'Cookie': self.cookie,
            },
            data=json.dumps({
                'branch': "NZ",
                'account': {
                    'email': self.email,
                    'password': self.password,
                }
            }),
        )
        return response


    def get_account_info(self):
        response = requests.get(
            'https://app.harmoney.com/api/v1/investor/account',
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.harmoney.co.nz/lender/',
                'Origin': 'https://www.harmoney.co.nz',
                'Connection': 'keep-alive',
                'Cookie': self.cookie,
            },
        )
        return response


    def validate_account_info(self, info):
        if (info.get('first_name') != self.first_name):
            return False
        if (info.get('last_name') != self.last_name):
            return False
        if (info.get('email') != self.email):
            return False

        return True


    def login(self):
        response = self.send_login_request()
        if (response.status_code != 201):
            print("Failed to login")
            return False

        self.set_cookie(response.cookies.get_dict().get('_harmoney_session_id'))

        response = self.get_account_info()
        if (response.status_code != 200):
            print("Failed to get account info")
            return False

        if not self.validate_account_info(response.json()):
            print("Account info did not validate")
            return False

        return True


    def get_account_balance(self):
        response = requests.get(
            'https://app.harmoney.com/api/v1/investor/funds',
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.harmoney.co.nz/lender/',
                'Origin': 'https://www.harmoney.co.nz',
                'Connection': 'keep-alive',
                'Cookie': self.cookie,
            },
        )

        if (response.status_code != 200):
            print("Failed to get account balance")
            return 0

        return response.json().get('available_balance')


    def make_orders(self):
        pass


    def run(self):
        while True:
            if not self.login():
                # todo sleep for an hour
                time.sleep(3600)
                continue

            if (self.get_account_balance < 25):
                # todo sleep for a day
                time.sleep(3600)
                continue

            self.make_orders()
            # todo sleep as required

            print("Success - exiting")
            sys.exit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f','--first_name', help='First name used to register the Harmoney account', required=True)
    parser.add_argument('-l','--last_name', help='Last name used to register the Harmoney account', required=True)
    parser.add_argument('-e','--email', help='Email address used to register the Harmoney account', required=True)
    args = parser.parse_args()

    password = getpass.getpass()
    autobuyer = AutoBuyer(args.first_name, args.last_name, args.email, password)
    autobuyer.run()
  
if __name__== "__main__":
    main()