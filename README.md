# Dynamic MCP Server & Skills Management

This repository contains the dynamic Model Context Protocol (MCP) server implementation. Instead of hardcoding tools and functions, this server dynamically registers, and executes function from service.py of each skill.

---

## Architecture Overview

[ mcp_dynamic_server.py ]
│
▼ Scans & monitors
skills/
├── scrap-url/
├── ratp/
└── anime-notify/
└── weather/

The server acts as a polymorphic gateway: it scans the filesystem structure to dynamically expose all sub-skills to any calling agent or orchestrator.

---

## Skills Directory Management (`skills/`)

Every sub-folder inside the `skills/` directory can be executed standalone.

* **Absolute Isolation:** Each folder contains its own business logic, configurations, and scripts.
* **Autodiscovery:** Adding a new skill requires zero modifications to the core mcp server code. Simply dropping a new folder into `skills/` makes it instantly available for schema discovery.
