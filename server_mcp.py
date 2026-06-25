import os
import sys
import importlib
import inspect
from datetime import datetime
from fastmcp import FastMCP
from config_loader import cfg

# Initialize MCP Server first
mcp = FastMCP("My Super Server")

# Ensure root path is available for dynamic resolution
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

EXCLUDE_DIRS = {"__pycache__", "agents", "data", "index_db"}
EXCLUDE_FILES = {"server_mcp.py", "config_loader.py", "mcp_cli.py"}

def auto_register_tools(mcp_instance, root_dir):
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            if file.endswith(".py") and file not in EXCLUDE_FILES:
                rel_path = os.path.relpath(os.path.join(root, file), root_dir)
                mod_name = rel_path.replace(os.sep, ".").removesuffix(".py")
                
                print(f"[Scan] Checking file: {rel_path} (module: {mod_name})")
                try:
                    module = importlib.import_module(mod_name)
                    for name, obj in inspect.getmembers(module):
                        # 1. Scan global standalone functions
                        if inspect.isfunction(obj) and not name.startswith("_"):
                            if obj.__module__ == module.__name__ and obj.__doc__:
                                print(f"  -> Found function tool: {name}")
                                mcp_instance.tool()(obj)
                        
                        # 2. Scan classes for methods (like WeatherHaApi)
                        elif inspect.isclass(obj) and obj.__module__ == module.__name__:
                            for method_name, method_obj in inspect.getmembers(obj, predicate=inspect.isfunction):
                                if not method_name.startswith("_") and method_obj.__doc__:
                                    # Create a wrapper or register method if it can run standalone/instantiated
                                    print(f"  -> Found class method tool candidate: {obj.__name__}.{method_name}")
                                    # For methods requiring self, you might need dedicated initialization logic.
                except Exception as e:
                    print(f"  [Error] Failed to import {mod_name}: {e}")

# Auto-discover and map tools
auto_register_tools(mcp, project_root)

@mcp.resource("config://app")
def get_config() -> str:
    return "Test | Version: 2.0.0"


if __name__ == "__main__":
    print("\n=== REGISTERED MCP TOOLS ===")
    
    registered = []
    if hasattr(mcp, "list_tools") and callable(mcp.list_tools):
        try:
            import asyncio
            import inspect
            if inspect.iscoroutinefunction(mcp.list_tools):
                tools_list = asyncio.run(mcp.list_tools())
            else:
                tools_list = mcp.list_tools()
            registered = [t.name for t in tools_list]
        except Exception:
            pass
            
    if not registered:
        if hasattr(mcp, "_registry") and hasattr(mcp._registry, "tools"):
            registered = [t.name for t in mcp._registry.tools]
        elif hasattr(mcp, "_tools"):
            registered = list(mcp._tools.keys())
        
    if registered:
        for tool_name in registered:
            print(f"  - {tool_name}")
    else:
        print("  No tools found in the standard registry locations.")
    print("============================\n")