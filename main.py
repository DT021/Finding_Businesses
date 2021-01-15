# -*- coding: utf-8 -*-
import os
import time
import traceback
import re
import json
import csv
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

base_dir = os.path.dirname(os.path.abspath(__file__))
output_csv_path = base_dir + "/result.csv"
config_path = base_dir + "/config.json"

class Crawler():

    # init
    def __init__(self):
        # init web driver
        self.driver = None

        # business List of Google Search Result
        self.businessList = list()

        # max trying count to get url on driver
        self.maxTryValue = 3

        self.cityList = list()
        self.city = ""
        self.business = ""
        self.useApiFlag = True
        self.jobTitlePatterns = list()
        self.apiKey = ""
        returnData = self.getConfigData()

        if not returnData["flag"]:
            print(returnData["message"])
            return

    # get query list
    def getConfigData(self):
        returnData = dict()
        try:
            config_exist = os.path.isfile(config_path)
            if config_exist:
                with open(config_path) as f:
                    config = json.load(f)
                    print(json.dumps(config, indent=2))
                
                self.apiKey = config["Key"]
                self.business = config["Business"]
                self.jobTitlePatterns = config["JobTitle"]
                self.cityList = config["CityList"]
                self.useApiFlag = config["UseApiFlag"]

                returnData["flag"] = True
                returnData["message"] = "Success"
                return returnData
                
            else:
                returnData["flag"] = False
                returnData["message"] = "Can not find cofig file. Confirm and Try again."
                return returnData
        except:
            returnData["flag"] = False
            returnData["message"] = "Raised some error. Confirm config and Try again."
            return returnData

    # create driver
    def setDriver(self):
        try:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                'Chrome/80.0.3987.132 Safari/537.36')

            driver = webdriver.Chrome(ChromeDriverManager().install(), options = chrome_options, service_args=['--verbose', '--log-path={}/webdriver.log'.format(base_dir)])
            driver.maximize_window()
            return driver

        except:
            return None

    # convert url to domain
    def convertURLToDomain(self, url):
        try:
            if "#" in url:
                url = url.split("#")[0]
            if re.search(r"http\:\/\/|https\:\/\/", url):
                url = url.split(re.search(r"http\:\/\/|https\:\/\/", url).group(), 1)[1].split("/", 1)[0].split('?', 1)[0]
            if "www" in url:
                url = url[4:]

            return url.lower()
        except:
            traceback.print_exc()
            return url.lower()

    # get url on driver
    def getURLonDriver(self, url):
        i = 0
        while i < self.maxTryValue:
            try:
                i += 1
                self.driver.get(url)
                break
            except:
                traceback.print_exc()
                if self.driver is not None:
                    self.driver.quit()
                    self.driver = None
                    print("Driver Closed!")
                    
                self.driver = self.setDriver()
                continue
                
    # get owner name
    def getOwnerName(self, business_dict):
        tries = 6
        for i in range(tries):
            try:
                job_title = "Owner"

                if business_dict["Business Website"]:
                    domain = self.convertURLToDomain(business_dict["Business Website"]).strip()
                    data = {'domain': domain, 'preferred_title': job_title}
                else:
                    company_name = business_dict["Business Name"].strip()
                    data = {'company_name': company_name, 'preferred_title': job_title}

                headers = {'X-Api-Key': self.apiKey}

                resp = requests.post('https://api.anymailfinder.com/v4.1/search/employees.json', data=data, headers=headers)
                result = json.loads(resp.content)
                print(resp.status_code, result)
                if resp.status_code == 404:
                    return "", "", ""
                elif resp.status_code == 202:
                    time.sleep(i)
                    continue
                elif resp.status_code == 200:
                    if result["employees"]:
                        for jobTitlePattern in self.jobTitlePatterns:
                            for employee in result["employees"]:
                                if jobTitlePattern.lower() in employee["title"].lower():
                                    return employee["name"], employee["linkedin_url"], employee["title"]

                        return result["employees"][0]["name"], employee["linkedin_url"], result["employees"][0]["title"]
                    return "", "", ""
                else:
                    print(result)
                    return "", "", ""

            except:
                traceback.print_exc()
                continue

        return "", "", ""

    # get owner info
    def getOwnerInfo(self, ownerName, business_dict):
        tries = 6
        for i in range(tries):
            try:
                if business_dict["Business Website"]:
                    domain = self.convertURLToDomain(business_dict["Business Website"]).strip()
                    data = {'domain': domain, 'full_name': ownerName}
                else:
                    company_name = business_dict["Business Name"].lower().strip()
                    data = {'company_name': company_name, 'full_name': ownerName}

                headers = {'X-Api-Key': self.apiKey}

                response = requests.post("https://api.anymailfinder.com/v4.1/search/person.json", headers=headers, data=data)
                result = json.loads(response.content)

                if response.status_code == 404:
                    return ""
                elif response.status_code == 202:
                    time.sleep(i)
                    continue
                elif response.status_code == 200:
                    if result["email"]:
                        return result["email"]
    
                    return ""
                else:
                    continue

            except:
                traceback.print_exc()
                continue

        return ""

    # get Businesses on Google
    def getBusinesses(self, oldUrl):
        try:
            # wait until url is changed
            WebDriverWait(self.driver, 30).until(EC.url_changes(oldUrl))
            time.sleep(2)

            businesses = []
            businesses = self.driver.find_elements_by_xpath("//div[@class='section-result-content']")

            for business in businesses:
                business_dict = {
                    "Business Name": "",
                    "Location": self.city,
                    "Business Website": "",
                }

                try:
                    company_name = business.find_element_by_xpath(".//h3[@class='section-result-title']/span").text
                    if company_name:
                        business_dict["Business Name"] = company_name.strip()

                        try:
                            business_dict["Business Website"] = business.find_element_by_xpath(".//div[@class='section-result-action-container']/div[1]/a[@href]").get_attribute("href")
                        except:
                            pass
                        
                        self.businessList.append(business_dict)

                        if self.useApiFlag:
                            ownerName, linkedin_url, jobTitle = self.getOwnerName(business_dict)

                            if ownerName:
                                ownerEmail = self.getOwnerInfo(ownerName, business_dict)
                            else:
                                ownerEmail = ""

                        else:
                            ownerName, linkedin_url, jobTitle, ownerEmail = "", "", "", ""

                        final_dict = business_dict.copy()
                        final_dict["Business Website"] = self.convertURLToDomain(final_dict["Business Website"])

                        if ownerName:
                            final_dict["First Name"] = ownerName.rsplit(" ", 1)[1]
                            final_dict["Last Name"] = ownerName.rsplit(" ", 1)[0]
                        else:
                            final_dict["First Name"] = ""
                            final_dict["Last Name"] = ""

                        final_dict["Job Title"] = jobTitle
                        final_dict["Contact Website"] = linkedin_url
                        final_dict["Email"] = ownerEmail

                        if ownerName:
                            final_dict["Source"] = "API"
                        else:
                            final_dict["Source"] = "Google"

                        # insert data to csv file.
                        file_exist = os.path.isfile(output_csv_path)
                        with open(output_csv_path, 'a', newline="", encoding="utf-8") as output_file:
                            fieldnames = ["First Name", "Last Name", "Job Title", "Location", "Email", "Source", "Business Name", "Business Website", "Contact Website"]
                            writer = csv.DictWriter(output_file, fieldnames=fieldnames)

                            # wirte fileds if file not exist
                            if not file_exist:
                                writer.writeheader()

                            writer.writerow(final_dict)

                        print("-----------------------------------")
                        print("Found `{}` Business".format(final_dict["Business Name"]))
                        print("Domain: ", final_dict["Business Website"])

                        if self.useApiFlag:
                            print("Name: ", final_dict["First Name"], final_dict["Last Name"])
                            print("Job Title: ", final_dict["Job Title"])
                            print("Email: ", final_dict["Email"])

                except:
                    traceback.print_exc()
                    continue
                
        except:
            traceback.print_exc()
            pass

        
        # pagination
        try:
            pagination_element = self.driver.find_element_by_xpath("//button[@aria-label=' Next page ']")
            
            if pagination_element:
                if pagination_element.is_enabled() and pagination_element.is_displayed():
                    current_url = self.driver.current_url
                    pagination_element.click()
                    print("----- Clicked Page Next Button -----")
                    return True, current_url
            else:
                print("Can not Find Pagination Button.")
            
            return False, ""
        except NoSuchElementException:
            print("Can not Find Pagination Button.")
            return False, ""
        except WebDriverException:
            print("Next Button Not Clickable.")
            return False, ""
        except:
            traceback.print_exc()
            return False, ""

    # get Business Detail Info on Detail Website
    def getBusinessDetails(self):
        for businessDetail in self.businessList:
            try:
                print("Getting Data From", businessDetail["Business Name"])
                self.getURLonDriver(businessDetail["Business Website"])
                WebDriverWait(self.driver, 30).until(lambda driver: driver.find_element_by_tag_name("body").get_attribute("innerHTML").strip())
                time.sleep(5)
                self.driver.save_screenshot("{}/imgs/{}.png".format(base_dir, businessDetail["Business Name"].replace(" ", "_")))
            except:
                traceback.print_exc()
                time.sleep(10)
                continue

    # main function
    def start(self):
        for city in self.cityList:
            if not city:
                continue

            self.city = city

            # Search from Google.
            try:
                query = ("{} in {} city".format(self.business, self.city.split(",")[0].strip())).replace(" ", "+")
                search_url = "http://maps.google.com/?q={}".format(query)
                
                # create web driver
                self.driver = self.setDriver()
                
                if self.driver is None:
                    print("Can Not Create Driver. Please Try Again.")
                    return

                # get inventory url
                self.getURLonDriver(search_url)

                # get podiartist offices
                next_flag = True
                current_url = ""
                while True:
                    next_flag, current_url = self.getBusinesses(current_url)
                    
                    if not next_flag:
                        break
                            
                else:
                    print("Can Not Find Google Search Result. Try Again With Other Query.")
                    return

                # get business detail info & photo
                # self.getBusinessDetails()

            except:
                traceback.print_exc()
            finally:

                if self.driver is not None:
                    self.driver.quit()
                    self.driver = None
            
if __name__ == "__main__":
    # delete result csv file 
    file_exist = os.path.isfile(output_csv_path)
    if file_exist:
        os.remove(output_csv_path)

    crawler = Crawler()
    crawler.start()
    
