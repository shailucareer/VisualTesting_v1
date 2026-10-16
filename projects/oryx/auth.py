from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def authenticate(driver):
    login_url = "https://oryx.galaxyweblinks.in/en/customer/account/login/"
    email = "manager@yopmail.com"
    password = "kamlesh@123"

    driver.get(login_url)
    wait = WebDriverWait(driver, 30)

    email_input = wait.until(
        EC.visibility_of_element_located((By.ID, "login-email"))
    )
    email_input.send_keys(email)

    password_input = wait.until(
        EC.visibility_of_element_located((By.ID, "login-password"))
    )
    password_input.send_keys(password)

    enter_button = wait.until(
        EC.element_to_be_clickable((By.ID, "login-btn"))
    )
    enter_button.click()

    wait.until(
        lambda current_driver: "/customer/account/login" not in current_driver.current_url
    )