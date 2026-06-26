from skills.weather.weather import WeatherHaApi

ha_weather = WeatherHaApi()

def ask_weather_question(request_str: str) -> str:
    """
    Answers a generic or complex free-text question about the weather.
    Use this tool ONLY when the user's request doesn't fit into specific 'current', 'today', or 'tomorrow' queries.
    
    Args:
        request_str: The natural language question or context from the user.
    """
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