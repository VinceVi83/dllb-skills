import json
import logging
import re
from datetime import datetime

from common.conf_manager import cfg
from common.llm_client import llm

from skills.smartlists.storage import ListStorage

logger = logging.getLogger(__name__)


class ListManager:
    """
    Manages smart lists (todo, achat, brainstorming) backed by JSON files,
    using unitary LLM calls for addition and summarization.

    Operates as follows:
        1. Delegates file I/O to ListStorage.
        2. Builds natural-language user prompts for each LLM interaction.
        3. Extracts and parses JSON from LLM responses defensively, stripping
           markdown code fences if present.
        4. Normalizes each item so it always has "content", "done" and
           "updated_at". "updated_at" is refreshed only when content or
           done status actually changes compared to the previous version.
        5. Never deletes or overwrites existing lists on create.

    Methods:
        get_listsubject(self) : Returns metadata for all existing lists.
        create_list(self, subject, list_type, description) : Creates a new list file if it does not already exist.
        add_new_element(self, subject, element) : Adds a new element to an existing list via LLM update.
        summary(self, subject, user_request) : Returns a natural-language summary of a list via LLM.
        brut_data(self, subject) : Returns the raw JSON content of a list.

    Usage:
        manager = ListManager()
        manager.create_list("Maison", "todo", "Weekly chores")
        manager.add_new_element("Maison", "I need to buy milk")
        manager.summary("Maison", "What do I still need to do?")
    """

    def __init__(self):
        self._storage = ListStorage()

    def _call_llm(self, system_prompt, user_prompt):
        try:
            raw_result = llm.call(system_prompt, user_prompt, model='ministral-3:14b',mode='summarize')
        except Exception as exc:
            logger.error("LLM call raised an exception: %s", exc)
            return None

        if not raw_result:
            logger.error("LLM call returned empty result")
            return None

        parsed = raw_result
        if isinstance(raw_result, str):
            try:
                parsed = json.loads(raw_result)
            except Exception as exc:
                logger.error("Failed to parse raw LLM result as JSON: %s", exc)
                return None

        if isinstance(parsed, dict) and "content" in parsed:
            return parsed["content"]

        logger.error("LLM result missing 'content' key: %s", parsed)
        return None

    def _extract_json_block(self, text):
        if text is None:
            return None

        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.error("No JSON object found in LLM content")
            return None
        try:
            return json.loads(match.group(0))
        except Exception as exc:
            logger.error("Failed to parse extracted JSON block: %s", exc)
            return None

    def _normalize_items(self, previous_items, new_items):
        now = datetime.now().isoformat()

        previous_by_content = {}
        for prev_item in previous_items or []:
            key = prev_item.get("content")
            if key is not None:
                previous_by_content[key] = prev_item

        normalized = []
        for item in new_items or []:
            content = item.get("content")
            done = bool(item.get("done", False))

            prev_item = previous_by_content.get(content)

            if prev_item is not None:
                prev_done = bool(prev_item.get("done", False))
                if prev_done != done:
                    updated_at = now
                else:
                    updated_at = prev_item.get("updated_at", now)
            else:
                updated_at = now

            normalized.append(
                {
                    "content": content,
                    "done": done,
                    "updated_at": updated_at,
                }
            )

        return normalized

    def get_listsubject(self):
        return self._storage.list_files()

    def create_list(self, subject, list_type, description):
        if self._storage.exists(subject, list_type):
            logger.error(
                "List already exists for subject '%s' and type '%s'; not overwriting",
                subject,
                list_type,
            )
            return None

        filepath = self._storage.build_filename(subject, list_type)
        data = {
            "subject": subject,
            "type": list_type,
            "description": description,
            "items": [],
        }
        self._storage.write(filepath, data)
        return filepath

    def add_new_element(self, subject, element):
        filepath = self._storage.find(subject)
        if filepath is None:
            logger.error("No list found for subject '%s'", subject)
            return None

        current_data = self._storage.read(filepath)
        if current_data is None:
            logger.error("Failed to read current list for subject '%s'", subject)
            return None

        system_prompt = cfg.agents.smartlists_add
        user_prompt = (
            "Here is the current list in JSON format:\n"
            "{0}\n\n"
            "Please add or merge the following new request into the list: \"{1}\". "
            "Avoid duplicates, improve or synthesize similar existing items if relevant. "
            "Return the complete updated list as a single JSON object, "
            "with no explanation, no markdown, and no text before or after the JSON."
        ).format(json.dumps(current_data, ensure_ascii=False), element)

        content = self._call_llm(system_prompt, user_prompt)
        updated_data = self._extract_json_block(content)

        if updated_data is None:
            logger.error("Failed to parse updated list for subject '%s'", subject)
            return None

        updated_data.setdefault("subject", current_data.get("subject", subject))
        updated_data.setdefault("type", current_data.get("type"))
        updated_data.setdefault("description", current_data.get("description"))

        updated_data["items"] = self._normalize_items(
            current_data.get("items", []),
            updated_data.get("items", []),
        )

        self._storage.write(filepath, updated_data)
        
        # Retourner les nouveaux items ajoutés/modifiés
        return updated_data.get("items", [])

    def summary(self, subject, user_request):
        filepath = self._storage.find(subject)
        if filepath is None:
            logger.error("No list found for subject '%s'", subject)
            return None

        data = self._storage.read(filepath)
        if data is None:
            logger.error("Failed to read list for subject '%s'", subject)
            return None

        system_prompt = cfg.agents.smartlists_summary
        user_prompt = (
            "Here is the list in JSON format:\n{0}\n\n"
            "Answer the following user request based only on this list, "
            "in natural language: \"{1}\""
        ).format(json.dumps(data, ensure_ascii=False), user_request)

        content = self._call_llm(system_prompt, user_prompt)
        if content is None:
            logger.error("Failed to generate summary for subject '%s'", subject)
            return None
        return content

    def brut_data(self, subject):
        filepath = self._storage.find(subject)
        if filepath is None:
            logger.error("No list found for subject '%s'", subject)
            return None
        return self._storage.read(filepath)

