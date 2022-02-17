FROM python:3.6.12-alpine3.12

COPY . /app
WORKDIR /app

RUN apk update && \
    apk add --no-cache tzdata

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["sh", "/app/run.sh"]
