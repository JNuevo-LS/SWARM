import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time
from dotenv import load_dotenv

load_dotenv()

email = os.environ.get("EMAIL")
password = os.environ.get("APP_PASSWORD")

def log(data, fileCode = 0):
    match fileCode:
        case 0:
            filepath = "data/logs.txt"
        case 1:
            filepath = "data/time.txt"

    with open(filepath, "a") as file:
        file.write(f"{data}\n")

def notify(code:int, records = 0):
    try:
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = email
        msg.attach(MIMEText(f"Gathered n = {records} records", 'plain')) #body

        match code:
            case 0:
                msg['subject'] = "API request successful. No issues."
            case 1:
                msg['subject'] = "FAILED TO AUTHORIZE"
            case 2:
                msg['subject'] = "FAILED TO FETCH DATA"
            case 3:
                msg['subject'] = "FAILED TO WRITE DATA TO CSV"

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  #encrypts the connection
            server.login(email, password) 
            server.send_message(msg)

    except Exception as e:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time())) 
        log(f"Failed to send email\n{t}\nERROR:\n{e}\n")