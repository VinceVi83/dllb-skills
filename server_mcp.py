from fastmcp import FastMCP
from weather.meteo import WeatherHaApi
from ratp.departure_alert_ratp import Trip, Line
from config_loader import cfg

mcp = FastMCP("Mon Super Serveur")
outbound = [Line(**line.to_dict()) for line in cfg.ratp.outbound]
returns = [Line(**line.to_dict()) for line in cfg.ratp.returns]
my_trip = Trip(outbound, returns)

outbound_test = [Line(**line.to_dict()) for line in cfg.ratp_test.outbound]
returns_test = [Line(**line.to_dict()) for line in cfg.ratp_test.returns]
my_trip_test = Trip(outbound_test, returns_test)

@mcp.tool()
def tracking(content: str) -> str:
    """Additionne deux nombres entiers (a + b)."""
    print("add a + b")
    return content

@mcp.tool()
def soustraction(a: int, b: int) -> int:
    """Calcule la différence (a - b)."""
    print("add a - b")
    return a - b

@mcp.resource("config://app")
def get_config() -> str:
    print("get_config")
    return "Test | Version: 2.0.0"

@mcp.tool()
def querry_weather(info) -> str:
    """Querry information about weather"""
    ha_weather = WeatherHaApi()
    return ha_weather.get_llm_payload('Quelle est la météo')

@mcp.tool()
def go_to_work_test() -> str:
    """
    APPELER CET OUTIL UNIQUEMENT SI l'utilisateur veut connaître les horaires de bus 
    ou recevoir une notification pour aller au TRAVAIL. 
    Ne pas utiliser pour autre chose.
    """
    print('go_to_work')
    return my_trip_test.display_all(reverse=False)

@mcp.tool()
def go_home_test() -> str:
    """
    APPELER CET OUTIL UNIQUEMENT SI l'utilisateur veut connaître les horaires de bus 
    ou recevoir une notification pour aller à la MAISON. 
    Ne pas utiliser pour autre chose.
    """
    print('go_home')
    return my_trip_test.display_all(reverse=True)

@mcp.tool()
def go_to_work() -> str:
    """
    APPELER CET OUTIL UNIQUEMENT SI l'utilisateur veut connaître les horaires de bus 
    ou recevoir une notification pour aller au TRAVAIL. 
    Ne pas utiliser pour autre chose.
    """
    print('go_to_work')
    return my_trip.display_all(reverse=False)

@mcp.tool()
def go_home() -> str:
    """
    APPELER CET OUTIL UNIQUEMENT SI l'utilisateur veut connaître les horaires de bus 
    ou recevoir une notification pour aller à la MAISON. 
    Ne pas utiliser pour autre chose.
    """
    print('go_home')
    return my_trip.display_all(reverse=True)

if __name__ == "__main__":
    mcp.run()