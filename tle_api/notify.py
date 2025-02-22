import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

email = os.environ.get("EMAIL")
password = os.environ.get("APP_PASSWORD")

def log(data):
    with open("data/logs.txt", "a") as file:
        file.write(f"{data}\n")

def notify(code:int, e = "", records = 0, step:int = 0):
    try:
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = email

        match code:
            case 0:
                msg['subject'] = f"API request successful. #{step+1}/730"
                body = f"Gathered n = {records} records"
            case 1:
                msg['subject'] = f"FAILED TO AUTHORIZE #{step+1}/730"
                body = f"ERROR: {e}"
            case 2:
                msg['subject'] = f"FAILED TO FETCH DATA #{step+1}/730"
                body = f"ERROR: {e}"
            case 3:
                msg['subject'] = f"FAILED TO WRITE DATA TO CSV #{step+1}/730"
                body = f"ERROR: {e}"
        
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  #encrypts the connection
            server.login(email, password)
            server.send_message(msg)

    except Exception as e:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time())) 
        logging.error(f"Failed to send email\n{t}\nERROR:\n{e}\n")