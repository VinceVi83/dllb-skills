from common.conf_manager import cfg, setup_logging, Utils
from common.llm_client import llm
import logging
logger = logging.getLogger(__name__)

TEST_CASES = [
    ("Allume toutes les lumières.", "ask_control_multiroom"),
    ("Envoie un message sur Discord : je vais faire les courses.", "ask_announcement"),
    ("Diffuse mon message : je vais faire les courses.", "ask_announcement"),
    ("Éteins toutes les lumières.", "ask_control_multiroom"),
]

def ask_create_task(request_str: str) -> str:
    """Create a one-shot or recurring task that will re-call ask later."""
    logger.info(f"ask_create_task: {request_str}")
    now = datetime.now()
    system_prompt = (
        f"Current datetime: {now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"({now.strftime('%A')})\n\n"
        + _build_tools_prompt()
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

    args = [cleaned_request]

    if tool_name == "add_oneshot_task":
        run_date = decision.get("run_date")
        if not run_date:
            return f"Missing run_date: {decision}"
        Utils.add_oneshot_task(
            task_id=task_name,
            function="dllb_skills.call_ask",
            date_or_timestamp=run_date,
            description=request_str,
            args=args,
            hidden="yes",
        )
        return f"One-shot task '{task_name}' scheduled at {run_date}"

    if tool_name == "add_cron_task":
        cron = decision.get("cron")
        if not cron:
            return f"Missing cron: {decision}"
        Utils.add_cron_task(
            task_id=task_name,
            function="dllb_skills.call_ask",
            cron_param=cron,
            description=request_str,
            args=args,
            hidden="no",
        )
        return f"Cron task '{task_name}' scheduled with '{cron}'"

    return f"Unknown tool: {tool_name}"

def ask_control_multiroom(request_str: str) -> str:
    """
    Control the smart home and multiroom audio: lights, switches, plugs, thermostats (turn on/off, dim, set temperature)
    in any room, plus speakers and music playback (play, pause, volume, per room).
    """
    logger.info(f"ask_control_multiroom: {request_str}")
    return f'{Utils.send_command_multiroom(request_str)}'

def ask_send_msg(request_str: str) -> str:
    """Send or broadcast a message: announce a text message on the house speakers or notify the user."""
    logger.info(f"ask_send_msg: {request_str}")
    function = dllb_skills.send_announcement
    if 'discord' in request_str.lower():
        function = dllb_skills.send_msg_discord
    now = datetime.now()
    system_prompt = f"Current datetime: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n" + _build_send_msg_prompt()
    local_res = llm.call(system_prompt, request_str, model=cfg.llm_models.mcp)
    decision = json.loads(local_res["content"])
    action = decision.get("send")
    message = (decision.get("message") or "").strip()

    if action == "send_now":
        if 'discord' in request_str.lower():
            send_msg_discord(message)
        else:
            send_announcement(message)
        return f"Sent: {message}"
    if action == "add_oneshot_task":
        Utils.add_oneshot_task(
            task_id=f"msg_{now.strftime('%H%M%S')}",
            function=function,
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