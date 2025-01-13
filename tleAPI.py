import requests
import os
import time
import random
from dotenv import load_dotenv
from readData import createSatObj
from notify import notify, log

load_dotenv() #Access .env login from your own account
random.seed()

username = os.environ.get("USERNAME")
password = os.environ.get("PASSWORD")

def login():
    try:
        loginURL = 'https://www.space-track.org/ajaxauth/login' 
        session = requests.Session()
        payload = {
            'identity': username,
            'password': password
        }
        response = session.post(loginURL, data = payload)

        if response.status_code == 200:
            log("Login Successful")
        else:
            log(f"LOGIN ERROR: {response.status_code}")
        return session
    except Exception as e:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
        notify(1)
        log(f"Failed to Authorize\n{t}\nERROR: {e}\n")
        log(t, 1) #Logs time in case of failure, to make restarting easier

def writeToCSV(satData):
    with open("data/LEO_TLE.csv", "a") as file: #write API response to a csv
        if (os.stat("data/LEO_TLE.csv").st_size == 0): #if file is empty
            file.write("name,NORAD,internationalDesignator,epochTime,firstTimeDerivative,secondTimeDerivative,drag,inclination,RAAN,eccentricity,perigee,meanAnomaly,meanMotion\n")
        for satellite in satData:
            tle1 = satellite["TLE_LINE1"]
            tle2 = satellite["TLE_LINE2"]
            sat = createSatObj(satellite["OBJECT_NAME"], tle1, tle2)
            csv = sat.formatCSV()
            file.write(csv+"\n")

def queryAPI(url, session):
    response = session.get(url)
    if response.status_code == 200:
        satData = response.json()  
        log(f"Received {len(satData)} records")
        return satData
    else:
        notify(2)
        log(f"Failed API Request\nERROR: {response.status_code}\n")
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time())) 
        log(t, 1)

for i in range(730): # 365 days * 10 (years of data) = 3650 days / 5 days per request = 730 requests | Ignoring leap years
    session = login()

    day = 86400 #seconds in a day, 60*60*24

    if i == 0:
        seconds = time.time()
        endSeconds = seconds - (day * 5) # 5 days before

    start = time.strftime('%Y-%m-%d', time.localtime(seconds))
    end = time.strftime('%Y-%m-%d', time.localtime(endSeconds))
    seconds, endSeconds = endSeconds-day, endSeconds-(day * 6) #sets seconds to the day before, and endSeconds to 6 days before for the next loop

    url_latest = f"https://www.space-track.org/basicspacedata/query/class/tle_latest/EPOCH/{end}--{start}/ECCENTRICITY/%3C0.25/MEAN_MOTION/%3E11.25"
    url = f"https://www.space-track.org/basicspacedata/query/class/tle/EPOCH/{end}--{start}/ECCENTRICITY/%3C0.25/MEAN_MOTION/%3E11.25"

    satData_latest = queryAPI(url_latest, session)
    satData = queryAPI(url, session)

    t = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time())) 
    try:
        writeToCSV(satData_latest)
        writeToCSV(satData)

        notify(0, len(satData))
        log(f"Successful Cycle\n{t}\n")
    except Exception as e:
        notify(3)
        log(f"Failed to write data\n{t}\nError: {e}\n")
        log(t, 1)
        exit()
    
    sleepTime = (random.random() * 1800) + 3600
    time.sleep(sleepTime) #randomly waits range of [1,1.5] hours
    #Needed as per Space-Track.org's request to limit TLE queries to 1/hour and randomize the minute.