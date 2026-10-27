import re
import sys
import json
import http.cookiejar
from datetime import date

import requests

GRAPHQL_URL = "https://www.livechart.me/graphql"
PAGE_URL    = "https://www.livechart.me/fall-2026/tv"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:157.0) Gecko/20100101 Firefox/157.0"

_CSRF_RE = re.compile(r'<meta\s+name="csrf-token"\s+content="([^"]+)"')

_UPSERT = """
mutation UpsertLibraryEntry($animeId: ID!, $attributes: LibraryEntryAttributes!) {
  upsertLibraryEntry(animeId: $animeId, attributes: $attributes) {
    libraryEntry { animeDatabaseId episodesWatched status rating rewatches startedAt finishedAt notes }
    problems { message path }
  }
}
"""


# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------

def load_cookies(session_file):
    """Charge un cookies.txt (format Netscape) et retourne un dict {name: value}."""
    jar = http.cookiejar.MozillaCookieJar(session_file)
    jar.load(ignore_discard=True, ignore_expires=True)
    return {c.name: c.value for c in jar}


def check_session_cookie(cookies, key=None):
    """
    Vérifie qu'un cookie de session est présent et non expiré.
    - Si key est fourni : vérifie ce cookie précis.
    - Sinon : cherche n'importe quel cookie qui ressemble à une session
      ('session' ou 'remember_user_token' dans le nom).
    Retourne (ok: bool, message: str).
    """
    if not cookies:
        return False, "aucun cookie chargé"

    if key is not None:
        if key not in cookies:
            return False, f"cookie '{key}' absent"
        return True, f"cookie '{key}' présent"

    candidates = [
        name for name in cookies
        if "session" in name.lower() or "remember_user_token" in name.lower()
    ]
    if not candidates:
        return False, "aucun cookie de session trouvé"
    return True, f"cookies de session trouvés : {', '.join(candidates)}"


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

def _fetch_csrf(session, cookies):
    """Récupère un CSRF token frais depuis une page publique."""
    r = session.get(
        PAGE_URL,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.5",
        },
        cookies=cookies,
        timeout=15,
    )
    r.raise_for_status()
    m = _CSRF_RE.search(r.text)
    if not m:
        raise RuntimeError("CSRF token introuvable dans la page")
    return m.group(1)


# ---------------------------------------------------------------------------
# Update épisode
# ---------------------------------------------------------------------------

def mark_episode_watched(anime_id, episodes_watched, session_file):
    """
    Marque `episodes_watched` épisodes vus pour `anime_id` sur LiveChart.

    - anime_id         : ID LiveChart (int ou str)
    - episodes_watched : nombre total d'épisodes vus (int ou str)
    - session_file     : chemin vers cookies.txt

    N'envoie QUE les clés modifiées (status + episodesWatched, + startedAt au 1er épisode).
    Ne touche pas aux notes / rating / rewatches / finishedAt existants.
    """
    episodes_watched = int(episodes_watched)

    cookies = load_cookies(session_file)
    ok, msg = check_session_cookie(cookies)
    if not ok:
        raise RuntimeError(f"session invalide : {msg}")

    session = requests.Session()
    csrf = _fetch_csrf(session, cookies)

    attributes = {
        "status": "WATCHING",
        "episodesWatched": episodes_watched,
    }
    # date de début : uniquement au tout premier épisode
    if episodes_watched == 1:
        attributes["startedAt"] = date.today().isoformat()

    payload = {
        "operationName": "UpsertLibraryEntry",
        "query": _UPSERT,
        "variables": {
            "animeId": str(anime_id),
            "attributes": attributes,
        },
    }

    r = session.post(
        GRAPHQL_URL,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "Origin": "https://www.livechart.me",
            "Referer": PAGE_URL,
            "X-CSRF-Token": csrf,
        },
        cookies=cookies,
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()

    if "errors" in data:
        raise RuntimeError(f"GraphQL errors : {data['errors']}")

    result = data.get("data", {}).get("upsertLibraryEntry", {})
    problems = result.get("problems") or []
    if problems:
        raise RuntimeError(f"problems : {problems}")

    return result.get("libraryEntry")