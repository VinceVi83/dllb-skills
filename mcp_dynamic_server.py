import os
import sys
import importlib
import inspect
from datetime import datetime
from fastmcp import FastMCP
from config_loader import cfg
import asyncio

EXCLUDE_DIRS = {"__pycache__", "agents", "data", "index_db"}
EXCLUDE_FILES = {"server_mcp.py", "config_loader.py", "mcp_cli.py"}

def auto_register_tools(mcp_instance, root_dir):
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            if file == "service.py" and "skills" in root.split(os.sep):
                rel_path = os.path.relpath(os.path.join(root, file), root_dir)
                mod_name = rel_path.replace(os.sep, ".").removesuffix(".py")
                
                print(f"[Scan] Checking target service file: {rel_path} (module: {mod_name})")
                try:
                    module = importlib.import_module(mod_name)
                    for name, obj in inspect.getmembers(module):
                        if inspect.isfunction(obj) and not name.startswith("_"):
                            if obj.__module__ == module.__name__ and obj.__doc__:
                                print(f"  -> Found function tool: {name}")
                                mcp_instance.tool()(obj)
                        
                        elif inspect.isclass(obj) and obj.__module__ == module.__name__:
                            for method_name, method_obj in inspect.getmembers(obj, predicate=inspect.isfunction):
                                if not method_name.startswith("_") and method_obj.__doc__:
                                    print(f"  -> Found class method tool candidate: {obj.__name__}.{method_name}")
                except Exception as e:
                    print(f"  [Error] Failed to import {mod_name}: {e}")

def create_server() -> FastMCP:
    mcp_instance = FastMCP("My Super Server")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    auto_register_tools(mcp_instance, project_root)
    
    @mcp_instance.resource("config://app")
    def get_config() -> str:
        return "Test | Version: 2.0.0"

    @mcp_instance.tool()
    async def list_available_tools() -> str:
        """
        Returns a string listing all currently registered MCP tools on this server.
        """
        try:
            if hasattr(mcp_instance, "list_tools") and callable(mcp_instance.list_tools):
                tools = await mcp_instance.list_tools()
                names = [t.name for t in tools]
                return "Registered tools: " + ", ".join(names)
        except Exception as e:
            return f"Error retrieving tools: {e}"
            
        if hasattr(mcp_instance, "_registry") and hasattr(mcp_instance._registry, "tools"):
            names = [t.name for t in mcp_instance._registry.tools]
            return "Registered tools: " + ", ".join(names)
        elif hasattr(mcp_instance, "_tools"):
            return "Registered tools: " + ", ".join(mcp_instance._tools.keys())
            
        return "No tools found or registry format unsupported."
        
    return mcp_instance

mcp = create_server()

def available_functions():
    print("\n=== REGISTERED MCP TOOLS ===")
    tools_list = asyncio.run(mcp.list_tools())
    
    for tool in tools_list:
        desc = tool.description if tool.description else "(No description)"
        print(f"  - {tool.name}: {desc}")
    print("============================\n")

    print("=== TESTING list_available_tools ===")
    target_tool = next((t for t in tools_list if t.name == "list_available_tools"), None)
    
    if target_tool:
        result = asyncio.run(target_tool.run({}))
        print(result)
    else:
        print("[Error] list_available_tools is not registered.")
    print("====================================\n")

def test(function_name):
    tools_list = asyncio.run(mcp.list_tools())
    target_tool = next((t for t in tools_list if t.name == function_name), None)
    
    if target_tool:
        result = asyncio.run(target_tool.run({}))
        if hasattr(result, "content") and result.content:
            print(result.content[0].text)
        else:
            print(result)
    else:
        print(f"[Error] {function_name} is not registered.")
    print("====================================\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        available_functions()
        # test("notify_new_anime")
        # test("get_today_12h_forecast")
        # test("work_commute_dest")
        # test("work_commute_ret")
    else:
        mcp.run()
