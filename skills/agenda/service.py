import inspect
import json
import logging

from skills.agenda.calendar import CalendarService
from common.conf_manager import cfg, setup_logging
from common.llm_client import llm
from datetime import datetime

setup_logging()
logger = logging.getLogger(__name__)

calendar = CalendarService()

def _build_tools_prompt() -> str:
    """List public functions with their signature and docstring."""
    tools = []
    for name, fn in globals().items():
        if not inspect.isfunction(fn):
            continue
        if fn.__module__ != __name__:
            continue
        if name.startswith(("ask", "_")):
            continue

        sig = inspect.signature(fn)
        tools.append({
            "name": name,
            "signature": str(sig),
            "parameters": {
                p.name: {
                    "type": (
                        str(p.annotation)
                        if p.annotation is not inspect.Parameter.empty
                        else "str"
                    ),
                    "default": (
                        p.default
                        if p.default is not inspect.Parameter.empty
                        else None
                    ),
                }
                for p in sig.parameters.values()
            },
            "description": inspect.getdoc(fn) or "",
        })

    return cfg.agents.agenda_router.replace(
        "{{TOOLS}}",
        json.dumps(tools, indent=2, ensure_ascii=False, default=str),
    )

    tools_prompt = json.dumps(tools, indent=2, ensure_ascii=False, default=str)
    return f"{context}\n\nAvailable tools:\n{tools_prompt}"


def ask_agenda(request_str: str) -> str:
    """Answer any question about the user's agenda, events, calendar, or concerts."""

    local_res = llm.call(_build_tools_prompt(), request_str, model=cfg.llm_models.mcp)
    decision = json.loads(local_res['content'])

    tool_name = decision.get("tool")
    if not tool_name:
        return f"No Tool : {decision.get('reason', '')}"

    fn = globals().get(tool_name)
    if not (fn and inspect.isfunction(fn) and fn.__module__ == __name__):
        return f"Unknown Tool : {tool_name}"

    sig = inspect.signature(fn)
    args = {
        k: int(v) if sig.parameters[k].annotation is int else v
        for k, v in (decision.get("arguments") or {}).items()
        if k in sig.parameters
    }

    res = str(fn(**args))
    
    if True:
        logger.info(f"Tool called: {tool_name}\n{res if len(res) < 600 else res[:600] + ' ... [truncated]'}")
        return f"Tool called: {tool_name}\n{res}"
    return res


def get_calendar_events_today() -> list[dict]:
    """Get all calendar events happening today (right now)."""
    logger.info('')
    return calendar.get_today_events()

def get_calendar_events_tomorrow() -> list[dict]:
    """Get all calendar events happening tomorrow."""
    logger.info('')
    return calendar.get_tomorrow_events()

def get_calendar_events_in_days(offset: int) -> list[dict]:
    """
    Get all calendar events happening exactly N days from today.

    Args:
        offset: Days from today (0 = today, 1 = tomorrow, 3 = in three days).
    """
    logger.info(f"offset : {offset}")
    return calendar.get_events_in_days(offset)

def get_calendar_events_this_week() -> list[dict]:
    """Get all calendar events for the current week (Monday → Sunday)."""
    logger.info('')
    return calendar.get_week_events(0)

def get_calendar_events_next_week() -> list[dict]:
    """Get all calendar events for next week (Monday → Sunday)."""
    logger.info('')
    return calendar.get_week_events(1)

def get_calendar_events_upcoming(days: int = 7) -> list[dict]:
    """
    Get all calendar events from now until N days ahead.
    Use for 'what's coming up?' or 'anything in the next 10 days?'.

    Args:
        days: Horizon in days from now (default: 7).
    """
    logger.info(f"Up to {days} days")
    return calendar.get_upcoming_events(days=days)

def get_next_calendar_event() -> dict | None:
    """Get the single next upcoming event in the calendar (any kind)."""
    logger.info(f"")
    return calendar.get_next_event()

def get_next_concert() -> dict | None:
    """Get the next upcoming concert, with its ticket PDF info if available."""
    logger.info('')
    return calendar.get_next_concert_data()

def mail_me_next_concert() -> dict:
    """
    Send an email to the user containing the next concert's details and its
    ticket PDF attached. Only use when the user explicitly asks for it by mail.
    """
    logger.info('')
    return calendar.mail_me_next_concert()

TEST_CASES = [
    # ("What is my agenda for today?", "get_calendar_events_today"),
    # ("What is my agenda for tomorrow?", "get_calendar_events_tomorrow"),
    ("What is my agenda in 3 days?", "get_calendar_events_in_days"),
    # ("What is my agenda for this week?", "get_calendar_events_this_week"),
    # ("What is my agenda for next week?", "get_calendar_events_next_week"),
    # ("Is there anything in the next 10 days?", "get_calendar_events_upcoming"),
    ("What is my next event?", "get_next_calendar_event"),
    ("What is my next concert?", "get_next_concert"),
    # ("Mail me my next concert info", "mail_me_next_concert"),
    ("Tell me a joke", None),
]


def TU_agenda():
    results = []
    for label, req in TEST_CASES:
        logger.info(f"=== {label} ===> {req}")
        try:
            out = ask_agenda(req)
        except Exception:
            logger.exception("ask_agenda crashed")
            continue
        if out:
            results.append(f"{label}: {out if len(out) < 600 else out[:600] + ' ... [truncated]'}")
            logger.info(out if len(out) < 600 else out[:600] + " ... [truncated]")
    return "\n".join(results)


if __name__ == "__main__":
    TU_agenda()
