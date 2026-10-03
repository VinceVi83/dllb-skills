# Dynamic MCP Server & Skills Management

This repository implements a dynamic Model Context Protocol (MCP) server that automatically discovers, registers, and exposes tools from skill modules without hardcoding dependencies.

---

## Architecture Overview

The system follows a modular architecture where the MCP server dynamically interacts with skill modules through a standardized interface.

```
[ mcp_dynamic_server.py ]
│
▼ Dynamically scans and imports
skills/
├── <skill_1>/
│   └── service.py
├── <skill_2>/
│   └── service.py
└── <skill_n>/
    └── service.py
```

The server acts as a **polymorphic gateway** that:
1. Scans the `skills/` directory for all `service.py` files
2. Imports modules dynamically using Python's `importlib`
3. Registers all documented functions as MCP tools
4. Routes requests to the appropriate skill function

---

## Core Components

### 1. Dynamic Tool Registration
The server automatically discovers and registers tools from each `service.py` file in the `skills/` directory.

- **Automatic Discovery**: The server walks through the `skills/` directory to find all `service.py` files
- **Tool Registration**: Each public function (not starting with `_`) with a docstring in a `service.py` file is registered as an MCP tool
- **Ask Tools Registry**: Functions starting with `ask_` are registered in a dedicated registry for the ask routing system

### 2. Skill Module Structure
Each skill module must follow a standardized structure to be automatically discovered and integrated:

- **Location**: Each skill must be in its own subdirectory under `skills/`
- **Entry Point**: Each skill must have a `service.py` file containing its tools and logic
- **Isolation**: Skills are completely isolated from each other, with their own dependencies and configurations

### 3. Testing Framework
The system includes a dynamic testing framework to verify skill functionality:

- **Test Cases**: Each skill can define a `<SKILL>_TEST_CASES` list in its `service.py` file containing tuples of `(label, request_string)`
- **Unit Tests**: Each skill can define a `TU_<skill>` function for standalone testing
- **Integration Tests**: The server provides MCP tools to run all unit tests (`run_all_unit_tests`) or test the ask router (`test_ask_router`)

### 4. Dynamic Routing
The server includes a routing mechanism for `ask_*` functions:

- **Prompt Generation**: The `generate_ask_tools_prompt` function creates a system prompt listing all available `ask_*` tools
- **Ask Function**: The `ask` function uses an LLM to route user requests to the appropriate `ask_*` tool
- **Tool Execution**: The selected tool is executed with the original request

---

## Dynamic Management

### Adding a New Skill
To add a new skill to the system:

1. Create a new directory under `skills/` for your skill
2. Add a `service.py` file with your skill's functions
3. Ensure all public functions have clear docstrings
4. The server will automatically discover and register your skill's tools on the next run

**No code changes to the core server are required.**

### Testing a Skill
To test a skill:

1. Define test cases in a `<SKILL>_TEST_CASES` list:
   ```python
   WEATHER_TEST_CASES = [
       ("current", "What is the weather like right now?"),
       ("forecast", "What is the weather forecast for tomorrow?"),
   ]
   ```
2. Implement a `TU_<skill>` function to execute the test cases:
   ```python
   def TU_weather():
       results = []
       for label, req in WEATHER_TEST_CASES:
           # Test each case
           out = ask_weather_question(req)
           results.append(f"{label}: {out}")
       return "\n".join(results)
   ```
3. Use the `run_all_unit_tests` MCP tool to execute all unit tests across all skills
4. Use the `test_ask_router` MCP tool to test all ask functions with their defined test cases

### Routing Configuration
To integrate with the ask routing system:

1. Implement functions starting with `ask_` in your `service.py`:
   ```python
   def ask_weather_question(request_str: str) -> str:
       """Answer any question about weather, forecast, or temperature."""
       return ha_weather.get_llm_payload(request_str)
   ```
2. Provide clear, concise docstrings for these functions
3. The server will automatically include them in the routing system

---

## Dynamic Features

### Automatic Discovery
- The server automatically discovers new skills and tools without requiring code changes
- New skills are integrated by simply adding them to the `skills/` directory
- The server manages Python's `sys.path` automatically to ensure all skills can be imported

### Dynamic Prompt Generation
- System prompts are generated dynamically based on available `ask_*` tools
- The `ask_tools_router.md` template is used to create a consistent interface for the LLM

### Flexible Testing
- Test cases and unit tests are discovered dynamically
- The testing framework adapts to new skills as they are added
- Both unit tests (`TU_*`) and test cases (`*_TEST_CASES`) are automatically collected and executed

---

## Directory Structure

```
.
├── mcp_dynamic_server.py    # Main server implementation
├── agents/                  # System prompts and templates
│   └── ask_tools_router.md   # Template for ask_* routing
├── common/                  # Shared utilities and configuration
└── skills/                  # Skill modules
    └── <skill>/             # Individual skill directories
        └── service.py       # Skill implementation (REQUIRED)
```

---

## Key Implementation Details

### File Discovery
- Only files named exactly `service.py` are processed
- Only directories containing `skills` in their path are considered
- Excluded directories: `__pycache__`, `agents`, `data`, `index_db`
- Excluded files: `server_mcp.py`, `mcp_cli.py`

### Function Registration
- Public functions (not starting with `_`) with docstrings are registered as MCP tools
- Functions starting with `ask_` are added to the ask tools registry
- Class methods with docstrings are also registered as tools

### Test Collection
- Functions starting with `TU_` are executed as unit tests
- Lists ending with `_TEST_CASES` are collected for ask router testing
- Each test case tuple should be `(label, request_string)` where the request string is used as input

---

## Usage

### Running the Server
```bash
python mcp_dynamic_server.py
```
Starts the MCP server on port 13316 with SSE transport.

### Testing
```bash
# List available tools and test the ask router
python mcp_dynamic_server.py test

# Run all unit tests (TU_* functions)
python mcp_dynamic_server.py all
```

### MCP Tools Available
- `list_available_tools`: Lists all registered MCP tools
- `call_ask`: Routes a request through the ask system to the appropriate `ask_*` function
- `test_ask_router`: Tests all `ask_*` functions with their defined test cases
- `run_all_unit_tests`: Executes all `TU_*` functions across all skills

---

## Design Principles

1. **Modularity**: Each skill is a self-contained module with clear interfaces
2. **Automatic Discovery**: The system dynamically discovers and integrates new skills
3. **Consistency**: Standardized interfaces ensure all skills work seamlessly together
4. **Extensibility**: New features can be added by following the established patterns
5. **Isolation**: Skills are isolated from each other, preventing dependency conflicts
6. **Privacy**: Skills are personal implementations - only their interfaces are discovered dynamically, not their internal logic

---

## Important Notes

- Skills are **personal implementations** and should not be exposed in documentation
- The server only discovers and exposes the **public interface** (functions with docstrings) of each skill
- Internal implementation details, dependencies, and configurations remain private to each skill
- The dynamic system ensures that adding, removing, or modifying skills requires no changes to the core server code