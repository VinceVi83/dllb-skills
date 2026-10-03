import logging
from skills.weather.weather import WeatherHaApi
from common.conf_manager import cfg, setup_logging
from common.llm_client import llm

setup_logging()
logger = logging.getLogger(__name__)

ha_weather = WeatherHaApi()

TEST_CASES = [
    ("What is the weather like right now?", "get_live_current_weather"),
    ("How will the weather evolve today?", "get_today_12h_forecast"),
    ("What is the weather forecast for tomorrow?", "get_tomorrow_forecast"),
]

def TU_weather():
    results = []
    for request_str, expected_tool in TEST_CASES:
        logger.info(f"=== {request_str} (Expected: {expected_tool}) ===")
        try:
            out = ask_weather_question(request_str)
        except Exception:
            logger.exception("ask_weather_question crashed")
            continue
        if out:
            results.append(f"{request_str}: {out if len(out) < 600 else out[:600] + ' ... [truncated]'}")
            logger.info(out if len(out) < 600 else out[:600] + " ... [truncated]")
    return "\n".join(results)

def get_live_current_weather() -> str:
    """Retrieves the immediate, real-time weather conditions right now."""
    report = ha_weather.run_weather_mode("current")
    if cfg.get("debug", False):
        return f"Tool called: get_live_current_weather\n{report}"
    return report

def get_today_12h_forecast() -> str:
    """Retrieves the weather forecast for tomorrow, covering the next 12 hours."""
    report = ha_weather.run_weather_mode("hourly")
    if cfg.get("debug", False):
        return f"Tool called: get_today_12h_forecast\n{report}"
    return report


def get_tomorrow_forecast() -> str:
    """Retrieves the complete weather forecast for tomorrow (the entire next calendar day)."""
    report = ha_weather.run_weather_mode("daily")
    if cfg.get("debug", False):
        return f"Tool called: get_tomorrow_forecast\n{report}"
    return report

def ask_weather_question(request_str: str) -> str:
    """Answer any question about weather, forecast, or temperature."""
    response = llm.call(cfg.agents.select_weather_report, request_str)
    if not response:
        return "Failed to select weather mode"
    mode = response.get('content', '')
    tools_map = {
        "weather_current": get_live_current_weather,
        "weather_daily": get_today_12h_forecast,
        "weather_tomorrow": get_tomorrow_forecast,
    }
    tool_fn = tools_map.get(mode)
    if tool_fn is None:
        return f"Unknown mode: {mode}"
    return tool_fn()

if __name__ == "__main__":
    TU_weather()
