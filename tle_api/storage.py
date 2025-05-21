import boto3
import pathlib
from pprint import pprint
import os
import logging
from dotenv import load_dotenv

load_dotenv()

accessKey = os.environ.get("ACCESS_KEY")
secretAccessKey = os.environ.get("SECRET_ACCESS_KEY")
regionName = os.environ.get("REGION_NAME")

def uploadFile(name:str, path:str, bucket:str): #uploads file on local to amazon s3 bucket
    s3 = boto3.client(
        "s3",
        aws_access_key_id = accessKey,
        aws_secret_access_key = secretAccessKey,
        region_name = regionName)
    filePath = os.path.join(pathlib.Path(__file__).parent.resolve(), name)
    response = s3.upload_file(filePath, bucket, name)
    
    logging.info(f"Uploaded {path} to S3 Bucket '{bucket}' as {name}")