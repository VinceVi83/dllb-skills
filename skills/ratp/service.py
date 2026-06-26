from skills.ratp.departure_alert_ratp import Trip, Line
from config_loader import cfg
from datetime import datetime

def create_trip(config_section):
    dest = [Line(**line.to_dict()) for line in config_section.dest]
    ret = [Line(**line.to_dict()) for line in config_section.ret]
    return Trip(dest, ret)

def _generate_commute_tools():
    current_module_name = __name__
    generated_names = []
    ratp_dict = vars(cfg.ratp) if hasattr(cfg.ratp, "__dict__") else cfg.ratp
    
    for key, section in ratp_dict.items():
        if key == "token" or section is None:
            continue
            
        def make_dest_func(sec, name_str):
            def func() -> str:
                my_trip = create_trip(sec)
                print('go_to_work')
                return my_trip._display_all(reverse=False)
            func.__name__ = name_str
            func.__qualname__ = name_str
            func.__module__ = current_module_name
            func.__doc__ = getattr(sec, "dest_desc", "Destination commute tool")
            return func

        def make_ret_func(sec, name_str):
            def func() -> str:
                my_trip = create_trip(sec)
                print('go_home')
                return my_trip._display_all(reverse=True)
            func.__name__ = name_str
            func.__qualname__ = name_str
            func.__module__ = current_module_name
            func.__doc__ = getattr(sec, "ret_desc", "Return commute tool")
            return func

        dest_name = f"{key}_dest"
        ret_name = f"{key}_ret"

        globals()[dest_name] = make_dest_func(section, dest_name)
        globals()[ret_name] = make_ret_func(section, ret_name)
        
        generated_names.extend([dest_name, ret_name])

    print(f"\n[Dynamic Generator] Registering tools into {current_module_name}:")
    for name in generated_names:
        func_obj = globals()[name]
        print(f"  -> Generated: {name}() | Docstring: {repr(func_obj.__doc__)} | Module: {func_obj.__module__}")
    print()

_generate_commute_tools()