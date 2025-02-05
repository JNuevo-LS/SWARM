import requests
import logging
import os
from pathlib import Path
import time
import random
from dotenv import load_dotenv
from readData import createSatObj
from storage import uploadFile
# from notify import notify, log

load_dotenv() #Access .env login from your own account
random.seed()

logging.basicConfig(filename="tleapi.log",
                    level = logging.DEBUG,
                    format='%(asctime)s %(message)s',
                    filemode='a')

logging.info("Initializing Logging")

username = os.environ.get("USERNAME")
password = os.environ.get("PASSWORD")
bucket = os.environ.get("BUCKET_NAME")

def login(session):
    try:
        loginURL = 'https://www.space-track.org/ajaxauth/login' 
        payload = {
            'identity': username,
            'password': password
        }
        response = session.post(loginURL, data = payload)

        if response.status_code == 200:
            logging.info("Login Successful")
        else:
            logging.critical(f"LOGIN ERROR: {response.status_code}")
        return session
    except Exception as e:
        # notify(1)
        logging.critical(f"Failed to Authorize\nERROR: {e}")
        raise ConnectionError

def writeToCSV(satData, filePath):
    try:
        if not os.path.exists(filePath):
            logging.info(f"File '{filePath}' does not exist. Creating new one.")
            empty = True
        else:
            empty = False
        with open(filePath, "a") as file: #write API response to a csv
            if empty:
                file.write("name,satelliteCatalogNumber,securityClass,internationalDesignator,year,day,firstTimeDerivative,secondTimeDerivative,drag,inclination,RAAN,eccentricity,perigee,meanAnomaly,meanMotion\n")
            for satellite in satData:
                tle1 = satellite["TLE_LINE1"]
                tle2 = satellite["TLE_LINE2"]
                sat = createSatObj(satellite["OBJECT_NAME"], tle1, tle2)
                csv = sat.formatCSV()
                file.write(csv+"\n")
    except Exception as e:
        logging.critical(f"Failed to Write: {e}")
        raise RuntimeError(f"Failed to Write: {e}")

def checkAndUpload(filePath:str, forced:bool = False):
    if not os.path.exists(filePath):
        return False
    else:
        size = os.stat(filePath).st_size
        gib = size / 1073741824
        logging.info(f"Checking {filePath} size: {gib} GiB")
        if gib >= 1 or forced:
            uploadFile(filePath, filePath, bucket)
            os.remove(filePath)
            logging.info(f"Deleted {filePath}")
            return True
        else: return False

def queryAPI(url, session):
    for attempt in range(5):  # retries up to 5 times
        try:
            response = session.get(url)
            if response.status_code == 200:
                satData = response.json()
                logging.info(f"Received {len(satData)} records from {url}")
                return satData
            elif response.status_code in [265, 401, 403]:  # Unauthorized or Forbidden
                logging.warning("Session expired or unauthorized. Re-authenticating.")
                login(session)
                continue  # Retry after re-authentication
            else:
                logging.warning(f"Failed API Request to {url} with status {response.status_code}")
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < 4:
                sleep_time = 3
                logging.info(f"Sleeping for {sleep_time} seconds before retrying")
                time.sleep(sleep_time)
            else:
                logging.critical(f"Fatal API Request to {url} after {attempt + 1} attempts", exc_info=True)
                raise  #re-raise after final attempt

def main():
    session = requests.session()
    login(session)
    batchCount = 1
    satData = []
    day = 86400 #seconds in a day
    for i in range(1827): #20 years of data = 7305 days / 4 days per request = 1827 requests
        if i == 0:
            seconds = 1735689600 #2024-12-31
            endSeconds = seconds - (day * 4) # 4 days before

        start = time.strftime('%Y-%m-%d', time.localtime(seconds))
        end = time.strftime('%Y-%m-%d', time.localtime(endSeconds))
        seconds, endSeconds = endSeconds-day, endSeconds-(day * 5)

        url = f"https://www.space-track.org/basicspacedata/query/class/tle/EPOCH/{end}--{start}/ECCENTRICITY/%3C0.25/MEAN_MOTION/%3E11.25"
        satData.extend(queryAPI(url, session))
        
        if (i+1) % 12 == 0: #process in batches only - constraint 
            filePath = f"data/TLE_LEO.{batchCount}.csv" #default filename
            if checkAndUpload(filePath):
                batchCount += 1
                filePath = f"data/TLE_LEO.{batchCount}.csv"
            writeToCSV(satData, filePath)
            satData.clear()
        if i+1 == 1827:
            writeToCSV(satData, filePath) #write final request to csv
            checkAndUpload(filePath, forced=True) #force upload final file
            satData.clear()
            logging.info("TASK COMPLETED SUCCESSFULLY. EXITING PROGRAM.")

            break

        # notify(0, records = len(satData) + len(satData_latest), step = i)
        logging.info(f"Successful Cycle {i+1}/1827")

if __name__ == "__main__":
    main()