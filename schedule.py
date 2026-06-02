from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import inspect
from typing import Callable, List, Dict, Any, Optional

scheduler = BackgroundScheduler()
scheduler.start()

class TaskManager:
    """Gestionnaire de tâches planifiées avec support des arguments et templates"""
    
    @staticmethod
    def planifier_tache(task_config: Dict[str, Any]) -> str:
        """
        Planifie une nouvelle tâche avec gestion des arguments
        
        Args:
            task_config: Configuration de la tâche avec:
                - id: identifiant unique
                - func: fonction ou chemin vers fonction
                - trigger: type de déclenchement (cron, interval, etc.)
                - [paramètres spécifiques au trigger]
                - args: arguments positionnels (optionnel)
                - kwargs: arguments nommés (optionnel)
        """
        try:
            job_params = {k: v for k, v in task_config.items()
                        if k not in ['id', 'func', 'args', 'kwargs']}

            func = TaskManager._get_function(task_config['func'])

            args = task_config.get('args', [])
            kwargs = task_config.get('kwargs', {})
            scheduler.add_job(
                func,
                id=task_config['id'],
                args=args,
                kwargs=kwargs,
                **job_params
            )
            
            return f"Tâche {task_config['id']} planifiée avec succès"
            
        except Exception as e:
            return f"Erreur lors de la planification: {str(e)}"
    
    @staticmethod
    def modifier_tache(job_id: str, **modifications) -> str:
        """
        Modifie une tâche existante (horaire et/ou arguments)
        
        Args:
            job_id: ID de la tâche à modifier
            **modifications: Nouveaux paramètres (hour, minute, args, kwargs, etc.)
        """
        try:
            job = scheduler.get_job(job_id)
            if not job:
                return f"Erreur: Tâche {job_id} non trouvée"
            
            reschedule_params = {}
            
            if 'trigger' in modifications:
                reschedule_params['trigger'] = modifications['trigger']
            if 'hour' in modifications:
                reschedule_params['hour'] = modifications['hour']
            if 'minute' in modifications:
                reschedule_params['minute'] = modifications['minute']
            if 'day_of_week' in modifications:
                reschedule_params['day_of_week'] = modifications['day_of_week']
            
            if 'args' in modifications:
                reschedule_params['args'] = modifications['args']
            if 'kwargs' in modifications:
                reschedule_params['kwargs'] = modifications['kwargs']
            
            if reschedule_params:
                scheduler.reschedule_job(job_id=job_id, **reschedule_params)
            
            return f"Tâche {job_id} mise à jour avec succès"
            
        except Exception as e:
            return f"Erreur lors de la modification: {str(e)}"
    
    @staticmethod
    def lister_taches() -> List[Dict[str, Any]]:
        return [{
            'id': job.id,
            'next_run': job.next_run_time,
            'func': job.func.__name__ if hasattr(job.func, '__name__') else str(job.func)
        } for job in scheduler.get_jobs()]
    
    @staticmethod
    def supprimer_tache(job_id: str) -> str:
        try:
            scheduler.remove_job(job_id)
            return f"Tâche {job_id} supprimée"
        except Exception as e:
            return f"Erreur lors de la suppression: {str(e)}"
    
    @staticmethod
    def _get_function(func_path: str) -> Callable:
        if callable(func_path):
            return func_path
        
        try:
            module_path, func_name = func_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[func_name])
            return getattr(module, func_name)
        except Exception as e:
            raise ImportError(f"Impossible d'importer {func_path}: {str(e)}")

class TaskTemplates:
    """Templates pour les prompts et configurations de tâches"""
    
    RESCHEDULE_TEMPLATE = """
    Tâches disponibles pour modification: {{IDS_LIST}}
    
    Pour modifier une tâche, utilisez la commande:
    /reschedule <id_tache> <heure> <minute> [args...]
    
    Exemples:
    - /reschedule job_chatbot_semaine 9 0
    - /reschedule job_backup 23 30 args="backup complet" priority=high
    """
    
    LIST_TEMPLATE = """
    Tâches planifiées actives:
    {{TASKS_LIST}}
    """
    
    ADD_TEMPLATE = """
    Pour ajouter une nouvelle tâche, utilisez:
    /add_task <id> <func_path> <trigger> [params...]
    
    Exemples:
    - /add_task job_rappel schedule.ma_tache_quotidienne cron hour=8 minute=30
    - /add_task job_backup backup.run_backup cron hour=2 day_of_week=mon-fri args=["full"]
    """
    
    @staticmethod
    def get_injected_prompt(template_name: str, **context) -> str:
        """Génère un prompt avec injection de variables"""
        template = getattr(TaskTemplates, template_name, "")
        
        for var, value in context.items():
            template = template.replace(f"{{{{{var}}}}}", str(value))
        
        return template

def ma_tache_quotidienne():
    print(f"[{datetime.now()}] Tâche quotidienne exécutée")

def ma_tache_avec_args(message: str, priorite: str = 'normale'):
    print(f"[{datetime.now()}] Tâche avec args:")
    print(f"  Message: {message}")
    print(f"  Priorité: {priorite}")

"""
Exemple de configuration YAML pour scheduler_tasks:

scheduler_tasks:
  - id: "job_chatbot_semaine"
    func: "schedule.ma_tache_avec_args"  # Chemin vers la fonction
    trigger: "cron"
    day_of_week: "mon-fri"
    hour: 8
    minute: 30
    args:  # Arguments positionnels
      - "Rappel quotidien"
    kwargs:  # Arguments nommés
      priorite: "haute"
      destinataire: "equipe"

  - id: "job_backup_quotidien"
    func: "backup.run_backup"
    trigger: "cron"
    hour: 2
    minute: 0
    args:
      - "incremental"
    kwargs:
      compression: true
      destination: "/backups"
"""

def get_reschedule_prompt():
    available_ids = [job.id for job in scheduler.get_jobs()]
    ids_str = ", ".join([f"`{id}`" for id in available_ids])
    
    return TaskTemplates.get_injected_prompt(
        "RESCHEDULE_TEMPLATE",
        IDS_LIST=ids_str
    )

def get_list_prompt():
    tasks = TaskManager.lister_taches()
    tasks_str = "\n".join([
        f"- {task['id']}: {task['func']} (prochaine exécution: {task['next_run']})"
        for task in tasks
    ])
    
    return TaskTemplates.get_injected_prompt(
        "LIST_TEMPLATE",
        TASKS_LIST=tasks_str or "Aucune tâche planifiée"
    )

if __name__ == "__main__":
    tache_config = {
        "id": "job_chatbot_semaine",
        "func": ma_tache_avec_args,
        "trigger": "cron",
        "day_of_week": "mon-fri",
        "hour": 8,
        "minute": 30,
        "args": ["Message important"],
        "kwargs": {
            "priorite": "haute"
        }
    }
    
    result = TaskManager.planifier_tache(tache_config)
    print(result)
    
    print("\n" + get_reschedule_prompt())
    
    print("\n" + get_list_prompt())