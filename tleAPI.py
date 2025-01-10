import requests
import os
import time
import random
from dotenv import load_dotenv
from readData import createSatObj

load_dotenv() #Access .env login from your own account
random.seed()

username = os.environ.get("USERNAME")
password = os.environ.get("PASSWORD")

def login():
    loginURL = 'https://www.space-track.org/ajaxauth/login' 
    session = requests.Session()
    payload = {
        'identity': username,
        'password': password
    }
    response = session.post(loginURL, data = payload)

    if response.status_code == 200:
        print("Login Successful")
    else:
        print(f"ERROR: {response.status_code}")
    
    return session

seconds = time.time()
endSeconds = seconds - 604800

def formatTime(seconds, endSeconds):
    start = time.strftime('%Y-%m-%d', time.localtime(seconds)) #format start to current day
    end = time.strftime('%Y-%m-%d', time.localtime(endSeconds)) #format end to 7 days prior
    return (start, end)

for i in range(260): # 52 weeks/year (estimate) * 5 years = 260 requests
    session = login()

    start, end = formatTime(seconds, endSeconds)
    seconds, endSeconds = endSeconds-86400, endSeconds-691200 #sets seconds to the day before, and endSeconds to 7 days before for the next loop

    url = f"https://www.space-track.org/basicspacedata/query/class/tle_latest/EPOCH/{end}--{start}/ECCENTRICITY/%3C0.25/MEAN_MOTION/%3E11.25"

    response = session.get(url)
    if response.status_code == 200:
        satData = response.json()  
        print(f"Received {len(satData)} records")

    with open("data/LEO_TLE.csv", "w") as file: #write API response to a csv
        if (os.stat("data/LEO_TLE.csv").st_size() == 0): #if file is empty
            file.write("name,NORAD,internationalDesignator,epochTime,firstTimeDerivative,secondTimeDerivative,drag,inclination,RAAN,eccentricity,perigee,meanAnomaly,meanMotion\n")
        for satellite in satData:
            tle1 = satellite["TLE_LINE1"]
            tle2 = satellite["TLE_LINE2"]
            sat = createSatObj(satellite["OBJECT_NAME"], tle1, tle2)
            csv = sat.formatCSV()
            file.write(csv+"\n")
    
    sleepTime = (random.random() * 3600) + 3600
    time.sleep(sleepTime) #randomly waits range of [1,2] hours