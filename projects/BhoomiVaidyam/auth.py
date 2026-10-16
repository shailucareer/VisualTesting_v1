import base64
import json
import re
import time
from urllib.parse import urlsplit

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


LOGIN_URL = "https://bhoomivaidyam.galaxyweblinks.com/admin-login"
PHONE_NUMBER = "9000000001"
OTP_INPUTS = "input[autocomplete='one-time-code'], input[inputmode='numeric'], input[maxlength='1']"


def _read_dev_otp(driver, timeout=30):
    deadline = time.monotonic() + timeout
    matching_responses = {}

    while time.monotonic() < deadline:
        for entry in driver.get_log("performance"):
            event = json.loads(entry["message"])["message"]
            method = event.get("method")
            params = event.get("params", {})

            if method == "Network.responseReceived":
                response = params.get("response", {})
                response_path = urlsplit(response.get("url", "")).path
                if response_path.endswith("/send-otp"):
                    matching_responses[params["requestId"]] = response.get("status")
            elif method == "Network.loadingFinished":
                request_id = params.get("requestId")
                if request_id not in matching_responses:
                    continue

                response_status = matching_responses.pop(request_id)
                if response_status != 200:
                    raise RuntimeError(
                        f"The send-otp request returned HTTP {response_status}."
                    )

                response_body = driver.execute_cdp_cmd(
                    "Network.getResponseBody", {"requestId": request_id}
                )
                body = response_body["body"]
                if response_body.get("base64Encoded"):
                    body = base64.b64decode(body).decode("utf-8")
                payload = json.loads(body)
                dev_otp = payload.get("devOtp")
                if isinstance(dev_otp, str) and re.fullmatch(r"\d{6}", dev_otp):
                    return dev_otp
                raise RuntimeError(
                    "The send-otp response did not contain a six-digit devOtp."
                )

        time.sleep(0.2)

    raise RuntimeError(
        "Could not capture a successful send-otp response containing devOtp. "
        "Run this project with Chrome or Edge performance logging enabled."
    )


def authenticate(driver):
    wait = WebDriverWait(driver, 30)

    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get_log("performance")
    except Exception as exc:
        raise RuntimeError(
            "BhoomiVaidyam OTP login requires a Chrome or Edge session with "
            "performance logging enabled."
        ) from exc

    driver.get(LOGIN_URL)
    phone_input = wait.until(
        EC.visibility_of_element_located(
            (
                By.CSS_SELECTOR,
                "input[type='tel'], input[inputmode='numeric'], "
                "input[placeholder*='mobile' i], input[placeholder*='phone' i]",
            )
        )
    )
    phone_input.clear()
    phone_input.send_keys(PHONE_NUMBER)

    send_otp_button = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[normalize-space()='Send OTP']")
        )
    )
    send_otp_button.click()
    wait.until(EC.url_contains("/verify-otp"))

    verification_code = _read_dev_otp(driver)
    otp_inputs = wait.until(
        lambda current_driver: [
            element
            for element in current_driver.find_elements(By.CSS_SELECTOR, OTP_INPUTS)
            if element.is_displayed() and element.is_enabled()
        ]
    )
    if len(otp_inputs) < 6:
        raise RuntimeError(
            f"The verification screen exposed {len(otp_inputs)} usable OTP inputs; "
            "expected six."
        )

    for element, digit in zip(otp_inputs[:6], verification_code):
        element.send_keys(digit)

    otp_url = driver.current_url
    verify_button = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[normalize-space()='Verify & Continue']",
            )
        )
    )
    verify_button.click()
    wait.until(
        lambda current_driver: current_driver.current_url != otp_url
        or not any(
            element.is_displayed()
            for element in current_driver.find_elements(
                By.CSS_SELECTOR, OTP_INPUTS
            )
        )
    )

    if any(
        element.is_displayed()
        for element in driver.find_elements(By.CSS_SELECTOR, OTP_INPUTS)
    ):
        raise RuntimeError(
            "The verification code was submitted, but the OTP inputs remain visible."
        )
