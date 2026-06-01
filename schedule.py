from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

scheduler = BackgroundScheduler()
scheduler.start()

def daily_task():
    print(f"[{datetime.now()}] The task is running!")


job_params = {k: v for k, v in vars(task).items() if k not in ['func', 'id']}
scheduler.add_job(
    func,                # La fonction récupérée via le registre
    id=task.id,          # L'identifiant unique
    **job_params         # Ce qui devient : trigger='cron', hour=6, minute=0
)

def modify_schedule_via_chatbot(new_hour: int, new_minute: int):
    try:
        scheduler.reschedule_job(
            job_id,
            trigger='cron',
            **new_time_params
        )
        return f"Perfect! The task has been rescheduled to {new_hour:02d}h{new_minute:02d}."
    except Exception as e:
        return f"Error during modification: {e}"

def get_injected_prompt(template_name):
    template = getattr(cfg.agents, template_name, "")
    
    available_ids = [task.id for task in cfg.scheduler_tasks]
    ids_str = ", ".join([f"`{id}`" for id in available_ids])
    
    return template.replace("{{IDS_LIST}}", ids_str)

final_prompt = get_injected_prompt("reschedule_template")
