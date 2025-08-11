import logging
import os
import time
import random
from dotenv import load_dotenv
from singletons import ApiClient, FileHandler


load_dotenv() # Access .env login from your own account

logging.basicConfig(filename="tleapi.log",
                    level = logging.DEBUG,
                    format='%(asctime)s %(message)s',
                    filemode='a')

USERNAME = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")

def main():
    api_client = ApiClient({"username": USERNAME, "password": PASSWORD})
    file_handler = FileHandler()
    sat_data = []

    DAY = 86400 # seconds in a day
    MAX_RANGE = 1827 # 20 years of data = 7305 days / 4 days per request = 1827 requests

    for i in range(MAX_RANGE): 
        if i == 0:
            seconds = 1735689600 #2024-12-31 = 1735689600
            end_seconds = seconds - (DAY * 4) # 4 days before

        logging.info(f"Seconds: {seconds}")

        start = time.strftime('%Y-%m-%d', time.localtime(seconds))
        end = time.strftime('%Y-%m-%d', time.localtime(end_seconds))
        seconds, end_seconds = end_seconds-DAY, end_seconds-(DAY * 5)

        endpoint = f"https://www.space-track.org/basicspacedata/query/class/tle/EPOCH/{end}--{start}/ECCENTRICITY/%3C0.25/MEAN_MOTION/%3E11.25"
        sat_data.extend(api_client.call_api(endpoint))

        if (i+1) % 10 == 0: # process in batches only - constraint
            file_handler.write_to_csv(sat_data)
            sat_data.clear()
        if i+1 == MAX_RANGE:
            file_handler.write_to_csv(sat_data) # write final request to csv
            sat_data.clear()
            logging.info("TASK COMPLETED SUCCESSFULLY. EXITING PROGRAM.")
            break

        logging.info(f"Successful Cycle {i+1}/{MAX_RANGE}")

if __name__ == "__main__":
    main()