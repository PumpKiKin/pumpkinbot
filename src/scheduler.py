from apscheduler.schedulers.blocking import BlockingScheduler
from src.config_loader import load_config
import subprocess

cfg = load_config("scheduler")
sched = BlockingScheduler()

@sched.scheduled_job("interval", minutes=cfg["notice_page"]["interval_minutes"])
def update_notices():
    subprocess.run(["poetry", "run", "crawl-detail"])  # or scripts/crawl_detail.py

def main():
    sched.start()
