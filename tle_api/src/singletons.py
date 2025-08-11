from ratelimit import sleep_and_retry, limits
import requests
import logging
from pathlib import Path
from read_data import create_sat
import os
import zstandard

logger = logging.getLogger()

class Singleton():
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton,cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class ApiClient(metaclass=Singleton):
    def __init__(self, login_config: dict):
        self.login_config = login_config
        self.session = requests.Session()
        self.login()

    def login(self):
        try:
            loginURL = 'https://www.space-track.org/ajaxauth/login' 
            payload = {
                'identity': self.login_config.get("username"),
                'password': self.login_config.get("password")
            }
            response = self.session.post(loginURL, data = payload)

            response.raise_for_status()
            logger.info("Login Successful")
        except Exception as e:
            logger.critical(f"Failed to Authorize\nERROR: {e}")
            raise ConnectionError(f"Failed to login: {e}")
        
    def call_api(self, endpoint: str):
        try:
            response = self.session.get(endpoint)
            sat_data = response.json()
            if response.status_code == 200 and len(sat_data) > 1:
                logger.info(f"Received {len(sat_data)} records from {endpoint}")
                return sat_data
            elif response.status_code == 403:  # Forbidden
                logger.info("Session expired. Re-authenticating.")
                self.login()
            else:
                response.raise_for_status()
        except Exception as e:
            logger.critical(f"API call failed: {e}")
            raise RuntimeError(f"API call failed: {e}")
        
class FileHandler(metaclass=Singleton):
    def __init__(self):
        self.file = None
        self.batch_count = 0

        self.compressor = zstandard.ZstdCompressor()

        if not Path("data").exists():
            Path("data").mkdir()
            logger.info("Created data directory")

    def write_to_csv(self, sat_data):
        file_path = f"data/TLE_LEO_{self.batch_count}.csv"
        with open(file_path, "a") as file:
            with self.compressor.stream_writer(file) as compressor_writer:
                compressor_writer.write("name,satelliteCatalogNumber,securityClass,internationalDesignator,year,day,firstTimeDerivative,secondTimeDerivative,drag,inclination,RAAN,eccentricity,perigee,meanAnomaly,meanMotion,revolutionNumber\n")
                for satellite in sat_data:
                    tle1 = satellite["TLE_LINE1"]
                    tle2 = satellite["TLE_LINE2"]
                    sat = create_sat(satellite["OBJECT_NAME"], tle1, tle2)
                    csv = sat.format_CSV()
                    compressor_writer.write(csv+"\n")
        file_size = os.stat(file_path).st_size / 1073741824  # Convert bytes to GiB
        logger.info(f"Data written to {file_path} | Size after compression: {file_size}")
        self.batch_count += 1

