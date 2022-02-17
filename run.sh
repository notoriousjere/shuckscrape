#!bin/sh

cd /app
python make_crontab.py
echo "crontab:"
cat crontab
crontab crontab
crond -f
