from selenium import webdriver
import os
import subprocess
try:
    path = subprocess.check_output(['where', 'geckodriver'], stderr=subprocess.STDOUT)
    print(path.decode().strip())
except subprocess.CalledProcessError as e:
    print("geckodriver not found in PATH. Error: ", e.output.decode().strip())
driver = webdriver.Firefox()
path = subprocess.check_output(['where', 'geckodriver'])
print(path.decode().strip())
driver.quit()
