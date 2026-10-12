from common.conf_manager import cfg, setup_logging, Utils
from common.llm_client import llm
from datetime import datetime
import json

import logging
logger = logging.getLogger(__name__)

TEST_CASES = [
    ("Allume toutes les lumières.", "ask_control_multiroom"),
    ("Envoie un message sur Discord : Je vais aller à la gare.", "ask_send_msg"),
    ("Diffuse mon message : je vais aller à la gare.", "ask_send_msg"),
    ("Dans 2 minutes, envoie moi un message que je dois aller acheter du pain.", "ask_send_msg"),
    ("Éteins toutes les lumières.", "ask_control_multiroom"),
]

def ask_create_task(request_str: str) -> str:
    """Schedule a future action (time ref + action to run). Use this in priority for anything time-based."""
    from mcp_dynamic_server import resolve

    logger.info(f"ask_create_task: {request_str}")
    now = datetime.now()
    system_prompt = (
        f"Current datetime: {now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"({now.strftime('%A')})\n\n"
        + cfg.agents.common_create_task
    )
    local_res = llm.call(system_prompt, request_str, model=cfg.llm_models.mcp)
    try:
        decision = json.loads(local_res["content"])
    except (json.JSONDecodeError, KeyError):
        return f"LLM returned invalid JSON: {local_res.get('content', '')[:200]}"

    tool_name = decision.get("tool")
    if not tool_name:
        return f"No Tool : {decision.get('reason', '')}"

    task_name = (decision.get("task_name") or "task").strip()
    cleaned_request = (decision.get("cleaned_request") or "").strip()
    if not cleaned_request:
        return f"Missing cleaned_request: {decision}"
    resolved = resolve(cleaned_request)
    if "error" in resolved:
        return f"Cannot resolve '{cleaned_request}': {resolved['error']}"

    target_function = "dllb-skill." + resolved["function"].split(".")[-1]
    target_args = list(resolved["args"].values())
    logger.debug(f"ask_create_task: tool={tool_name}, task_name={task_name}, function={target_function}, args={target_args}")
    if tool_name == "add_oneshot_task":
        run_date = decision.get("run_date")
        if not run_date:
            return f"Missing run_date: {decision}"
        Utils.add_oneshot_task(
            task_id=task_name,
            function=target_function,
            date_or_timestamp=run_date,
            description=request_str,
            args=target_args,
            hidden="yes",
        )
        return f"One-shot task '{task_name}' scheduled at {run_date}: {target_function}{tuple(target_args)}"

    if tool_name == "add_cron_task":
        cron = decision.get("cron")
        if not cron:
            return f"Missing cron: {decision}"
        Utils.add_cron_task(
            task_id=task_name,
            function=target_function,
            cron_param=cron,
            description=request_str,
            args=target_args,
            hidden="no",
        )
        return f"Cron task '{task_name}' scheduled with '{cron}': {target_function}{tuple(target_args)}"
    return f"Unknown tool: {tool_name}"

def ask_control_multiroom(request_str: str) -> str:
    """
    Control the smart home and multiroom audio: lights, switches, plugs, thermostats (turn on/off, dim, set temperature)
    in any room, plus speakers and music playback (play, pause, volume, per room).
    """
    logger.info(f"ask_control_multiroom: {request_str}")
    return f'{Utils.send_command_multiroom(request_str)}'

def ask_send_msg(request_str: str) -> str:
    """Send, diffuse, relay or schedule a text message to Discord or house speakers, future time means schedule it."""
    function_name = "dllb-skill.send_announcement"
    if 'discord' in request_str.lower():
        function_name = "dllb-skill.send_msg_discord"

    now = datetime.now()
    system_prompt = f"Current datetime: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n" + cfg.agents.common_relay_message
    local_res = llm.call(system_prompt, request_str, model=cfg.llm_models.mcp)
    try:
        decision = json.loads(local_res["content"])
        action = decision.get("send") or decision.get("send_now") or decision.get("tool")
        message = (decision.get("message") or "").strip()
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON response: {local_res['content']}")
        action = 'send_now'
        message = request_str.strip()
    if not action:
        return f"No action: {decision}"

    logger.info(f"ask_send_msg: action={action}, message={message}, function={function_name}")
    if action in ("send_now", "now", "now_now"):
        if 'discord' in request_str.lower():
            send_msg_discord(message)
        else:
            send_announcement(message)
        return f"Sent: {message}"

    if action == "add_oneshot_task":
        Utils.add_oneshot_task(
            task_id=f"msg_{now.strftime('%H%M%S')}",
            function=function_name,
            date_or_timestamp=decision.get("run_date"),
            args=[message],
            hidden="yes",
        )
        return f"Scheduled: {message} at {decision.get('run_date')}"
    return f"No action: {decision}"

def shutdown_server(request_str: str) -> str:
    if isinstance(llm, LLMGatewayClient) :
        return llm._send_wol()
    return "Impossible to shutdown the server from this instance. Please configure LLM Gateway client."

def restart_service(request_str: str) -> str:
    """Restart a service."""
    return "" # Utils.shutdown_server(request_str)

def send_announcement(request_str: str) -> str:
    """Send an announcement message in a room."""
    return Utils.play_text_announcement(request_str)

def send_msg_discord(request_str: str) -> str:
    """Send a message to a Discord channel."""
    return Utils.send_discord_notification(request_str, 'notify-me')

def TU_common():
    results = []
    for label, req in TEST_CASES:
        logger.info(f"=== {label} ===> {req}")
        try:
            out = ask_common(req)
        except Exception:
            logger.exception("ask_agenda crashed")
            continue
        if out:
            results.append(f"{label}: {out if len(out) < 600 else out[:600] + ' ... [truncated]'}")
            logger.info(out if len(out) < 600 else out[:600] + " ... [truncated]")
    return "\n".join(results)
