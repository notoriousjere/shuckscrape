import os
from croniter import croniter

cron = os.environ.get("CRON", "0 */8 * * *")
if not croniter.is_valid(cron):
    raise ValueError(f"Invalid cron expression: {cron}")

with open("/app/crontab", "w+") as f:
    f.write(f"{cron} python -u /app/shuckscrape.py\n")
