import logging
import os
import shutil
from skills.smartlists.list_manager import ListManager

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def print_section(title):
    logger.info(f"\n{'='*60}")
    logger.info(f"  {title}")
    logger.info(f"{'='*60}\n")

def test_todo_list():
    print_section("TODO LIST: Maison")

    manager = ListManager()
    data_dir = manager._storage.get_data_dir()
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
        os.makedirs(data_dir)

    logger.info("Creating Todo list...\n")
    filepath = manager.create_list("Maison", "todo", "Weekly chores")
    logger.info(f"✓ Created: {filepath}\n")

    logger.info("Adding tasks:\n")
    requests = [
        "I need to go shopping, so I should buy some milk",
        "The plumber needs to be called, maybe tomorrow would be good",
        "The kitchen is a mess, I really should clean it up before the weekend",
    ]
    for req in requests:
        result = manager.add_new_element("Maison", req)
        count = len(result) if result else 0
        logger.info(f"  + '{req[:45]}...' → {count} item(s) in list\n")

    logger.info("Marking first task as done...\n")
    raw = manager.brut_data("Maison")
    if raw.get("items"):
        raw["items"][0]["done"] = True
        manager._storage.write(filepath, raw)
        logger.info(f"✓ Marked '{raw['items'][0]['content']}' as done\n")

    logger.info("Current list:\n")
    raw = manager.brut_data("Maison")
    for item in raw.get("items", []):
        status = "✓" if item.get("done") else "○"
        logger.info(f"  {status} {item.get('content')}")
    logger.info("")

    logger.info("Deleting a task...\n")
    delete_req = "Actually, I don't need to clean the kitchen anymore"
    result = manager.add_new_element("Maison", delete_req)
    count = len(result) if result else 0
    logger.info(f"✓ Removed task → {count} item(s) remaining\n")

    logger.info("Updated list:\n")
    raw = manager.brut_data("Maison")
    for item in raw.get("items", []):
        status = "✓" if item.get("done") else "○"
        logger.info(f"  {status} {item.get('content')}")
    logger.info("")

    logger.info("Summary requests:\n")
    summaries = [
        ("So what am I supposed to be doing right now?", "List pending tasks"),
        ("Have I managed to finish anything yet?", "Check completed tasks"),
        ("Give me a quick overview of everything", "Overview of all"),
    ]
    for query, expected in summaries:
        result = manager.summary("Maison", query)
        logger.info(f"Q: {query}")
        logger.info(f"A: {result}")
        logger.info(f"✓ Expected: {expected}\n")


def test_brainstorming():
    print_section("BRAINSTORMING: SmartLists Project")
    
    manager = ListManager()
    
    logger.info("Creating Brainstorming list...\n")
    filepath = manager.create_list("SmartLists Project", "brainstorming", 
                                    "Ideas for the smart lists CLI application")
    logger.info(f"✓ Created: {filepath}\n")
    
    ideas = [
        "It would be really cool if multiple users could access the same lists, maybe with different permission levels",
        "What if we could export everything to a nice PDF or maybe a spreadsheet format?",
        "Cloud synchronization would be awesome, maybe with some encryption for privacy",
        "I think a mobile app that sends notifications would really improve the experience",
        "Users should be able to customize the interface, maybe with a dark mode option",
    ]
    
    logger.info("Adding ideas:\n")
    for idea in ideas:
        result = manager.add_new_element("SmartLists Project", idea)
        count = len(result) if result else 0
        logger.info(f"  + '{idea[:50]}...' → {count} idea(s) in list\n")
    
    logger.info("Current brainstorm:\n")
    raw = manager.brut_data("SmartLists Project")
    for i, item in enumerate(raw.get("items", []), 1):
        logger.info(f"  {i}. {item.get('content')}")
    logger.info("")
    
    logger.info("Summary requests:\n")
    summaries = [
        ("So what ideas have we come up with so far?", "List all ideas"),
        ("Which features do you think would have the biggest impact?", "Prioritize by impact"),
    ]
    
    for query, expected in summaries:
        result = manager.summary("SmartLists Project", query)
        logger.info(f"Q: {query}")
        logger.info(f"A: {result}")
        logger.info(f"✓ Expected: {expected}\n")

if __name__ == "__main__":
    test_todo_list()
    test_brainstorming()
    logger.info(f"\n{'='*60}\nAll tests completed!\n{'='*60}\n")

