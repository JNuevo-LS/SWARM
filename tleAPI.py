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

for i in range(520): # 52 weeks/year (estimate) * 10 years = 520 requests
    session = login()

    start, end = formatTime(seconds, endSeconds)
    seconds, endSeconds = endSeconds-86400, endSeconds-691200 #sets seconds to the day before, and endSeconds to 7 days before for the next loop

    url = f"https://www.space-track.org/basicspacedata/query/class/tle_latest/EPOCH/{end}--{start}/ECCENTRICITY/%3C0.25/MEAN_MOTION/%3E11.25"

    response = session.get(url)
    if response.status_code == 200:
        satData = response.json()  
        print(f"Received {len(satData)} records")
    else:
        print(f"ERROR: {response.status_code}")

    with open("data/LEO_TLE.csv", "w") as file: #write API response to a csv
        if (os.stat("data/LEO_TLE.csv").st_size == 0): #if file is empty
            file.write("name,NORAD,internationalDesignator,epochTime,firstTimeDerivative,secondTimeDerivative,drag,inclination,RAAN,eccentricity,perigee,meanAnomaly,meanMotion\n")
        for satellite in satData:
            tle1 = satellite["TLE_LINE1"]
            tle2 = satellite["TLE_LINE2"]
            sat = createSatObj(satellite["OBJECT_NAME"], tle1, tle2)
            csv = sat.formatCSV()
            file.write(csv+"\n")
    
    sleepTime = (random.random() * 1800) + 3600
    print(f"Next request in about {sleepTime/60} minutes")
    time.sleep(sleepTime) #randomly waits range of [1,1.5] hours
    #Needed as per Space-Track.org's request to limit TLE queries to 1/hour and randomize the minute.