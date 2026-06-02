from fastmcp import FastMCP
from weather.weather import WeatherHaApi
from ratp.departure_alert_ratp import Trip, Line
from config_loader import cfg

mcp = FastMCP("My Super Server")

def create_trip(config_section):
    outbound = [Line(**line.to_dict()) for line in config_section.outbound]
    returns = [Line(**line.to_dict()) for line in config_section.returns]
    return Trip(outbound, returns)

my_trip = create_trip(cfg.ratp)
my_trip_test = create_trip(cfg.ratp_test)

@mcp.tool()
def tracking(content: str) -> str:
    """Additionne deux nombres entiers (a + b)."""
    print("add a + b")
    return content

@mcp.tool()
def subtraction(a: int, b: int) -> int:
    """Calcule la différence (a - b)."""
    return a - b

@mcp.resource("config://app")
def get_config() -> str:
    print("get_config")
    return "Test | Version: 2.0.0"

@mcp.tool()
def query_weather(info) -> str:
    """Query information about weather"""
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
