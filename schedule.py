from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

scheduler = BackgroundScheduler()
scheduler.start()

def ma_tache_quotidienne():
    print(f"[{datetime.now()}] La tâche s'exécute !")


job_params = {k: v for k, v in vars(task).items() if k not in ['func', 'id']}
scheduler.add_job(
    func,                # La fonction récupérée via le registre
    id=task.id,          # L'identifiant unique
    **job_params         # Ce qui devient : trigger='cron', hour=6, minute=0
)

def modifier_horaire_via_chatbot(nouvelle_heure: int, nouvelle_minute: int):
    """
    Cette fonction sera appelée par ton chatbot lorsqu'un utilisateur
    demande de changer l'heure.
    """
    try:
        # On modifie le déclencheur de la tâche existante grâce à son ID
        scheduler.reschedule_job(
            job_id,
            trigger='cron',
            **new_time_params
        )
        return f"Parfait ! La tâche a été reprogrammée à {nouvelle_heure:02d}h{nouvelle_minute:02d}."
    except Exception as e:
        return f"Erreur lors de la modification : {e}"

def get_injected_prompt(template_name):
    template = getattr(cfg.agents, template_name, "")
    
    available_ids = [task.id for task in cfg.scheduler_tasks]
    ids_str = ", ".join([f"`{id}`" for id in available_ids])
    
    return template.replace("{{IDS_LIST}}", ids_str)

final_prompt = get_injected_prompt("reschedule_template")