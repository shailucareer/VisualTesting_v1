from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def authenticate(driver):
    login_url = "https://gwl-testing-apps.myshopify.com/password"
    store_password = "123456"

    driver.get(login_url)
    wait = WebDriverWait(driver, 30)

    password_input = wait.until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
    )
    password_input.send_keys(store_password)

    enter_button = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
        )
    )
    enter_button.click()

    wait.until(lambda current_driver: "/password" not in current_driver.current_url)