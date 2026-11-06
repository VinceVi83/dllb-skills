import json
import logging
import re
import shutil
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
import pdfplumber
import pypdfium2 as pdfium
import pytesseract

from common.llm_client import llm
from common.conf_manager import cfg, Utils

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
TESS_LANG = "fra+eng"

TICKET_FIELDS = ("artist", "venue", "date")
EVENT_FIELDS = ("event_name", "localisation", "date")

_URL_RE = re.compile(r'https?://[^\s"\'<>]+|~?/[^\s"\'<>]+')

FIELD_PROMPTS = {
    "artist": (
        "artist OR event name — the performer, band, festival, or show title. "
        "Examples that are VALID: 'Queen', 'Hellfest', 'Hoshi en concert'. "
        "NOT the buyer, NOT the venue, NOT the seller, NOT the ticket seller."
    ),
    "venue": "physical place with a city — NOT the seller (Fnac, Ticketmaster), NOT the buyer",
    "date": "date of the EVENT — NOT the purchase date, NOT the printing date",
    "event_name": "short title of the appointment — NOT the location, NOT the person",
    "localisation": (
        "place where the event happens. Includes virtual meeting platforms even lowercase: "
        "'sur teams' -> teams, 'via zoom' -> zoom, 'sur meet' -> meet, 'sur discord' -> discord. "
        "Strip the preposition ('sur', 'a', 'via', 'aux'). "
        "NOT a time, NOT a person, NOT the title."
    ),
}

def _ocr_region(doc, page_index: int, img: dict, dpi: int = 300) -> str:
    scale = dpi / 72
    full = doc[page_index].render(scale=scale).to_pil()
    x0 = int(img["x0"] * scale)
    top = int(img["top"] * scale)
    x1 = int(img["x1"] * scale)
    bottom = int(img["bottom"] * scale)
    crop = full.crop((x0, top, x1, bottom))
    return pytesseract.image_to_string(crop, lang=TESS_LANG)

def _extract_text(path: Path) -> str:
    parts = []
    with pdfplumber.open(path) as pdf, pdfium.PdfDocument(str(path)) as pdfium_doc:
        for i, page in enumerate(pdf.pages):
            parts.append(page.extract_text() or "")
            for img in page.images:
                parts.append(_ocr_region(pdfium_doc, i, img))
    return "\n".join(parts)

def _filename_from_url(url: str) -> str:
    name = url.split("?")[0].rstrip("/").split("/")[-1]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name or "ticket.pdf"

_CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://discord.com/",
}

def _resolve_local(payload: str) -> tuple[Path, str]:
    payload = payload.strip()
    if payload.startswith(("http://", "https://")):
        suffix = ".pdf" if payload.split("?")[0].lower().endswith(".pdf") else ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()
        with requests.get(payload, headers=_CDN_HEADERS, stream=True, timeout=30) as resp:
            if resp.status_code in (403, 404, 410):
                raise RuntimeError(
                    f"ticket download failed ({resp.status_code}) — "
                    "Discord link likely expired, re-upload the file"
                )
            resp.raise_for_status()
            with open(tmp.name, "wb") as f:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
        return Path(tmp.name), _filename_from_url(payload)
    path = Path(payload).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"ticket not found: {path}")
    return path, path.name

def _render(template, **values):
    out = template
    for key, value in values.items():
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, indent=2)
        out = out.replace(f"REPLACE_{key.upper()}", value)
    left = re.compile(r"REPLACE_[A-Z_]+").findall(out)
    if left:
        logger.warning(f"unfilled placeholders in prompt: {sorted(set(left))}")
    return out

def _json_loads(raw: str) -> dict:
    if not raw:
        return {}
    raw = re.compile(r"^```(?:json)?|```$", flags=re.MULTILINE).sub("", raw.strip()).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.compile(r"\{.*\}").search(raw)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

def _llm_json(system_prompt: str, user_prompt: str) -> dict:
    res = llm.call(system_prompt, user_prompt, model=cfg.common.llm_gateway.model.mcp, mode="extract")
    out = _json_loads(res.get("content", ""))
    if isinstance(out, list) and len(out) == 1 and isinstance(out[0], dict):
        return out[0]
    if isinstance(out, dict):
        return out
    return {}

def _extract(field: str, text: str, rejected: list) -> list:
    if field == "date":
        rules = (
            "Return the datetime resolved against NOW, format YYYYMMDDThhmmss.\n"
            'Ex: "demain 14h" -> 20261102T140000. No time -> 000000.\n'
            'If no date in text: {"candidates": []}.'
        )
    else:
        rules = (
            "Return the SHORTEST contiguous span, verbatim from the text.\n"
            "NEVER return the whole input text.\n"
            'If not present: {"candidates": []}.'
        )

    system_prompt = _render(
        cfg.agents.agenda_extract,
        field=FIELD_PROMPTS.get(field, field),
        rules=rules,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        rejected=rejected or ["(none)"],
    )
    out = _llm_json(system_prompt, text[:6000])
    logger.debug(f"extract {field!r} rejected={rejected} candidates={out.get('candidates')}")

    text_norm = " ".join(text.lower().split())
    clean = []
    for candidate in out.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        value = (candidate.get("value") or "").strip()
        if not value:
            continue
        if " ".join(value.lower().split()) == text_norm:
            logger.warning(f"extract echoed full input for {field!r}, dropping: {value!r}")
            continue
        clean.append(candidate)
    return clean

def _select(field: str, candidates: list, text: str, forbidden: list[str] | None = None):
    if not candidates:
        return None
    system_prompt = _render(
        cfg.agents.agenda_select,
        field=FIELD_PROMPTS.get(field, field),
        forbidden=forbidden or ["(none)"],
        candidates=candidates,
    )
    out = _llm_json(system_prompt, text[:6000])
    logger.debug(f"select {field!r} raw={out}")
    idx = out.get("selected")
    if not isinstance(idx, int):
        return None
    if idx < 0 or idx >= len(candidates):
        return None
    return candidates[idx]

def _resolve_field(field: str, text: str, forbidden: list[str] | None = None) -> str | None:
    rejected: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        candidates = _extract(field, text, rejected)
        if field == "date" and candidates:
            selected = candidates[0]
        else:
            selected = _select(field, candidates, text, forbidden)
        if not selected:
            continue
        value = (selected.get("value") or "").strip()
        if value and value not in rejected:
            return value
        if value:
            rejected.append(value)
    logger.warning(f"no value for {field!r} after {MAX_ATTEMPTS} attempts")
    return None

def _extract_all(text: str, fields, forbidden: list[str] | None = None) -> dict:
    out = {}
    for field in fields:
        out[field] = _resolve_field(field, text, forbidden)
    return out

def _calendar_json_path() -> Path:
    return Path(cfg.config_dir.parent) / cfg.agenda.calendar.filename

def _tickets_dir() -> Path:
    return _calendar_json_path().parent

def _store_ticket_file(src: Path, filename: str) -> Path:
    dest_dir = _tickets_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest

def _slug(name: str) -> str:
    return re.compile(r"[^A-Za-z0-9_-]+").sub("_", name or "").strip("_") or "event"

def _normalize_date(value) -> str | None:
    if not value:
        return None
    v = str(value).strip()
    if re.compile(r"\d{8}T\d{6}").fullmatch(v):
        return v
    formats = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(v, fmt).strftime("%Y%m%dT%H%M%S")
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(v).strftime("%Y%m%dT%H%M%S")
    except ValueError:
        return None

def _render_ics(name: str, date: str, location: str) -> str:
    template = (Path(cfg.project_dir) / "skills/agenda/template_concert.ics").read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = f"{now}-{_slug(name)}@bot"
    start = datetime.strptime(date, "%Y%m%dT%H%M%S")
    end = start + timedelta(hours=2)
    return (
        template
        .replace("{uid}", uid)
        .replace("{now}", now)
        .replace("{artist}", name or "")
        .replace("{dtstart}", start.strftime("%Y%m%dT%H%M%S"))
        .replace("{dtend}", end.strftime("%Y%m%dT%H%M%S"))
        .replace("{location}", location or "")
    )

def _write_ics(name: str, date: str, location: str = "") -> Path:
    out_path = Path(cfg.config_dir) / f"{_slug(name)}.ics"
    out_path.write_text(_render_ics(name, date, location), encoding="utf-8")
    Utils.send_discord_notification(f'New event created : {name}', channel='notify-tmp' , files=[str(out_path)])
    return out_path

def _append_event_json(key: str, entry: dict) -> None:
    path = _calendar_json_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {}
    data[key] = entry
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

def _event_title(artist: str, date: str | None) -> str | None:
    if not artist or not date or len(date) < 8:
        return None
    return f"[{date[0:4]}/{date[4:6]}/{date[6:8]}] CONCERT: {artist}"

def create_spectacle_from_ticket(payload: str) -> dict:
    if not isinstance(payload, str):
        raise TypeError(f"payload must be str, got {type(payload).__name__}")

    match = _URL_RE.search(payload)
    if not match:
        raise ValueError(f"no ticket source in: {payload!r}")
    source = match.group(0).rstrip('.,;:)]}')
    logger.info("create_spectacle_from_ticket")
    path, name = _resolve_local(source)
    text = _extract_text(path)
    stored = _store_ticket_file(path, name)
    logger.info(f"ticket stored: {stored}")
    ticket = _extract_all(text, TICKET_FIELDS, cfg.agenda.forbidden_info)
    artist = ticket.get("artist")
    venue = ticket.get("venue") or "Unknown venue"
    date = _normalize_date(ticket.get("date"))
    event_title = _event_title(artist, date)
    if event_title:
        _write_ics(artist, date, venue)

    entry = {
        "status": "ics_pending",
        "data": {
            "artist": artist or "Unknown Artist",
            "venue": venue,
            "date": date or "",
        },
        "event": event_title,
    }
    _append_event_json(name, entry)
    payload = {"pdf_name": name, "entry": entry, "ticket": ticket}
    logger.info(f"ticket entry added to calendar.json: {payload}")
    return f"Done {payload}"

def create_event_ics(name: str, date: str, location: str = "", description: str = "") -> dict:
    path = _write_ics(name, date, location)
    return {"ics": path.name, "name": name, "date": date, "location": location or ""}

def _make_description(fields: dict, fallback: str) -> str:
    parts = []
    for key in ("event_name", "date", "localisation"):
        value = fields.get(key)
        if value:
            parts.append(value)
    seed = " - ".join(parts)
    if not seed:
        return fallback
    try:
        res = llm.call(
            "Summarize this appointment in one short line, in English. "
            "No quotes, no preamble, no trailing punctuation. Reply with the summary only.",
            seed,
            model=cfg.common.llm_gateway.model.mcp,
            mode="extract",
        )
        if isinstance(res, dict):
            content = res.get("content", "").strip()
        else:
            content = str(res).strip()
        if content:
            return content
    except Exception:
        pass
    return fallback

def create_event_from_text(user_prompt: str) -> dict:
    fields = _extract_all(user_prompt, EVENT_FIELDS, ["none"])
    if not fields.get("event_name"):
        logger.info("event_name missing")
        return "Failed: event_name missing"

    date = _normalize_date(fields.get("date"))
    if not date:
        logger.info("date missing or invalid")
        return "Failed: date missing or invalid"

    result = create_event_ics(
        name=fields["event_name"],
        date=date,
        location=fields.get("localisation"),
    )
    result["description"] = _make_description(fields, user_prompt)
    return "Done"

def handle_ticket(user_prompt: str) -> dict:
    logger.info(f"handle_ticket: {user_prompt[:80]}")
    if _URL_RE.search(user_prompt):
        return create_spectacle_from_ticket(user_prompt)
    return create_event_from_text(user_prompt)

if __name__ == "__main__":
    logger.info("=== create_event_ics ===")
    logger.info(create_event_ics(
        name="Dentist",
        date="20261105T140000",
        location="12 rue de la Paix, Paris",
    ))

    logger.info("=== create_event_from_text ===")
    logger.info(create_event_from_text("Rappel: RDV dentiste demain 14h sur teams"))

    logger.info("=== create_spectacle_from_ticket ===")
    logger.info(create_spectacle_from_ticket("~/test2.pdf"))
