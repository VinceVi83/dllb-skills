from skills.ratp.departure_alert_ratp import Trip, Line, fetch_itinerary
from datetime import datetime
from common.conf_manager import cfg, setup_logging, Utils

import logging
logger = logging.getLogger(__name__)

def create_trip(config_section):
    dest = [Line(**line.to_dict()) for line in config_section.dest]
    ret = [Line(**line.to_dict()) for line in config_section.ret]
    return Trip(dest, ret)

def _generate_departure_tools():
    current_module_name = __name__
    generated_names = []
    ratp_dict = vars(cfg.ratp.departure) if hasattr(cfg.ratp.departure, "__dict__") else cfg.ratp.departure
    for key, section in ratp_dict.items():
        if key == "token" or section is None:
            continue

        def make_dest_func(sec, name_str):
            def func() -> str:
                my_trip = create_trip(sec)
                print('go_to_work')
                msg = my_trip._display_all(reverse=False)
                Utils.send_discord_notification(msg, channel='notify-me')
                return msg
            func.__name__ = name_str
            func.__qualname__ = name_str
            func.__module__ = current_module_name
            func.__doc__ = getattr(sec, "dest_desc", "Destination commute tool")
            return func

        def make_ret_func(sec, name_str):
            def func() -> str:
                my_trip = create_trip(sec)
                msg = my_trip._display_all(reverse=True)
                Utils.send_discord_notification(msg, channel='notify-me')
                return msg
            func.__name__ = name_str
            func.__qualname__ = name_str
            func.__module__ = current_module_name
            func.__doc__ = getattr(sec, "ret_desc", "Return commute tool")
            return func

        dest_name = f"{key}_dest_departure"
        ret_name = f"{key}_ret_departure"

        globals()[dest_name] = make_dest_func(section, dest_name)
        globals()[ret_name] = make_ret_func(section, ret_name)
        generated_names.extend([dest_name, ret_name])

    print(f"\n[Dynamic Generator] Registering tools into {current_module_name}:")
    for name in generated_names:
        func_obj = globals()[name]
        print(f"  -> Generated: {name}() | Docstring: {repr(func_obj.__doc__)} | Module: {func_obj.__module__}")
    print()

def _generate_itinerary_tools():
    current_module_name = __name__
    generated_names = []
    if not hasattr(cfg, "ratp") or not hasattr(cfg.ratp, "commute"):
        return

    commute_dict = vars(cfg.ratp.commute) if hasattr(cfg.ratp.commute, "__dict__") else cfg.ratp.commute

    for key, section in commute_dict.items():
        if key.startswith("_") or section is None:
            continue

        start_key = getattr(section, "from", None) if hasattr(section, "from") else section.get("from")
        end_key = getattr(section, "to", None) if hasattr(section, "to") else section.get("to")
        filter_ligne = getattr(section, "mandatory_line", []) if hasattr(section, "mandatory_line") else section.get("mandatory_line", [])
        custom_doc = getattr(section, "desc", None) if hasattr(section, "desc") else section.get("desc")

        start_coord = getattr(cfg.ratp.location, start_key, None) if hasattr(cfg.ratp, "location") else None
        end_coord = getattr(cfg.ratp.location, end_key, None) if hasattr(cfg.ratp, "location") else None

        def make_itinerary_func(start, end, lines, name_str, doc_str):
            async def func() -> dict:
                return fetch_itinerary(
                    start=start,
                    end=end,
                    # departure_time = "20260706T072000",
                    filter_ligne=lines
                )
            func.__name__ = name_str
            func.__qualname__ = name_str
            func.__module__ = current_module_name
            func.__doc__ = doc_str if doc_str else f"Fetches dynamic itinerary details for profile: {key}"
            return func

        outbound_name = f"commute_{key}"
        outbound_doc = custom_doc
        globals()[outbound_name] = make_itinerary_func(start_coord, end_coord, filter_ligne, outbound_name, outbound_doc)
        generated_names.append(outbound_name)

        return_name = f"commute_{key}_ret"
        return_doc = f"Return route: {custom_doc}" if custom_doc else f"Fetches dynamic return itinerary details for profile: {key}"
        globals()[return_name] = make_itinerary_func(end_coord, start_coord, filter_ligne, return_name, return_doc)
        generated_names.append(return_name)

    print(f"\n[Dynamic Itinerary Generator] Registering itinerary tools into {current_module_name}:")
    for name in generated_names:
        func_obj = globals()[name]
        print(f"  -> Generated: {name}() | Docstring: {repr(func_obj.__doc__)} | Module: {func_obj.__module__}")
    print()

def go_home(start, filter=None, departure_time=None):
    """
    I want to go home
    """
    fetch_itinerary(
        start=start,
        end=cfg.location.home,
        filter=filter or None,
        departure_time=departure_time or None
    )

_generate_departure_tools()
_generate_itinerary_tools()
