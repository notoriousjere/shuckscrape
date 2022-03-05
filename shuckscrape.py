import os
import re
from croniter import croniter
from datetime import datetime
from selenium.webdriver import Remote
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common import exceptions as selenium_exc
from twilio.rest import Client

# twilio
FROM_NUM = os.environ["FROM_NUM"]
TO_NUM = os.environ["TO_NUM"]
TWILIO_SID = os.environ["TWILIO_SID"]
TWILIO_TOKEN = os.environ["TWILIO_TOKEN"]

# target drive
TARGET_CAPACITY = os.environ["TARGET_CAPACITY"]
TARGET_MODEL = os.environ["TARGET_MODEL"]
MAX_PRICE = float(os.environ["MAX_PRICE"])
PRICE_MSG = f"{TARGET_CAPACITY} {TARGET_MODEL} costs ${{price:.2f}}"
PRICE_FILE = "notified_price.txt"
PRICE_REGEX = re.compile(r"\$(?P<price>\d{1,3}\.\d{2})")

# shuckstop site info
SHUCKS_URL = "https://shucks.top/"
COL_CAPACITY = 1
COL_MODEL = 2
COL_BB_PRICE = 4
MAX_ROWS = 50

# webdriver url
SEL_URL = os.environ["SEL_URL"]


class PriceChecker:
    """
    Check the price of an external HDD on shuckstop
    """

    def __init__(self):

        self.notified_price = None
        self.current_price = None
        self.product_row = None
        self.client = Client(TWILIO_SID, TWILIO_TOKEN)
        options = Options()
        options.add_argument("--headless")
        self.driver = Remote(SEL_URL, options=options)

        cron = os.environ.get("CRON", "0 */8 * * *")
        if not croniter.is_valid(cron):
            raise ValueError(f"Invalid cron expression: {cron}")

        base = datetime.now()
        self.cron = croniter(cron, base)

    def get_current_price(self):
        self.driver.get(SHUCKS_URL)
        row = 1
        price = None
        while row < MAX_ROWS:
            try:
                capacity = self.driver.find_element(
                    By.XPATH, f"//tr[{row}]/td[{COL_CAPACITY}]"
                ).text
                model = self.driver.find_element(By.XPATH, f"//tr[{row}]/td[{COL_MODEL}]").text
            except selenium_exc.NoSuchElementException as exc:
                raise RuntimeError(f"Did not find {TARGET_CAPACITY} {TARGET_MODEL}!") from exc

            if capacity == TARGET_CAPACITY and model == TARGET_MODEL:
                try:
                    price = self.driver.find_element(
                        By.XPATH, f"//tr[{row}]/td[{COL_BB_PRICE}]"
                    ).text
                    price_match = PRICE_REGEX.search(price)
                    if price_match:
                        self.current_price = float(price_match.group("price"))
                    else:
                        raise ValueError("Could not extract price!")
                    self.product_row = row
                    break
                except selenium_exc.NoSuchElementException as exc:
                    raise RuntimeError(
                        f"Did not find {TARGET_CAPACITY} {TARGET_MODEL} BestBuy price!"
                    ) from exc
            else:
                row += 1

        if price is None:
            raise RuntimeError("Error getting price!")

    def get_notified_price(self):
        if os.path.exists(PRICE_FILE):
            with open(PRICE_FILE, "r") as f:
                notified_price = f.read()
                if notified_price != "never":
                    try:
                        self.notified_price = float(notified_price)
                    except ValueError:
                        self.notified_price = "never"
        else:
            self.notified_price = "never"

    def send_sms(self):

        # get link to product page
        self.driver.get(SHUCKS_URL)
        try:
            link = self.driver.find_element(
                By.XPATH, f"//tr[{self.product_row}]/td[{COL_BB_PRICE}]/a"
            ).get_attribute("href")

        except selenium_exc.NoSuchElementException as exc:
            raise RuntimeError("Did not find BestBuy product hyperlink!") from exc

        # send sms
        print("Sending SMS notification...")
        self.client.messages.create(
            body=(
                f"Good news everyone!\n\n"
                f"{PRICE_MSG.format(price=self.current_price)}\n\n"
                f"{link}"
            ),
            from_=FROM_NUM,
            to=TO_NUM,
        )

    def run(self):

        self.get_current_price()
        self.get_notified_price()

        if self.notified_price is None or self.current_price is None:
            raise RuntimeError("Error getting current price or last notified price!")

        if self.current_price < MAX_PRICE:

            print("Good news everyone!")
            print(PRICE_MSG.format(price=self.current_price))

            if self.notified_price == "never" or self.current_price < float(self.notified_price):
                self.send_sms()
                with open(PRICE_FILE, "w+") as f:
                    f.write(str(self.current_price))
            else:
                print(f"Already notified at ${self.notified_price:.2f}")

        else:
            print("Terrible news...")
            print(PRICE_MSG.format(price=self.current_price))

        print(f"Next Run time: {self.cron.get_next(datetime)}")
        self.driver.quit()


if __name__ == "__main__":

    # ensure webdriver is always quit, but re-raise exceptions
    checker = None
    try:
        checker = PriceChecker()
        checker.run()
    except Exception as exc:
        if checker is not None:
            checker.driver.quit()
        raise exc from exc
