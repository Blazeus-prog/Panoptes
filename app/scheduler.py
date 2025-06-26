from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz


from app.routes.price_history import (
    run_kelz0r_scraper,
    run_matraws_scraper,
    run_pokemons_scraper,
    run_qubimon_scraper,
    run_rogerz_scraper
)

COPENHAGEN_TZ = pytz.timezone("Europe/Copenhagen")
scheduler = BackgroundScheduler(timezone=COPENHAGEN_TZ)

def scrape_all_sites():
    print(f"[🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running scrape_all_sites()")
    run_kelz0r_scraper()
    run_matraws_scraper()
    run_pokemons_scraper()
    run_qubimon_scraper()
    run_rogerz_scraper()

def start():
    scheduler.add_job(
        scrape_all_sites,
        "cron",
        hour=10,
        minute=0,
        id="scrape_all_sites_test",
        replace_existing=True
    )
    scheduler.start()
    print("✅ APScheduler started — scrape_all_sites() runs every day @ 10:00")
 