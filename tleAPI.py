import requests
import os
from dotenv import load_dotenv
from readData import parseObjData, createSatObj

load_dotenv()

username = os.environ.get("USERNAME")
password = os.environ.get("PASSWORD")

loginURL = 'https://www.space-track.org/ajaxauth/login'
url = "https://www.space-track.org/basicspacedata/query/class/satcat/OBJECT_TYPE/PAYLOAD/DECAY/null/LAUNCH_DATE/>2010-01-01/orderby/LAUNCH_DATE"

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
    exit()

response = session.get(url)
if response.status_code == 200:
    satData = response.json()
    print(f"Received {len(satData)} records")

with open("data/LEO_3LE.csv", "w") as file:
    file.write("name,NORAD,internationalDesignator,epochTime,firstTimeDerivative,secondTimeDerivative,drag,inclination,RAAN,eccentricity,perigee,meanAnomaly,meanMotion")
    for satellite in satData:
        tle1 = satellite["TLE_LINE1"]
        tle2 = satellite["TLE_LINE2"]
        sat = createSatObj(satellite["OBJECT_NAME"], tle1, tle2)
        file.write(satellite["OBJECT_NAME"] + "," + satellite["OBJECT_ID"])
        