import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def authenticate(driver):
    email = "Adarsh@yopmail.com"
    login_url = (
        "https://shopify.com/100199956776/account/profile"
        "?locale=en&region_country=US"
    )
    wait = WebDriverWait(driver, 30)
    otp_selectors = (
        "input[autocomplete='one-time-code']",
        "input[name*='otp' i]",
        "input[name*='code' i]",
        "input[name*='verification' i]",
        "input[id*='otp' i]",
        "input[aria-label*='digit' i]",
        "input[maxlength='1']",
        "input[inputmode='numeric']",
        "input[type='tel']",
    )

    def find_visible(selectors):
        for selector in selectors:
            for element in driver.find_elements(By.CSS_SELECTOR, selector):
                if element.is_displayed():
                    return element
        return False

    def perform_action(action, *args):
        result = action(*args)
        time.sleep(2)
        return result

    def spinner_is_visible():
        return any(
            element.is_displayed()
            for element in driver.find_elements(
                By.CSS_SELECTOR, "[class*='SpinnerWrapper']"
            )
        )

    def click_submit():
        wait.until(lambda current_driver: not spinner_is_visible())

        def visible_submit_button(_current_driver):
            for button in driver.find_elements(
                By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"
            ):
                if (
                    button.is_displayed()
                    and button.is_enabled()
                    and button.get_attribute("aria-hidden") != "true"
                    and button.get_attribute("tabindex") != "-1"
                ):
                    return button
            return False

        perform_action(wait.until(visible_submit_button).click)

    perform_action(driver.get, login_url)
    email_input = wait.until(
        lambda current_driver: find_visible(
            (
                "input[type='email']",
                "input[name='email']",
                "input[autocomplete='email']",
            )
        )
    )
    perform_action(email_input.clear)
    perform_action(email_input.send_keys, email)

    click_submit()

    login_window = driver.current_window_handle
    wait.until(lambda current_driver: find_visible(otp_selectors))
    perform_action(driver.switch_to.new_window, "tab")

    perform_action(driver.get, "https://yopmail.com/en/")
    mailbox_input = wait.until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "input#login, input[name='login']")
        )
    )
    perform_action(mailbox_input.clear)
    perform_action(mailbox_input.send_keys, email.split("@", 1)[0])

    refresh_button = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "#refresh, #refreshbut")
        )
    )
    perform_action(refresh_button.click)
    time.sleep(10)
    perform_action(
        wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#refresh, #refreshbut")
            )
        ).click
    )

    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ifinbox")))
    time.sleep(2)

    def latest_matching_email():
        candidates = driver.find_elements(
            By.XPATH,
            "//*[self::a or self::div][contains("
            "translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'gwl-testing-app')]",
        )
        visible_candidates = [
            element
            for element in candidates
            if element.is_displayed() and element.text.strip()
        ]
        if not visible_candidates:
            return False
        return min(visible_candidates, key=lambda element: len(element.text))

    email_item = wait.until(lambda current_driver: latest_matching_email())
    perform_action(email_item.click)

    perform_action(driver.switch_to.default_content)
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ifmail")))
    time.sleep(2)
    code_pattern = re.compile(
        r"(?:your\s+)?verification(?:\s+code)?\D{0,50}(\d{6})",
        re.IGNORECASE,
    )
    code_match = wait.until(
        lambda current_driver: code_pattern.search(
            current_driver.find_element(By.TAG_NAME, "body").text
        )
    )
    verification_code = code_match.group(1)

    perform_action(driver.close)
    perform_action(driver.switch_to.window, login_window)
    otp_url = driver.current_url
    code_inputs = wait.until(
        lambda current_driver: [
            element
            for element in current_driver.find_elements(
                By.CSS_SELECTOR, ", ".join(otp_selectors)
            )
            if element.is_displayed() and element.is_enabled()
        ]
    )
    segmented_inputs = len(code_inputs) >= 6 and all(
        element.get_attribute("maxlength") in (None, "1")
        for element in code_inputs[:6]
    )
    if segmented_inputs:
        for element, digit in zip(code_inputs[:6], verification_code):
            perform_action(element.clear)
            perform_action(element.send_keys, digit)
    else:
        perform_action(code_inputs[0].clear)
        perform_action(code_inputs[0].send_keys, verification_code)

    if driver.current_url == otp_url and not spinner_is_visible():
        click_submit()

    wait.until(
        lambda current_driver: driver.current_url != otp_url
        or not spinner_is_visible()
    )
    if find_visible(otp_selectors):
        raise RuntimeError(
            "The six-digit verification code was submitted, but the OTP form "
            "is still visible. Check that the latest Yopmail message is current."
        )
