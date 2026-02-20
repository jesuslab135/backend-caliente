"""
Management command to scrape sport events from Flashscore.

Uses Playwright + BeautifulSoup to navigate specific league fixture pages,
extract upcoming matches, and import only NEW events via the import service.

Deduplication: Checks (league_name + home_team + away_team + date_start)
to avoid importing duplicates on repeated scrapes.

Usage:
    python manage.py scrape_flashscore
    python manage.py scrape_flashscore --urls "https://www.flashscore.com/football/spain/laliga/fixtures/"
"""
import csv
import io
import logging
import re
from datetime import datetime

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# Default league fixture URLs to scrape
DEFAULT_URLS = [
    # Football
    "https://www.flashscore.com/football/france/ligue-1/fixtures/",
    "https://www.flashscore.com/football/germany/bundesliga/fixtures/",
    "https://www.flashscore.com/football/italy/serie-a/fixtures/",
    "https://www.flashscore.com/football/netherlands/eredivisie/fixtures/",
    "https://www.flashscore.com/football/spain/laliga/fixtures/",
    "https://www.flashscore.com/football/england/premier-league/fixtures/",
    "https://www.flashscore.com/football/europe/champions-league/fixtures/",
    "https://www.flashscore.com/football/mexico/liga-mx/fixtures/",
    # Tennis
    "https://www.flashscore.com/tennis/atp-singles/australian-open/fixtures/",
    "https://www.flashscore.com/tennis/atp-singles/french-open/fixtures/",
    # Basketball
    "https://www.flashscore.com/basketball/usa/nba/fixtures/",
    # Baseball
    "https://www.flashscore.com/baseball/usa/mlb/fixtures/",
    "https://www.flashscore.com/baseball/mexico/lmb/fixtures/",
    # Ice Hockey
    "https://www.flashscore.com/hockey/usa/nhl/fixtures/",
]


class Command(BaseCommand):
    help = 'Scrape upcoming sport events from Flashscore fixture pages and import new ones.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--urls',
            nargs='*',
            default=None,
            help='Specific Flashscore fixture URLs to scrape (default: all configured)',
        )

    def handle(self, *args, **options):
        urls = options['urls'] or DEFAULT_URLS
        result = run_scraper(urls=urls)
        self.stdout.write(
            self.style.SUCCESS(
                f'Scraping completado: {result["imported"]} nuevos eventos importados '
                f'({result.get("skipped", 0)} duplicados omitidos).'
            )
        )
        if result.get('errors'):
            for err in result['errors']:
                self.stdout.write(self.style.WARNING(f'  {err}'))


def _parse_url_metadata(url):
    """Extract sport, country, and league name from a Flashscore fixture URL."""
    try:
        clean = url.replace("https://www.", "").replace("http://www.", "").replace("flashscore.com/", "")
        parts = clean.split("/")
        sport = parts[0].capitalize()
        country = parts[1].replace("-", " ").title()
        league = parts[2].replace("-", " ").title()
        return sport, country, league
    except (IndexError, AttributeError):
        return "Unknown", "Unknown", "Unknown"


def run_scraper(urls=None):
    """
    Main scraper function. Navigates Flashscore fixture pages, extracts matches,
    deduplicates against existing DB records, and imports only new events.

    Returns dict with 'imported', 'skipped', and 'errors'.
    """
    if urls is None:
        urls = DEFAULT_URLS

    try:
        from playwright.sync_api import sync_playwright
        from bs4 import BeautifulSoup
    except ImportError as e:
        return {
            'imported': 0,
            'skipped': 0,
            'errors': [
                f'Dependencias no instaladas: {e}. '
                'Ejecuta: pip install playwright beautifulsoup4 && playwright install chromium'
            ],
        }

    rows = []
    current_year = datetime.now().year

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Accept cookies on first visit
            try:
                page.goto("https://www.flashscore.com/", timeout=30000)
                page.click("#onetrust-accept-btn-handler", timeout=4000)
            except Exception:
                pass

            for url in urls:
                sport, country, league = _parse_url_metadata(url)
                logger.info(f'Scraping: {league} ({country}) - {sport}')

                try:
                    page.goto(url, timeout=30000)

                    # Wait for match elements (universal g_ ID prefix)
                    try:
                        page.wait_for_selector("div[id^='g_']", timeout=10000)
                    except Exception:
                        logger.info(f'  No matches found for {league}')
                        continue

                    html = page.content()
                    soup = BeautifulSoup(html, 'lxml')

                    match_rows = soup.find_all("div", id=re.compile(r"^g_\d+_"))
                    if not match_rows:
                        continue

                    for row_el in match_rows:
                        full_text = row_el.get_text(separator="|", strip=True)
                        text_parts = full_text.split("|")

                        match_date = ""
                        match_time = ""
                        home_team = ""
                        away_team = ""

                        # Extract date/time: pattern "DD.MM. HH:MM"
                        time_index = -1
                        for i, part in enumerate(text_parts):
                            if re.search(r"\d{2}\.\d{2}\.\s+\d{2}:\d{2}", part):
                                raw_dt = part.replace("FRO", "").strip()
                                split_dt = raw_dt.split()
                                if len(split_dt) >= 2:
                                    match_date = f"{split_dt[0]}{current_year}"
                                    match_time = split_dt[1]
                                    time_index = i
                                    break

                        if time_index == -1:
                            continue

                        # Extract teams: first 2 non-noise text parts after the time
                        noise = {"-", "FRO", "Postp", "Finished", "Awrd", "After OT", ""}
                        potential_teams = []
                        for k in range(time_index + 1, len(text_parts)):
                            val = text_parts[k].strip()
                            if val in noise or re.search(r"^\d+$", val):
                                continue
                            potential_teams.append(val)
                            if len(potential_teams) == 2:
                                break

                        if len(potential_teams) == 2:
                            home_team = potential_teams[0]
                            away_team = potential_teams[1]

                        if home_team and away_team and home_team != away_team:
                            rows.append({
                                'League': league,
                                'Country': country,
                                'Sport': sport,
                                'Date': match_date,
                                'Time': match_time,
                                'Home Team': home_team,
                                'Away Team': away_team,
                            })

                except Exception as e:
                    logger.warning(f'Error scraping {url}: {e}')
                    continue

            browser.close()

    except Exception as e:
        return {'imported': 0, 'skipped': 0, 'errors': [f'Error al ejecutar el scraper: {e}']}

    if not rows:
        return {'imported': 0, 'skipped': 0, 'errors': ['No se encontraron eventos nuevos.']}

    return _import_rows_dedup(rows)


def _import_rows_dedup(rows):
    """
    Import scraped rows, skipping events that already exist in the database.
    Deduplication key: (league_name, home_team, away_team, date_start date).
    """
    import django
    django.setup()
    from api.models import SportEvent, League
    from api.services.importers.sport_event_import_service import SportEventImportService

    # Build set of existing events for fast lookup
    existing = set()
    for ev in SportEvent.objects.select_related('league').only(
        'league__name', 'home_team', 'away_team', 'date_start'
    ):
        key = (
            ev.league.name.strip().lower(),
            ev.home_team.strip().lower(),
            ev.away_team.strip().lower(),
            ev.date_start.strftime('%d.%m.%Y') if ev.date_start else '',
        )
        existing.add(key)

    # Filter out duplicates
    new_rows = []
    skipped = 0
    for row in rows:
        key = (
            row['League'].strip().lower(),
            row['Home Team'].strip().lower(),
            row['Away Team'].strip().lower(),
            row['Date'].strip(),
        )
        if key in existing:
            skipped += 1
        else:
            new_rows.append(row)
            existing.add(key)  # Avoid dupes within same batch

    if not new_rows:
        return {'imported': 0, 'skipped': skipped, 'errors': []}

    # Feed new rows through import service via CSV
    output = io.StringIO()
    fieldnames = ['League', 'Country', 'Sport', 'Date', 'Time', 'Home Team', 'Away Team']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(new_rows)

    csv_content = output.getvalue().encode('utf-8')
    csv_file = io.BytesIO(csv_content)
    csv_file.name = 'flashscore_scrape.csv'

    service = SportEventImportService(csv_file, csv_file.name)
    result = service.execute()
    result['skipped'] = skipped
    return result
