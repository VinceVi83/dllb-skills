import requests
import vobject
import json
from thefuzz import fuzz
from datetime import datetime, timedelta
from pathlib import Path
from common.conf_manager import cfg, setup_logging, Utils
import logging

logger = logging.getLogger(__name__)


class CalendarService:
    """Calendar Service Plugin."""

    def __init__(self):
        self.index_path = Path(cfg.config_dir) / "concert_tickets/concerts.json"
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text())
        else:
            data = {}
            self.index_path.write_text(json.dumps(data))    
        self.calendar_url = cfg.agenda.calendar.LINK_CALENDAR

    def _save(self, data) -> None:
        self.index_path.write_text(json.dumps(data, indent=2))

    @staticmethod
    def _parse_datetime(dt_start):
        if not dt_start:
            return None
        if isinstance(dt_start, datetime):
            return dt_start.replace(tzinfo=None)
        return datetime.combine(dt_start, datetime.min.time())

    def _extract_event_data(self, vevent):
        summary = str(getattr(vevent.summary, "value", "")) if hasattr(vevent, "summary") else ""
        location = str(getattr(vevent.location, "value", "")) if hasattr(vevent, "location") else ""
        dt_start = vevent.dtstart.value if hasattr(vevent, "dtstart") else None

        return {
            "summary": summary or "No Title",
            "location": location or "Unspecified Location",
            "dt": self._parse_datetime(dt_start),
        }

    def _get_calendar_events(self):
        try:
            response = requests.get(self.calendar_url, timeout=10)
            response.raise_for_status()
            calendar = vobject.readOne(response.text)
        except Exception as e:
            logger.error(f"[!] Network error: Unable to fetch calendar: {e}")
            return []

        events = []
        for vevent in getattr(calendar, "vevent_list", []):
            event = self._extract_event_data(vevent)
            if event["dt"]:
                events.append(event)

        return sorted(events, key=lambda x: x["dt"])

    def _events_between(self, start, end, keyword=""):
        keyword = keyword.lower()
        return [
            e
            for e in self._get_calendar_events()
            if start <= e["dt"] <= end
            and (not keyword or keyword in e["summary"].lower())
        ]

    def fetch_calendar_events(self, keyword="", month="", limit=None):
        events = self._events_between(datetime.now(), datetime.max, keyword=keyword)
        if month:
            m = month.zfill(2)
            events = [e for e in events if e["dt"].strftime("%m") == m]
        return events[:limit] if limit else events

    @staticmethod
    def _day_bounds(offset=0):
        day = (datetime.now() + timedelta(days=offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return day, day + timedelta(days=1) - timedelta(microseconds=1)

    @staticmethod
    def _week_bounds(offset=0):
        now = datetime.now()
        start = (now - timedelta(days=now.weekday())) + timedelta(weeks=offset)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=6, hours=23, minutes=59, seconds=59)

    def get_today_events(self):
        return self._events_between(*self._day_bounds(0))

    def get_tomorrow_events(self):
        return self._events_between(*self._day_bounds(1))

    def get_events_in_days(self, offset):
        """Events for a single day at `offset` days from today."""
        return self._events_between(*self._day_bounds(offset))

    def get_week_events(self, offset=0):
        return self._events_between(*self._week_bounds(offset))

    def get_upcoming_events(self, days=7):
        """All events from now until now + `days`."""
        now = datetime.now()
        return self._events_between(now, now + timedelta(days=days))

    def get_next_event(self, keyword=""):
        """Closest upcoming event (optionally filtered by keyword)."""
        events = self._events_between(datetime.now(), datetime.max, keyword=keyword)
        return events[0] if events else None

    def get_next_concert_data(self):
        if not self.index_path.exists():
            return None

        event = self.get_next_event(keyword="Concert")
        if not event:
            return None

        with open(self.index_path, "r", encoding="utf-8") as f:
            index = json.load(f)

        title = event["summary"]
        best_pdf, best_score = None, 0

        for pdf_name, info in index.items():
            artist = info.get("data", {}).get("artist", "")
            if not artist:
                continue
            score = fuzz.token_set_ratio(artist.upper(), title.upper())
            if score > best_score:
                best_score, best_pdf = score, pdf_name

        if best_score < 80:
            return None

        date_str = event["dt"].strftime("%Y/%m/%d")
        return {
            "summary": title,
            "dt": date_str,
            "pdf": best_pdf,
            "raw_key": f"[{date_str}] {title}",
        }

    @staticmethod
    def _format_email_content(summary, date_str, pdf_file):
        subject = f"🎵 Ticket & Info : {summary}"
        body = (
            f"Here are the details for your next concert:\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 EVENT : {summary}\n"
            f"📅 DATE      : {date_str}\n"
            f"📄 TICKET    : {pdf_file}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Enjoy the show!"
        )
        return subject, body

    def mail_me_next_concert(self):
        try:
            next_event = self.get_next_concert_data()
            if not next_event:
                return "Error: No concert found in index."

            subject, body = self._format_email_content(
                next_event["summary"], next_event["dt"], next_event["pdf"]
            )
            attachment = Path(cfg.agenda.DATA_DIR) / "concert_tickets" / next_event["pdf"]

            return {
                "api_name": "send_mail",
                "subject": subject,
                "body": body,
                "attachment": str(attachment) if attachment.exists() else None,
            }
        except Exception as e:
            logger.error(f"Critical Error in Mail Service: {e}")
            return {}


if __name__ == "__main__":
    setup_logging()
    calendar = CalendarService()
    
    print("Today     :", calendar.get_today_events())
    print("Tomorrow  :", calendar.get_tomorrow_events())
    print("In 3 days :", calendar.get_events_in_days(3))
    print("This week :", calendar.get_week_events(0))
    print("Next 7d   :", calendar.get_upcoming_events(days=7))
    print("Next event:", calendar.get_next_event())
    print("Next conc :", calendar.get_next_concert_data())
    print("Mail      :", calendar.mail_me_next_concert())
