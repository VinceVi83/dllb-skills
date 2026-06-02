import requests
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List
from config_loader import cfg

API_TOKEN = cfg.ratp.token


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
        format_schedule(self, line) : Format schedule for a specific line.
        display_all(self, reverse) : Display all lines (outbound or return).
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

    def format_schedule(self, line: Line) -> str:
        passages = self._get_stop_monitoring(line)
        line_ref = self._get_line_ref(line)
        
        filtered_all = self._filter_relevant_passages(passages, line_ref)
        
        if not filtered_all:
            return f"No upcoming trips for line {line.name} - direction {line.direction}."

        relevant_passages = self._get_relevant_passages(passages, line_ref, line)
        display_list = self._build_display_list(relevant_passages, filtered_all)
        
        return self._format_schedule_output(display_list, line)

    def display_all(self, reverse: bool = False):
        target_lines = self.return_lines if reverse else self.outbound_lines
        display = ''
        for line in target_lines:
            display += self.format_schedule(line)
        return display

if __name__ == "__main__":
    outbound = [Line('10', 'Pont de Saint-Cloud', '21970', 'C01380', 5), Line('13', 'Saint-Denis-Université', '22229', 'C01383', 5)]
    returns = [Line('9', 'Montreuil', '462914', 'C01379', 5)]
    
    my_trip = Trip(outbound, returns)
    
    print("--- Outbound ---")
    display = my_trip.display_all(reverse=False)
    print(display)
    print("\n--- Return ---")
    display = my_trip.display_all(reverse=True)
    print(display)
