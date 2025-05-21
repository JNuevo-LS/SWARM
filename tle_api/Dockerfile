FROM python:3.13.1-slim

WORKDIR /app

ADD requirements.txt ./
ADD .env ./
ADD readData.py ./
ADD tleAPI.py ./
ADD notify.py ./
ADD storage.py ./

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/data

VOLUME [ "/app/data" ]

CMD ["python3", "tleAPI.py"]