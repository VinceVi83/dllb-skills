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


def _synthesize(request_str: str, result: str) -> str:
    """Turn raw tool output into a human answer. Empty result → no LLM call."""
    if result.strip() in ("", "[]", "{}", "None"):
        return "Nothing scheduled."

    system = cfg.agents.agenda_secretary.replace(
        "{{NOW}}", datetime.now().strftime("%A, %d %B %Y %H:%M")
    )
    user = f"# User request\n{request_str}\n\n# Raw data\n{result}"
    return llm.call(system, user, model=cfg.llm_models.creative)

def ask_agenda(request_str: str) -> str:
    """
    Answer any free-text question about the user's agenda: today's events,
    the week, the next concert, reasoning/filtering across several events,
    or anything that doesn't map to a dedicated query.

    Args:
        request_str: The natural language question from the user.
                     (e.g. 'Do I have anything important next Tuesday?')
    """

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

    res = _synthesize(request_str, str(fn(**args)))
    if isinstance(res, dict):
        logger.debug("_synthesize: dict branch -> res['content']")
        return res.get("content", "")
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

if __name__ == "__main__":
    # print(_build_tools_prompt())
    cases = [
        ("today",     "What do I have today?"),
        ("tomorrow",  "And tomorrow, what do I have?"),
        ("in_days",   "What do I have in 3 days?"),
        ("this_week", "Show me this week's events"),
        ("next_week", "And next week?"),
        ("upcoming",  "Is there anything in the next 10 days?"),
        ("next",      "What is my next event?"),
        ("concert",   "What is the next concert?"),
        ("mail",      "Send me the next concert info by mail"),
        ("nomatch",   "Tell me a joke"),
    ]

    for label, req in cases:
        logger.info(f"=== {label} ===> {req}")
        try:
            out = ask_agenda(req)
        except Exception:
            logger.exception("ask_agenda crashed")
            continue
        if out:
            logger.info(out if len(out) < 600 else out[:600] + " ... [truncated]")
