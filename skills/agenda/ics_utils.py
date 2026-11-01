import logging
from datetime import datetime, timedelta
from pathlib import Path

from common.conf_manager import cfg

logger = logging.getLogger(__name__)

DATE_FMT = "%Y%m%dT%H%M%S"


def generate_ics_from_template(
    output_path,
    summary: str,
    dtstart: str,
    location: str = "",
    duration_hours: int = 3,
) -> Path:
    """
    Fill the .ics template and write it.

    Args:
        output_path:    destination .ics path.
        summary:        event title (injected as {artist} in the template).
        dtstart:        start datetime, STRICT format %Y%m%dT%H%M%S.
        location:       optional location.
        duration_hours: duration used to compute DTEND (default 3h).

    Returns:
        The written path.
    """
    with open(cfg.agenda.ics_template, "r", encoding="utf-8") as f:
        content = f.read()

    now = datetime.now().strftime(DATE_FMT)
    uid = f"{now}-{summary.replace(' ', '_')}@bot"

    try:
        start_dt = datetime.strptime(dtstart, DATE_FMT)
        dtend = (start_dt + timedelta(hours=duration_hours)).strftime(DATE_FMT)
    except ValueError:
        logger.warning(f"Invalid dtstart {dtstart!r}, DTEND = DTSTART")
        dtend = dtstart

    formatted = content.format(
        uid=uid,
        now=now,
        artist=summary,
        dtstart=dtstart,
        dtend=dtend,
        location=location,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(formatted)
    logger.info(f"ICS written: {output_path}")
    return output_path
