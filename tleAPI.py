import requests
import os
from dotenv import load_dotenv

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
    file.write("OBJECT_NAME,OBJECT_ID, ")
    for satellite in satData:
        file.write(f"{satellite["OBJECT_NAME"]},{satellite["OBJECT_ID"]}")