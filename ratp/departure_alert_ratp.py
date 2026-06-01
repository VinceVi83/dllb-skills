import requests
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List
from config_loader import cfg

API_TOKEN = cfg.ratp.token

@dataclass
class Line:
    name: str
    direction: str
    stop: str
    id_name: str
    walk: int

class Trip:
    def __init__(self, outbound_lines: List[Line], return_lines: List[Line]):
        self.outbound_lines = outbound_lines
        self.return_lines = return_lines

    def _get_stop_monitoring(self, line: Line) -> list:
        stop_ref = f"STIF:StopPoint:Q:{line.stop}:"
        url = "https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring"
        headers = {"Accept": "application/json", "apikey": API_TOKEN}
        params = {"MonitoringRef": stop_ref}

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                return []
            
            data = response.json()
            # print(data)
            deliveries = data.get("Siri", {}).get("ServiceDelivery", {}).get("StopMonitoringDelivery", [])
            
            all_visits = []
            for delivery in deliveries:
                all_visits.extend(delivery.get("MonitoredStopVisit", []))
            return all_visits
        except Exception:
            return []

    def format_schedule(self, line: Line) -> str:
        passages = self._get_stop_monitoring(line)
        line_ref = f"STIF:Line::{line.id_name}:"
        
        filtered_all = [
            p for p in passages 
            if p.get("MonitoredVehicleJourney", {}).get("LineRef", {}).get("value") == line_ref
        ]

        if not filtered_all:
            return f"No upcoming trips for line {line.name} - direction {line.direction}."

        relevant_passages = []
        for p in filtered_all:
            journey = p.get("MonitoredVehicleJourney", {})
            call = journey.get("MonitoredCall", {})
            time_str = call.get("ExpectedDepartureTime") or call.get("ExpectedArrivalTime")
            
            if time_str:
                bus_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                minutes = int((bus_time - datetime.now(timezone.utc)).total_seconds() // 60) - line.walk
                if (minutes) >= 0:
                    relevant_passages.append((p, minutes, bus_time))

        display_list = relevant_passages if relevant_passages else [
            (p, None, datetime.fromisoformat(p.get("MonitoredVehicleJourney", {}).get("MonitoredCall", {}).get("ExpectedDepartureTime", "2000-01-01T00:00:00Z").replace("Z", "+00:00"))) 
            for p in filtered_all[:3]
        ]

        output = f"\n=== SCHEDULE - LINE {line.name} - Destination : {line.direction} ===\n"
        header_added = False
        
        for p, minutes, bus_time in display_list:
            journey = p.get("MonitoredVehicleJourney", {})
            dest = journey.get("DestinationName", [{}])[0].get("value", "Unknown")
            
            display_time = "Approaching!" if minutes is not None and minutes <= 0 else (f"{minutes} min" if minutes is not None else "Passed/Soon")
            
            if not header_added:
                output += f"➔ {dest}\n"
                header_added = True
            output += f"    └─ {bus_time.astimezone().strftime('%H:%M')} ({display_time})\n"
        
        return output

    def display_all(self, reverse: bool = False):
        target_lines = self.return_lines if reverse else self.outbound_lines
        display = ''
        for line in target_lines:
            display += self.format_schedule(line)
        return display

if __name__ == "__main__":
    outbound = [Line('10', 'Pont de Saint-Cloud', '21970', 'C01380', 5), Line('13', 'Saint-Denis-Université', '22229', 'C01383', 5)]
    returns = [Line('9', 'Montreuil', '462914', 'C01379', 5)]
    
    # 10 https://www.ratp.fr/itineraires/Duroc_%2075007%20Paris%26Marcel%20Sembat_%2092100%20Boulogne-Billancourt
    # 9 https://www.ratp.fr/itineraires/Marcel%20Sembat_%2092100%20Boulogne-Billancourt%26Duroc_%2075007%20Paris
    my_trip = Trip(outbound, returns)
    
    print("--- Outbound ---")
    display = my_trip.display_all(reverse=False)
    print(display)
    print("\n--- Return ---")
    display = my_trip.display_all(reverse=True)
    print(display)