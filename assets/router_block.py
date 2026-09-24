def _build_tools_prompt() -> str:
    """List public functions with their signature and docstring."""
    tools = []
    for name, fn in globals().items():
        if not inspect.isfunction(fn):
            continue
        if fn.__module__ != __name__:
            continue
        if name.startswith(("ask", "_")):
            continue
        sig = inspect.signature(fn)
        tools.append({
            "name": name,
            "signature": str(sig),
            "parameters": {
                p.name: {
                    "type": str(p.annotation) if p.annotation is not inspect.Parameter.empty else "str",
                    "default": p.default if p.default is not inspect.Parameter.empty else None,
                }
                for p in sig.parameters.values()
            },
            "description": inspect.getdoc(fn) or "",
        })
    return cfg.agents.<skill>_router.replace(
        "{{TOOLS}}", json.dumps(tools, indent=2, ensure_ascii=False, default=str)
    )

def _synthesize(request_str: str, result: str) -> str:
    """Turn raw tool output into a human answer. Empty result → no LLM call."""
    if result.strip() in ("", "[]", "{}", "None"):
        return "Nothing to report."
    system = cfg.agents.<skill>_secretary.replace(
        "{{NOW}}", datetime.now().strftime("%A, %d %B %Y %H:%M")
    )
    user = f"# User request\n{request_str}\n\n# Raw data\n{result}"
    return llm.call(system, user, model=cfg.llm_models.creative)

def ask_<domain>(request_str: str) -> str:
    """
    Answer any free-text question about <domain> by routing to the right tool.

    Args:
        request_str: The natural language question from the user.
    """
    raw = llm.call(_build_tools_prompt(), request_str, model=cfg.llm_models.mcp)
    decision = json.loads(raw["content"])
    tool_name = decision.get("tool")
    if not tool_name:
        return f"No Tool : {decision.get('reason', '')}"
    fn = globals().get(tool_name)
    if not (fn and inspect.isfunction(fn) and fn.__module__ == __name__):
        return f"Unknown Tool : {tool_name}"
    sig = inspect.signature(fn)
    args = {
        k: int(v) if sig.parameters[k].annotation is int else v
        for k, v in (decision.get("arguments") or {}).items()
        if k in sig.parameters
    }
    return _synthesize(request_str, str(fn(**args)))