import os
import sys
import re
import importlib
import inspect
from pathlib import Path
import asyncio
from common.conf_manager import cfg, setup_logging
from common.llm_client import llm
from fastmcp import FastMCP

import logging
setup_logging()
logger = logging.getLogger(__name__)

EXCLUDE_DIRS = {"__pycache__", "agents", "data", "index_db"}

ask_tools_registry = {}


def find_service_files():
    service_files = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file == "service.py" and "skills" in root.split(os.sep):
                rel_path = os.path.relpath(os.path.join(root, file))
                service_files.append(rel_path)
    return service_files

def path_to_module_name(rel_path):
    return rel_path.replace(os.sep, ".").removesuffix(".py")

def auto_register_tools(mcp_instance):
    global ask_tools_registry
    service_files = find_service_files()
    for rel_path in service_files:
        mod_name = path_to_module_name(rel_path)
        logger.info(f"[Scan] Checking target service file: {rel_path} (module: {mod_name})")
        try:
            module = importlib.import_module(mod_name)
        except Exception as e:
            logger.error(f"  [Error] Failed to import {mod_name}: {e}")
            continue
        for name, obj in inspect.getmembers(module):
            is_public_function = inspect.isfunction(obj) and not name.startswith("_")
            if is_public_function and obj.__module__ == module.__name__ and obj.__doc__:
                logger.info(f"  -> Found function tool: {name}")
                mcp_instance.tool()(obj)
                if name.startswith("ask_"):
                    ask_tools_registry[name] = obj

def clean_docstring(docstring):
    if not docstring:
        return "No description available."
    cleaned = docstring.strip().replace("\n", " ").replace("  ", " ")
    first_sentence = cleaned.split(".")[0]
    first_sentence = first_sentence.split("Args:")[0]
    first_sentence = first_sentence.split("Use this tool")[0]
    first_sentence = first_sentence.strip()
    return first_sentence if first_sentence else "No description available."

def get_ask_tools_list():
    """Construit la liste textuelle des tools ask_* pour le prompt du routeur."""
    ask_tools = []
    for rel_path in find_service_files():
        mod_name = path_to_module_name(rel_path)
        try:
            module = importlib.import_module(mod_name)
        except Exception as e:
            logger.error(f"[Error] Failed to import {mod_name}: {e}")
            continue
        for name, obj in inspect.getmembers(module):
            is_ask_function = inspect.isfunction(obj) and name.startswith("ask_")
            if is_ask_function and obj.__module__ == module.__name__:
                description = clean_docstring(inspect.getdoc(obj))
                ask_tools.append({"name": name, "description": description})
    if not ask_tools:
        return "No ask_* tools available."
    lines = []
    for tool in ask_tools:
        lines.append(f"- **{tool['name']}** : {tool['description']}")
    return "\n".join(lines)

def generate_ask_tools_prompt():
    template_content = cfg.agents.ask_tools_router
    ask_tools_list = get_ask_tools_list()
    return template_content.replace("{{ASK_TOOLS_LIST}}", ask_tools_list)

def ask(request_str: str) -> str:
    """Route une requête utilisateur vers le bon tool ask_* via le LLM."""
    system_prompt = generate_ask_tools_prompt()
    raw = llm.call(system_prompt, request_str, model=cfg.llm_models.mcp)
    tool_name = raw.get("content", "").strip()
    if not tool_name or tool_name == "None":
        return "No matching ask_* tool found for the request."
    if tool_name not in ask_tools_registry:
        return f"Unknown ask_* tool: {tool_name}"
    fn = ask_tools_registry[tool_name]
    result = fn(request_str)
    if cfg.get("debug", False):
        return f"Tool called: {tool_name}\n{result}"
    return result

def discover_test_cases():
    all_cases = []
    skills_dir = Path(__file__).parent / "skills"
    for service_path in sorted(skills_dir.glob("*/service.py")):
        skill_name = service_path.parent.name
        module_name = f"skills.{skill_name}.service"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"[test_ask_router] Could not import {module_name}: {e}")
            continue
        test_cases_list = None
        for name, obj in inspect.getmembers(module):
            is_test_cases_list = isinstance(obj, list) and (name == "TEST_CASES" or name.endswith("_TEST_CASES"))
            if is_test_cases_list:
                test_cases_list = obj
                break
        if not test_cases_list:
            logger.debug(f"[test_ask_router] No TEST_CASES in {module_name}, skipping")
            continue
        for item in test_cases_list:
            if len(item) == 3:
                test_request, expected_tool, validator = item
            else:
                test_request, expected_tool = item
                validator = None
            all_cases.append((skill_name, test_request, expected_tool, validator))
    return all_cases

def extract_executed_tool(result_str):
    matches = re.findall(r"Tool called:\s*(\S+)", result_str)
    return matches[-1] if matches else None

def run_one_test(skill_name, test_request, expected_tool, validator):
    logger.info(f"=== [{skill_name}] Testing: '{test_request}' (Expected: {expected_tool}) ===")
    try:
        result = ask(test_request)
    except Exception as e:
        logger.error(f"[test_ask_router] EXCEPTION during ask('{test_request}'): {e}")
        return (skill_name, test_request, expected_tool, None, False, f"EXCEPTION: {e}")
    result_str = str(result)
    logger.info(f"[test_ask_router] Result: {result_str}")
    executed_tool = extract_executed_tool(result_str)
    routing_ok = True
    if expected_tool:
        routing_ok = (executed_tool == expected_tool)
    content_ok = True
    if validator:
        try:
            content_ok = bool(validator(result_str))
        except Exception as e:
            content_ok = False
            logger.error(f"[test_ask_router] Validator exception: {e}")
    passed = routing_ok and content_ok
    status = "PASS" if passed else "FAIL"
    logger.info(f"{status} — [{skill_name}] expected='{expected_tool}' executed='{executed_tool}'")
    return (skill_name, test_request, expected_tool, executed_tool, passed, result_str)

def build_summary(results):
    total = len(results)
    passed_count = 0
    for r in results:
        if r[4]:
            passed_count += 1
    summary_lines = []
    for skill_name, req, exp, executed, passed, _result_str in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        line = f'{status} — prompt: "{req}" --> [{skill_name}] :\n    expected: {exp} --> executed: {executed}'
        summary_lines.append(line)
    summary = "\n".join(summary_lines)
    header = f"=== test_ask_router SUMMARY: {passed_count}/{total} passed ==="
    return f"{header}\n{summary}"

def create_server() -> FastMCP:
    global ask_tools_registry
    mcp_instance = FastMCP("My Super Server")
    auto_register_tools(mcp_instance)

    @mcp_instance.tool()
    async def list_available_tools() -> str:
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

    @mcp_instance.tool()
    def call_ask(request_str: str) -> str:
        return ask(request_str)

    @mcp_instance.tool()
    def test_ask_router():
        all_cases = discover_test_cases()
        if not all_cases:
            logger.warning("[test_ask_router] No TEST_CASES found in any skill")
            return "No test cases found"
        results = []
        for skill_name, test_request, expected_tool, validator in all_cases:
            result = run_one_test(skill_name, test_request, expected_tool, validator)
            results.append(result)
        summary_text = build_summary(results)
        logger.info(summary_text)
        return summary_text

    @mcp_instance.tool()
    def run_all_unit_tests() -> str:
        results = []
        for rel_path in find_service_files():
            mod_name = path_to_module_name(rel_path)
            try:
                module = importlib.import_module(mod_name)
            except ImportError as e:
                logger.warning(f"[Warning] Skipping {mod_name} (import error): {e}")
                continue
            except Exception as e:
                logger.error(f"[Error] Failed to process {mod_name}: {e}")
                continue
            for name, obj in inspect.getmembers(module):
                if name.startswith("TU_") and callable(obj):
                    logger.info(f"Running unit test: {name}")
                    try:
                        test_result = obj()
                        results.append(f"=== {name} ===\n{test_result}\n")
                    except Exception as e:
                        results.append(f"=== {name} ===\n[ERROR] {str(e)}\n")
        return "\n".join(results) if results else "No unit tests found."
    return mcp_instance

mcp = create_server()

def available_functions():
    logger.info("\n=== REGISTERED MCP TOOLS ===")
    tools_list = asyncio.run(mcp.list_tools())
    for tool in tools_list:
        desc = tool.description if tool.description else "(No description)"
        logger.info(f"  - {tool.name}: {desc}")
    logger.info("============================\n")
    logger.info("=== TESTING list_available_tools ===")
    target_tool = None
    for t in tools_list:
        if t.name == "list_available_tools":
            target_tool = t
            break
    if target_tool:
        result = asyncio.run(target_tool.run({}))
        logger.info(result)
    else:
        logger.info("[Error] list_available_tools is not registered.")
    logger.info("====================================\n")

def find_tool_by_name(tools_list, tool_name):
    for t in tools_list:
        if t.name == tool_name:
            return t
    return None

def run_tool_and_log(tool):
    result = asyncio.run(tool.run({}))
    if hasattr(result, "content") and result.content:
        text = result.content[0].text
    else:
        text = str(result)
    logger.info("\n" + text)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "test":
            available_functions()
            tools_list = asyncio.run(mcp.list_tools())
            test_ask_tool = find_tool_by_name(tools_list, "test_ask_router")
            if test_ask_tool:
                run_tool_and_log(test_ask_tool)

        elif command == "all":
            tools_list = asyncio.run(mcp.list_tools())
            unit_test_tool = find_tool_by_name(tools_list, "run_all_unit_tests")
            if unit_test_tool:
                run_tool_and_log(unit_test_tool)
    else:
        mcp.run(transport="sse", host="0.0.0.0", port=13316)
