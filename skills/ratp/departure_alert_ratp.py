import requests
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List
import re
from common.conf_manager import cfg, setup_logging, Utils

import logging
logger = logging.getLogger(__name__)

API_TOKEN = cfg.ratp.token

@dataclass
class JourneySection:
    type: str
    duration: int
    mode: str = ""
    line: str = ""

@dataclass
class Journey:
    duration: int
    sections: List[JourneySection]

@dataclass
class ItineraryResult:
    journeys: List[Journey]


def _get_stop_monitoring_url(stop_ref: str) -> str:
    url = "https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring"
    headers = {"Accept": "application/json", "apikey": API_TOKEN}
    return url, headers


def _fetch_stop_monitoring_data(stop_ref: str) -> list:
    url, headers = _get_stop_monitoring_url(stop_ref)
    params = {"MonitoringRef": stop_ref}

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return []
        data = response.json()
        deliveries = data.get("Siri", {}).get("ServiceDelivery", {}).get("StopMonitoringDelivery", [])
        all_visits = []
        for delivery in deliveries:
            all_visits.extend(delivery.get("MonitoredStopVisit", []))
        return all_visits
    except Exception:
        return []


@dataclass
class Line:
    """RATP Line Information

    Role: Represents a transit line with route details.

    Methods:
        __init__(self, name, direction, stop, id_name, walk) : Initialize line with route data.
    """
    name: str
    direction: str
    stop: str
    id_name: str
    walk: int


class Trip:
    """RATP Departure Alert Service
    
    Role: Manages departure alerts and schedule display for transit lines.
    
    Methods:
        __init__(self, outbound_lines, return_lines) : Initialize with line lists.
        _get_stop_monitoring(self, line) : Fetch stop monitoring data from API.
        _format_schedule(self, line) : Format schedule for a specific line.
        _display_all(self, reverse) : Display all lines (outbound or return).
    """

    def __init__(self, outbound_lines: List[Line], return_lines: List[Line]):
        self.outbound_lines = outbound_lines
        self.return_lines = return_lines

    def _get_stop_monitoring(self, line: Line) -> list:
        stop_ref = f"STIF:StopPoint:Q:{line.stop}:"
        return _fetch_stop_monitoring_data(stop_ref)

    def _get_line_ref(self, line: Line) -> str:
        return f"STIF:Line::{line.id_name}:"

    def _get_current_time(self) -> datetime:
        return datetime.now(timezone.utc)

    def _parse_time_to_minutes(self, time_str: str, line: Line) -> int:
        bus_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        minutes = int((bus_time - self._get_current_time()).total_seconds() // 60)
        return minutes - line.walk

    def _get_display_time(self, minutes: int) -> str:
        if minutes is not None and minutes <= 0:
            return "Approaching!"
        if minutes is not None:
            return f"{minutes} min"
        return "Passed/Soon"

    def _get_destination_name(self, journey: dict) -> str:
        dest = journey.get("DestinationName", [{}])[0].get("value", "Unknown")
        return dest

    def _get_bus_time(self, passage: dict) -> datetime:
        journey = passage.get("MonitoredVehicleJourney", {})
        call = journey.get("MonitoredCall", {})
        time_str = call.get("ExpectedDepartureTime") or call.get("ExpectedArrivalTime")
        if time_str:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return None

    def _get_fallback_time(self, passage: dict) -> datetime:
        journey = passage.get("MonitoredVehicleJourney", {})
        call = journey.get("MonitoredCall", {})
        time_str = call.get("ExpectedDepartureTime", "2000-01-01T00:00:00Z")
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))

    def _filter_relevant_passages(self, passages: list, line_ref: str) -> list:
        filtered_all = [
            p for p in passages 
            if p.get("MonitoredVehicleJourney", {}).get("LineRef", {}).get("value") == line_ref
        ]
        return filtered_all

    def _get_relevant_passages(self, passages: list, line_ref: str, line: Line) -> list:
        filtered_all = self._filter_relevant_passages(passages, line_ref)
        relevant_passages = []
        for p in filtered_all:
            journey = p.get("MonitoredVehicleJourney", {})
            call = journey.get("MonitoredCall", {})
            time_str = call.get("ExpectedDepartureTime") or call.get("ExpectedArrivalTime")
            if time_str:
                bus_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                minutes = self._parse_time_to_minutes(time_str, line)
                if minutes >= 0:
                    relevant_passages.append((p, minutes, bus_time))
        return relevant_passages

    def _get_fallback_passages(self, filtered_all: list) -> list:
        fallback_list = [
            (p, None, self._get_fallback_time(p)) 
            for p in filtered_all[:3]
        ]
        return fallback_list

    def _build_display_list(self, relevant_passages: list, filtered_all: list) -> list:
        display_list = relevant_passages if relevant_passages else self._get_fallback_passages(filtered_all)
        return display_list

    def _format_schedule_output(self, display_list: list, line: Line) -> str:
        output = f"\n=== SCHEDULE - LINE {line.name} - Destination : {line.direction} ===\n"
        header_added = False
        for p, minutes, bus_time in display_list:
            journey = p.get("MonitoredVehicleJourney", {})
            dest = self._get_destination_name(journey)
            display_time = self._get_display_time(minutes)
            if not header_added:
                output += f"➔ {dest}\n"
                header_added = True
            output += f"    └─ {bus_time.astimezone().strftime('%H:%M')} ({display_time})\n"
        return output

    def _format_schedule(self, line: Line) -> str:
        passages = self._get_stop_monitoring(line)
        line_ref = self._get_line_ref(line)
        filtered_all = self._filter_relevant_passages(passages, line_ref)
        if not filtered_all:
            return f"No upcoming trips for line {line.name} - direction {line.direction}."

        relevant_passages = self._get_relevant_passages(passages, line_ref, line)
        display_list = self._build_display_list(relevant_passages, filtered_all)
        return self._format_schedule_output(display_list, line)

    def _display_all(self, reverse: bool = False):
        target_lines = self.return_lines if reverse else self.outbound_lines
        display = ''
        for line in target_lines:
            display += self._format_schedule(line)
        return display


def _get_journeys_url() -> str:
    url = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/journeys"
    headers = {"Accept": "application/json", "apikey": API_TOKEN}
    return url, headers

def parse_itinerary_response(data: dict) -> ItineraryResult:
    parsed_journeys = []
    raw_journeys = data.get("journeys", [])
    for r_journey in raw_journeys:
        parsed_sections = []
        for r_section in r_journey.get("sections", []):
            section_type = r_section.get("type", "")
            duration = r_section.get("duration", 0)
            mode = r_section.get("mode", "")
            line = ""
            if "display_informations" in r_section:
                if not mode:
                    mode = r_section["display_informations"].get("commercial_mode", "")
                line = r_section["display_informations"].get("code", "")
            parsed_sections.append(JourneySection(type=section_type, duration=duration, mode=mode, line=line))
        parsed_journeys.append(Journey(duration=r_journey.get("duration", 0), sections=parsed_sections))
    return ItineraryResult(journeys=parsed_journeys)

def debug_stop_points(stop_ids):
    for sid in stop_ids:
        stop_ref = f"STIF:StopPoint:Q:{sid}:"
        visits = _fetch_stop_monitoring_data(stop_ref)
        if visits:
            first_visit = visits[0].get("MonitoredVehicleJourney", {})
            dest_list = first_visit.get("DestinationName", [])
            dest = dest_list[0].get("value") if isinstance(dest_list, list) and len(dest_list) > 0 else "N/A"
            print(f"ID: {sid} -> Destination: {dest}")
            if not dest or dest == "N/A":
                print(f"DEBUG: Structure complète du premier visit: {first_visit}")
        else:
            print(f"ID: {sid} -> Aucune donnée temps réel")

def _is_matching_filter(f_str: str, c_low: str, lab_low: str, l_low: str) -> bool:
    if f_str == c_low or f_str == lab_low or f_str == l_low:
        return True
    words = [w for w in re.split(r'[\s.,;:/\\]+', f_str) if w]
    if not words:
        return False
    return all(word in c_low or word in lab_low or word in l_low for word in words)

def fetch_itinerary(start: str, end: str, filter_ligne: str = None, departure_time: str = None, prohibited_modes: List[str] = None, channel: str = None) -> dict:
    start_parts = start.split(',')
    start_inverted = f"{start_parts[1].strip()};{start_parts[0].strip()}"

    end_parts = end.split(',')
    end_inverted = f"{end_parts[1].strip()};{end_parts[0].strip()}"

    url, headers = _get_journeys_url()
    params = {
        "from": start_inverted,
        "to": end_inverted
    }

    if prohibited_modes:
        params["prohibited_modes[]"] = prohibited_modes
    if departure_time:
        params["datetime"] = departure_time

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return
        data = response.json()
        if not filter_ligne or "journeys" not in data:
            display_commute(data)
            return

        filtered_journeys = []
        for journey in data.get("journeys", []):
            has_target_bus = False
            for section in journey.get("sections", []):
                display_info = section.get("display_informations") or {}
                code = display_info.get("code")
                label = display_info.get("label")
                line = section.get("line")
                c_low, lab_low, l_low = str(code).lower(), str(label).lower(), str(line).lower()
                lower_filters = [str(f).lower().strip() for f in filter_ligne] if filter_ligne else []
                if any(_is_matching_filter(f, c_low, lab_low, l_low) for f in lower_filters):
                    has_target_bus = True
                    break
            if has_target_bus:
                filtered_journeys.append(journey)
        data["journeys"] = filtered_journeys
        display_commute(data, channel)
        return
    except Exception as e:
        print(f'error in fetch_itinerary {e}')
        return

def display_commute(raw_result, channel=None):
    result = parse_itinerary_response(raw_result)
    msg = ""
    if result and hasattr(result, "journeys") and result.journeys:
        raw_journeys = raw_result.get("journeys", [])
        for idx, journey in enumerate(result.journeys, 1):
            raw_journey = raw_journeys[idx - 1]
            raw_start = raw_journey.get("departure_date_time", "")
            raw_end = raw_journey.get("arrival_date_time", "")
            start_dt = datetime.strptime(raw_start, "%Y%m%dT%H%M%S")
            end_dt = datetime.strptime(raw_end, "%Y%m%dT%H%M%S")
            msg += f"\n--- Option #{idx} (Total: {journey.duration // 60} min) [{start_dt.strftime('%H:%M')} -> {end_dt.strftime('%H:%M')}] ---\n"
            current_dt = start_dt
            for section in journey.sections:
                mode_str = f" ({section.mode})" if section.mode else ""
                line_str = f" [Ligne {section.line}]" if section.line else ""
                next_dt = current_dt + timedelta(seconds=section.duration)
                time_str = f" [{current_dt.strftime('%H:%M')} -> {next_dt.strftime('%H:%M')}]"
                msg += f"{section.type}{mode_str}{line_str}{time_str}: {section.duration}s\n"
                current_dt = next_dt
    else:
        msg = "Aucun itinéraire trouvé."

    print(msg)
    if not channel:
        channel='notify-me'
    Utils.send_discord_notification(msg, channel=channel)

def test_commute():
    start = cfg.ratp.location.home
    end = cfg.ratp.location.workplace
    filter_ligne = cfg.ratp.commute.work.mandatory_line or None
    depart = None
    # depart = "20260706T072000"
    fetch_itinerary(
        start=start,
        end=end,
        filter_ligne=filter_ligne,
        departure_time=depart
    )

if __name__ == "__main__":
    setup_logging()
    test_commute()
    # outbound = [Line('10', 'Pont de Saint-Cloud', '21970', 'C01380', 5), Line('13', 'Saint-Denis-Université', '22229', 'C01383', 5)]
    # returns = [Line('9', 'Montreuil', '462914', 'C01379', 5)]
    # my_trip = Trip(outbound, returns)
    # print("--- Outbound ---")
    # display = my_trip._display_all(reverse=False)
    # print(display)
    # print("\n--- Return ---")
    # display = my_trip._display_all(reverse=True)
    # print(display)
    # debug_stop_points(["25585", "24484", "8013"])
