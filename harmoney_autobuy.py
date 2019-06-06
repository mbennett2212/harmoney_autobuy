import requests
import json
import time
import getpass
import sys
import argparse
import datetime
import logging
from pytz import timezone
from logging.handlers import RotatingFileHandler


class AutoBuyer:
    def __init__(self, first_name, last_name, email, password, log_path):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password = password
        self.cookie = '_harmoney_session_id=12616d4df15594f40882d9396c125b78'
        self.init_logger(log_path)


    def init_logger(self, log_path):
        self.logger = logging.getLogger("Rotating Log")
        self.logger.setLevel(logging.INFO)

        handler = RotatingFileHandler(log_path, maxBytes=100000, backupCount=3)
        formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)


    def send_get_request(self, url, headers, expected_code):
        """ Send a HTTP GET request to the Harmoney web API

        This function handles setting the cookie in the request headers.

        Parameters:
        url (string): The URL to use with the GET request
        headers (dict): The values to set in the request header
        expected_code (int): The expected status code from calling the API

        Returns:
        requests.Response: The response returned from the API call if the returned
                           status code matches the expected status code.
                           Otherwise None.
        """
        if self.cookie != 0:
            headers['Cookie'] = self.cookie

        response = requests.get(
            url,
            headers=headers,
        )

        if response.status_code != expected_code:
            self.logger.error("Get request failed. URL: {}".format(url))
            return None

        if 'Set-Cookie' in response.headers:
            self.cookie = response.headers.get('Set-Cookie')

        return response


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
        return self.send_get_request(
            url='https://app.harmoney.com/api/v1/investor/account',
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.harmoney.co.nz/lender/',
                'Origin': 'https://www.harmoney.co.nz',
                'Connection': 'keep-alive',
            },
            expected_code=200,
        )


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
            self.logger.error("Failed to login")
            return False

        self.set_cookie(response.cookies.get_dict().get('_harmoney_session_id'))

        response = self.get_account_info()
        if response is None:
            self.logger.error("Failed to get account info")
            return False


        if not self.validate_account_info(response.json()):
            self.logger.error("Account info did not validate")
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
            self.logger.error("Failed to get account balance")
            return 0

        return response.json().get('available_balance')


    def get_available_loans(self):
        response = requests.get(
            'https://app.harmoney.com/api/v1/investor/marketplace/loans',
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
            self.logger.error("Failed to get available loans")
            return {}

        # Store the X-CSRF-Token now, this is required when we make the API
        # calls for buying loans
        self.csrf_token = response.headers.get('X-Csrf-Token')

        return response.json().get('items')


    def have_not_invested_in_loan(self, loan):
        return loan.get('already_invested_amount') == 0


    def check_loan_grade(self, grade):
        acceptable_grades = ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3"]
        return grade in acceptable_grades


    def loan_is_acceptable(self, loan):
        grade = loan.get('grade')
        note_value = loan.get('note_value')

        if not self.check_loan_grade(grade):
            return False

        if note_value != 25:
            self.logger.error("Unexpected note value: {}".format(note_value))
            return False

        return True


    def buy_loan(self, loan):
        self.logger.info("Buying loan: {}".format(loan.get('name')))

        response = requests.post(
            'https://app.harmoney.com/api/v1/investor/order_batches/summary',
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0',
                'Accept': 'application/json',
                'Referer': 'https://www.harmoney.co.nz/lender/portal/invest/marketplace/browse',
                'content-type': 'application/json',
                'Connection': 'keep-alive',
                'Cookie': self.cookie,
                'X-CSRF-Token': self.csrf_token,
            },
            data=json.dumps({
                'orders': [{
                    'id': loan.get('id'),
                    'quantity': 1,
                }]
            }),
        )

        if (response.status_code != 200):
            print ("Unexpected response code from summary request: {}".format(response.status_code))
            return

        self.csrf_token = response.headers.get('X-Csrf-Token')

        response = requests.post(
            'https://app.harmoney.com/api/v1/investor/order_batches',
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0',
                'Accept': 'application/json',
                'Referer': 'https://www.harmoney.co.nz/lender/portal/invest/marketplace/current-order',
                'content-type': 'application/json',
                'Connection': 'keep-alive',
                'Cookie': self.cookie,
                'X-CSRF-Token': self.csrf_token,
            },
            data=json.dumps({
                'orders': [{
                    'id': loan.get('id'),
                    'quantity': 1,
                }]
            }),
        )

        if (response.status_code != 201):
            self.logger.error("Unexpected response code from order request: {}".format(response.status_code))
            return


    def make_orders(self):
        loans = self.get_available_loans()
        self.logger.info("Found {} loans".format(len(loans)))
        for loan in loans:
            if (self.have_not_invested_in_loan(loan) and self.loan_is_acceptable(loan)):
                self.buy_loan(loan)


    def sleep_until_tomorrow(self):
        current_time = datetime.datetime.now(timezone('Pacific/Auckland'))
        eight_am = datetime.time(8, 0, 0, 0)

        if (current_time.time() > eight_am):
            eight_am_tomorrow = current_time + datetime.timedelta(days=1)
        else:
            eight_am_tomorrow = current_time

        eight_am_tomorrow = eight_am_tomorrow.replace(hour=8, minute=0)
        diff = (eight_am_tomorrow - current_time).total_seconds()
        self.logger.info("Sleeping for until tomorrow")
        time.sleep(abs(diff))
        self.logger.info("Woke up")


    def sleep_minutes(self, minutes):
        current_time = datetime.datetime.now(timezone('Pacific/Auckland'))
        eight_am = datetime.time(8, 0, 0, 0)
        nine_pm = datetime.time(21, 0, 0, 0)

        if (eight_am < current_time.time() < nine_pm):
            self.logger.info("Sleeping for {} minutes".format(minutes))
            time.sleep (minutes * 60)
            self.logger.info("Woke up")
        else:
            self.sleep_until_tomorrow()


    def run(self):
        while True:
            if not self.login():
                self.sleep_minutes(60)
                continue

            if (self.get_account_balance < 25):
                self.sleep_until_tomorrow()
                continue

            self.make_orders()
            self.sleep_minutes(5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f','--first_name', help='First name used to register the Harmoney account', required=True)
    parser.add_argument('-l','--last_name', help='Last name used to register the Harmoney account', required=True)
    parser.add_argument('-e','--email', help='Email address used to register the Harmoney account', required=True)
    parser.add_argument('-p','--log_path', help='The path to the files to log messages to', required=True)
    args = parser.parse_args()

    password = getpass.getpass()
    autobuyer = AutoBuyer(args.first_name, args.last_name, args.email, password, args.log_path)
    autobuyer.run()
  
if __name__== "__main__":
    main()