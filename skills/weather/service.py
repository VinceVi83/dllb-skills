import logging
from skills.weather.weather import WeatherHaApi
from common.conf_manager import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

ha_weather = WeatherHaApi()

TEST_CASES = [
    ("What is the weather like right now?", "get_live_current_weather"),
    # ("How will the weather evolve today?", "get_today_12h_forecast"),
    # ("What is the weather forecast for tomorrow?", "get_tomorrow_full_forecast"),
]

def ask_weather_question(request_str: str) -> str:
    """Answer any question about weather, forecast, or temperature."""
    return ha_weather.get_llm_payload(request_str)

def get_live_current_weather() -> str:
    """
    Retrieves the immediate, real-time weather conditions right now (current temperature, wind, humidity, present sky).
    Do NOT use this if the user asks for the general outlook of the day or upcoming hours.
    """
    return ha_weather.get_llm_payload('', force_mode='weather_current')

def get_today_12h_forecast() -> str:
    """
    Retrieves the weather forecast for the rest of today, covering the next 12 hours.
    Use this when the user asks 'what is the weather like today?' or wants the upcoming daylight trend.
    """
    return ha_weather.get_llm_payload('', force_mode='weather_daily')

def get_tomorrow_full_forecast() -> str:
    """
    Retrieves the complete weather forecast for tomorrow (the entire next calendar day).
    Use this when the user explicitly asks about 'tomorrow'.
    """
    return ha_weather.get_llm_payload('', force_mode='weather_tomorrow')


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


if __name__ == "__main__":
    TU_weather()
