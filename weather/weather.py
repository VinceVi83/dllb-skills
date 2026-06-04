import json
import os
import requests
from dataclasses import dataclass, is_dataclass, fields
from tools.ollama_config import OllamaConfig
from tools.ollama_service import llm
from typing import List, Dict, Any, Optional
from datetime import datetime
from config_loader import cfg
from PIL import Image, ImageDraw, ImageFont
import logging
logger = logging.getLogger(__name__)


@dataclass
class WeatherHour:
    timestamp: str
    condition: str
    temperature: float
    precipitation: float


@dataclass
class WeatherDay:
    timestamp: datetime
    condition: str
    temperature: float
    precipitation_probability: Optional[int]


@dataclass
class WeatherStatus:
    status: str
    temperature: float
    last_update: str


def format_for_llm(data: Any) -> str:
    if is_dataclass(data):
        items = [data]
    elif isinstance(data, list) and len(data) > 0 and is_dataclass(data[0]):
        items = data
    else:
        return "Error: Provided data must be a dataclass or a list of dataclasses."

    stats_summary = []
    for f in fields(items[0]):
        if f.type in (int, float):
            try:
                values = [float(getattr(item, f.name)) for item in items]
                if values:
                    stats_summary.append(f"- {f.name} (Min: {min(values)} / Max: {max(values)})")
            except (ValueError, TypeError):
                pass

    clean_items = []
    for item in items:
        clean_item = {}
        for f in fields(item):
            val = getattr(item, f.name)
            if isinstance(val, datetime):
                time_str = val.astimezone().strftime("%H:%M")
                clean_item[f.name] = time_str
            elif isinstance(val, str) and ("T" in val or "+" in val):
                try:
                    dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
                    clean_item[f.name] = dt.astimezone().strftime("%H:%M")
                except:
                    clean_item[f.name] = val
            else:
                clean_item[f.name] = val
        clean_items.append(clean_item)

    output = "CALCULATED VALUES :\n"
    output += "\n".join(stats_summary) if stats_summary else "No numerical values"
    output += "\n\nDATA (JSON) :\n"
    output += json.dumps(clean_items, ensure_ascii=False)
    
    return output


def print_table(data: Any):
    if is_dataclass(data):
        items = [data]
    elif isinstance(data, list) and len(data) > 0 and is_dataclass(data[0]):
        items = data
    else:
        print("Error: Provided data must be a dataclass or a list of dataclasses.")
        return

    headers = [f.name.upper() for f in fields(items[0])]
    
    rows = []
    for item in items:
        row = []
        for f in fields(item):
            val = getattr(item, f.name)
            if isinstance(val, datetime):
                row.append(val.strftime("%Y-%m-%d %H:%M"))
            else:
                row.append(str(val))
        rows.append(row)

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    border = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    
    print(border)
    header_line = "|" + "|".join(f" {headers[i]:<{col_widths[i]}} " for i in range(len(headers))) + "|"
    print(header_line)
    print(border)
    
    for row in rows:
        row_line = "|" + "|".join(f" {row[i]:<{col_widths[i]}} " for i in range(len(row))) + "|"
        print(row_line)
        
    print(border)


class WeatherHaApi:
    """Home Assistant Weather API Client
    
    Role: Fetches and formats weather data from Home Assistant and generates weather cards.
    
    Methods:
        __init__(self) : Initialize the WeatherHaApi instance with Home Assistant credentials.
        base_url_services(self) : Get the base URL for weather service endpoints.
        _fetch_forecast(self, forecast_type) : Fetch forecast data from Home Assistant.
        fetch_current_status(self) : Get current weather status from Home Assistant.
        fetch_hourly_forecast(self, limit) : Get hourly weather forecast from Home Assistant.
        fetch_daily_forecast(self, offset) : Get daily weather forecast from Home Assistant.
        get_llm_payload(self, request, force_mode) : Generate LLM payload for weather reports.
        generate_weather_card(self, weather_data, output_path, card_type) : Generate weather card image.
    """

    def __init__(self):
        self.host = f"http://{cfg.home_assistant.ha_hostname}:8123/api"
        self.token = cfg.home_assistant.ha_token
        self.city = cfg.home_assistant.ha_weather_location
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def base_url_services(self):
        return f"{self.host}/services/weather/get_forecasts"

    def _fetch_forecast(self, forecast_type):
        url = f"{self.base_url_services()}?return_response"
        payload = {"entity_id": self.city, "type": forecast_type}
        
        r = requests.post(url, json=payload, headers=self.headers)
        r.raise_for_status()
        raw_list = r.json()["service_response"][self.city]["forecast"]
        
        return raw_list

    def fetch_current_status(self) -> WeatherStatus:
        r = requests.get(f"{self.host}/states/{self.city}", headers=self.headers)
        r.raise_for_status()
        data = r.json()
        attr = data['attributes']
        
        return WeatherStatus(
            status=data['state'],
            temperature=attr.get('temperature'),
            last_update=datetime.fromisoformat(data['last_updated'].replace('Z', '+00:00'))
        )

    def fetch_hourly_forecast(self, limit: Optional[int] = None) -> List[WeatherHour]:
        try:
            raw_list = self._fetch_forecast("hourly")
        except Exception as e:
            logger.error(f"Error fetching hourly forecast: {e}")
            return []
        
        if limit is not None:
            raw_list = raw_list[:limit]
        
        hourly_list = []
        for h in raw_list:
            try:
                dt_str = h.get('datetime', '')
                if dt_str.endswith('Z'):
                    dt_str = dt_str.replace('Z', '+00:00')
                timestamp = datetime.fromisoformat(dt_str) if dt_str else datetime.now()

                hourly_list.append(WeatherHour(
                    timestamp=timestamp,
                    condition=h.get('condition', 'unknown'),
                    temperature=float(h['temperature']) if h.get('temperature') is not None else 0.0,
                    precipitation=float(h['precipitation']) if h.get('precipitation') is not None else 0.0
                ))
            except Exception as e:
                logger.error(f"Error processing hourly weather: {e}")
                continue
        
        return hourly_list

    def fetch_daily_forecast(self, offset=0) -> List[WeatherDay]:
        raw_list = self._fetch_forecast("daily")
        
        daily_list = []
        for j in raw_list:
            daily_list.append(WeatherDay(
                timestamp=datetime.fromisoformat(j['datetime'].replace('Z', '+00:00')),
                condition=j['condition'],
                temperature=j.get('temperature'),
                precipitation_probability=j.get('precipitation_probability', 0.0)
            ))
        
        return daily_list[offset]

    def get_llm_payload(self, request: str, force_mode=None) -> Dict[str, Any]:
        conf = OllamaConfig()
        # res = llm.generate(conf).get('content', "")
        mode = 'osef'

        if not force_mode:
            conf.model = 'qwen2.5:3b'
            conf.set_system(cfg.agents.select_weather_report)
            conf.set_content(request)
            mode = llm.generate(conf).get('content', None)
            print(f'AAA  {request}  {mode}')
            if not mode:
                logger.error('Failed')
                return

        conf.model = 'qwen2.5:7b'
        conf.set_system(cfg.agents.weather_daily_report)
        if "weather_current" in [force_mode, mode]:
            result = self.fetch_current_status()
            self.generate_weather_card(result, "weather_current.png", "current")
            conf.user_content = format_for_llm(result)
            print(conf.user_content)
            res = llm.generate(conf).get('content', None)
            return f'weather_current: {res} \nTemperature: {result.temperature}'
        elif "weather_daily" in [force_mode, mode]:
            result = self.fetch_hourly_forecast(10)
            self.generate_weather_card(result, "weather_hourly.png", "hourly")
            conf.user_content = format_for_llm(result)
            print(conf.user_content)
            res = llm.generate(conf).get('content', None)
            return f'weather_daily: {res} \nTemperature: {result[4].temperature}'
        elif "weather_tomorrow" in [force_mode, mode]:
            result = self.fetch_daily_forecast(1)
            self.generate_weather_card(result, "weather_daily.png", "daily")
            conf.user_content = format_for_llm(result)
            print(conf.user_content)
            res = llm.generate(conf).get('content', None)
            print(f'weather_tomorrow\n')
            return f'weather_tomorrow: {res} \nTemperature: {result.temperature}'
        else:
            return 'Failed'

    def generate_weather_card(self, weather_data: Any, output_path: str = "weather_output.png", card_type: str = "hourly") -> str:
        if os.path.exists(output_path):
            os.remove(output_path)

        ICONS_FOLDER = os.path.join(os.path.dirname(__file__), "weather_icons")
        CONDITION_MAPPING = {
            "partlycloudy": {"text": "Cloudy", "file": "partlycloudy.png"},
            "lightning-rainy": {"text": "Stormy", "file": "lightning.png"},
            "lightning": {"text": "Stormy", "file": "lightning.png"},
            "sunny": {"text": "Sunny", "file": "sunny.png"},
            "rainy": {"text": "Rainy", "file": "rainy.png"},
            "clear-night": {"text": "Clear night", "file": "clear-night.png"}
        }

        if not os.path.exists(ICONS_FOLDER):
            logger.warning(f"Missing folder: {ICONS_FOLDER}, using fallback icons")

        CARD_WIDTH = 550
        CARD_HEIGHT = 210 if card_type == "hourly" else 300 if card_type == "daily" else 350
        BACKGROUND_COLOR = (28, 28, 30)
        TEXT_WHITE = (227, 227, 227)
        TEXT_GRAY = (142, 142, 147)
        
        img = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(img)

        def get_linux_font(font_name, size):
            possible_paths = [
                f"/usr/share/fonts/truetype/dejavu/{font_name}.ttf",
                f"/usr/share/fonts/truetype/ubuntu/{font_name}.ttf",
                f"/usr/share/fonts/truetype/liberation/{font_name}.ttf",
                f"{font_name}.ttf"
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    try:
                        return ImageFont.truetype(path, size)
                    except IOError:
                        continue
            return ImageFont.load_default()

        font_title = get_linux_font("DejaVuSans", 18)
        font_state = get_linux_font("DejaVuSans", 32)
        font_location = get_linux_font("DejaVuSans", 16)
        font_main_temp = get_linux_font("DejaVuSans", 40)
        font_info = get_linux_font("DejaVuSans", 14)

        def paste_png_icon(base_img, condition, x, y, size_px):
            cond_info = CONDITION_MAPPING.get(condition, {"text": "Weather", "file": "partlycloudy.png"})
            icon_path = os.path.join(ICONS_FOLDER, cond_info["file"])
            
            if not os.path.exists(icon_path):
                # Create a simple colored square as fallback when icon is missing
                if condition == "sunny":
                    fill_color = (255, 215, 0)
                elif condition == "clear-night":
                    fill_color = (240, 230, 140)
                elif condition == "rainy":
                    fill_color = (33, 150, 243)
                elif condition == "lightning-rainy":
                    fill_color = (100, 100, 200)
                else:
                    fill_color = (227, 227, 227)
                
                icon = Image.new("RGBA", (size_px, size_px), fill_color + (255,))
                base_img.paste(icon, (int(x), int(y)))
                return
            
            try:
                icon = Image.open(icon_path).convert("RGBA")
                icon = icon.resize((int(size_px), int(size_px)), Image.Resampling.LANCZOS)
                base_img.paste(icon, (int(x), int(y)), mask=icon.getchannel('A'))
            except Exception as e:
                logger.error(f"Error processing icon {icon_path}: {e}")

        if card_type == "hourly":
            forecast_data = []
            for h in weather_data:
                forecast_data.append({
                    "timestamp": h.timestamp.strftime("%H:%M") if isinstance(h.timestamp, datetime) else h.timestamp,
                    "condition": h.condition,
                    "temperature": h.temperature
                })

            draw.text((20, 16), "Weather", font=font_title, fill=TEXT_WHITE)
            current = forecast_data[0]
            draw.text((85, 48), CONDITION_MAPPING.get(current["condition"], {"text": "Cloudy"})["text"], font=font_state, fill=TEXT_WHITE)
            draw.text((85, 82), "Boulogne-Billancourt", font=font_location, fill=TEXT_GRAY)

            paste_png_icon(img, current["condition"], 20, 48, 50)
            temp_str = f"{round(current['temperature'])}°C"
            text_length = draw.textlength(temp_str, font=font_main_temp)
            draw.text((CARD_WIDTH - 20 - text_length, 48), temp_str, font=font_main_temp, fill=TEXT_WHITE)

            col_width = (CARD_WIDTH - 40) / len(forecast_data)
            for i, f in enumerate(forecast_data):
                x = 20 + i * col_width + col_width / 2
                timestamp_text = f["timestamp"]
                timestamp_length = draw.textlength(timestamp_text, font=font_location)
                draw.text((x - timestamp_length / 2, 130), timestamp_text, font=font_location, fill=TEXT_WHITE)
                paste_png_icon(img, f["condition"], int(x - 18), 145, 36)
                temp_display = f"{round(f['temperature'])}°"
                temp_display_length = draw.textlength(temp_display, font=font_location)
                draw.text((x - temp_display_length / 2, 176), temp_display, font=font_location, fill=TEXT_WHITE)
        
        elif card_type == "current":
            status = weather_data.status
            draw.text((20, 20), "Current Weather", font=font_title, fill=TEXT_WHITE)
            paste_png_icon(img, status, CARD_WIDTH // 2 - 75, 60, 150)
            cond_text = CONDITION_MAPPING.get(status, {"text": "Unknown"})["text"]
            cond_text_length = draw.textlength(cond_text, font=font_state)
            draw.text((CARD_WIDTH // 2 - cond_text_length // 2, 230), cond_text, font=font_state, fill=TEXT_WHITE)
            temp_str = f"{round(weather_data.temperature)}°C"
            temp_str_length = draw.textlength(temp_str, font=font_main_temp)
            draw.text((CARD_WIDTH // 2 - temp_str_length // 2, 270), temp_str, font=font_main_temp, fill=TEXT_WHITE)
            draw.text((20, 320), f"Last update: {weather_data.last_update}", font=font_info, fill=TEXT_GRAY)
        
        else:
            forecast = weather_data
            date_str = forecast.timestamp.strftime("%A %d %B %Y")
            draw.text((20, 20), f"Forecast for {date_str}", font=font_title, fill=TEXT_WHITE)
            paste_png_icon(img, forecast.condition, CARD_WIDTH // 2 - 60, 60, 120)
            cond_text = CONDITION_MAPPING.get(forecast.condition, {"text": "Unknown"})["text"]
            cond_text_length = draw.textlength(cond_text, font=font_state)
            draw.text((CARD_WIDTH // 2 - cond_text_length // 2, 190), cond_text, font=font_state, fill=TEXT_WHITE)
            temp_str = f"{round(forecast.temperature)}°C"
            temp_str_length = draw.textlength(temp_str, font=font_main_temp)
            draw.text((CARD_WIDTH // 2 - temp_str_length // 2, 230), temp_str, font=font_main_temp, fill=TEXT_WHITE)
            precip_str = f"Rain: {forecast.precipitation_probability}%"
            precip_str_length = draw.textlength(precip_str, font=font_info)
            draw.text((CARD_WIDTH // 2 - precip_str_length // 2, 270), precip_str, font=font_info, fill=TEXT_GRAY)
        
        img.save(output_path, "PNG")
        logger.info(f"Weather card generated: {output_path}")
        
        return output_path


if __name__ == "__main__":
    try:
        ha_weather = WeatherHaApi()
        
        # print("Testing hourly weather card...")
        # hourly_data = ha_weather.fetch_hourly_forecast(8)
        # if hourly_data:
        #     card_path = ha_weather.generate_weather_card(hourly_data, "weather_hourly.png", "hourly")
        #     print(f"Hourly weather card generated at: {card_path}")
        
        # print("Testing current weather card...")
        # current_data = ha_weather.fetch_current_status()
        # if current_data:
        #     card_path = ha_weather.generate_weather_card(current_data, "weather_current.png", "current")
        #     print(f"Current weather card generated at: {card_path}")
        
        # print("Testing daily weather card...")
        # daily_data = ha_weather.fetch_daily_forecast(1)
        # if daily_data:
        #     card_path = ha_weather.generate_weather_card(daily_data, "weather_daily.png", "daily")
        #     print(f"Daily weather card generated at: {card_path}")
        
        ha_weather.get_llm_payload('Quelle est la météo')
        ha_weather.get_llm_payload("il fera quel temp aujourd'hui")
        ha_weather.get_llm_payload("c'est quoi la méteo demain ?")
        ha_weather.get_llm_payload('', force_mode='weather_current')
        ha_weather.get_llm_payload('', force_mode='weather_daily')
        ha_weather.get_llm_payload('', force_mode='weather_tomorrow')
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
