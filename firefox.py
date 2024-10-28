from selenium import webdriver
from selenium.common.exceptions import WebDriverException

try:
    # Attempt to initialize Firefox WebDriver
    driver = webdriver.Firefox()
    print("Selenium successfully initialized Firefox.")
    driver.quit()  # Close the browser if successful
except WebDriverException as e:
    print("Selenium failed to initialize Firefox:", e)
