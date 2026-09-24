import json
import logging
import os
import re
from datetime import datetime

from common.conf_manager import cfg

logger = logging.getLogger(__name__)


class ListStorage:
    """
    Handles reading and writing list files on disk as JSON.

    Operates as follows:
        1. Resolves the data directory from cfg.BASE_DIR.
        2. Builds file paths from subject and type using a slug convention.
        3. Provides read/write helpers with timestamp management.
        4. Never deletes files; write() only creates or updates.

    Methods:
        __init__(self) : Initializes the storage with the configured data directory.
        get_data_dir(self) : Returns the resolved data directory path, creating it if needed.
        slugify(self, text) : Converts text into a filesystem-safe slug.
        build_filename(self, subject, list_type) : Builds the filename for a given subject and type.
        list_files(self) : Returns metadata for all existing list files.
        find(self, subject) : Returns the filepath matching a given subject, regardless of type.
        read(self, filepath) : Reads and returns the JSON content of a list file.
        write(self, filepath, data) : Writes JSON content to a list file, updating timestamps.
        exists(self, subject, list_type) : Checks whether a list file already exists.

    Usage:
        storage = ListStorage()
        data = storage.read(path)
        storage.write(path, data)
    """

    def __init__(self):
        self._data_dir = os.path.join(cfg.config_dir, "data")

    def get_data_dir(self):
        if not os.path.isdir(self._data_dir):
            os.makedirs(self._data_dir, exist_ok=True)
        return self._data_dir

    def slugify(self, text):
        slug = text.strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug or "untitled"

    def build_filename(self, subject, list_type):
        slug = self.slugify(subject)
        filename = "{0}_{1}.json".format(list_type, slug)
        return os.path.join(self.get_data_dir(), filename)

    def list_files(self):
        results = []
        data_dir = self.get_data_dir()
        try:
            for name in os.listdir(data_dir):
                if not name.endswith(".json"):
                    continue
                filepath = os.path.join(data_dir, name)
                data = self.read(filepath)
                if data is None:
                    continue
                results.append(
                    {
                        "subject": data.get("subject"),
                        "type": data.get("type"),
                        "description": data.get("description"),
                        "path": filepath,
                    }
                )
        except Exception as exc:
            logger.error("Failed to list files in %s: %s", data_dir, exc)
        return results

    def find(self, subject):
        target_slug = self.slugify(subject)
        data_dir = self.get_data_dir()
        try:
            for name in os.listdir(data_dir):
                if not name.endswith(".json"):
                    continue
                if name.endswith("_{0}.json".format(target_slug)):
                    return os.path.join(data_dir, name)
        except Exception as exc:
            logger.error("Failed to search for subject '%s': %s", subject, exc)
        return None

    def read(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Failed to read file '%s': %s", filepath, exc)
            return None

    def write(self, filepath, data):
        now = datetime.now().isoformat()
        if not os.path.exists(filepath):
            data.setdefault("created_at", now)
        data["updated_at"] = now
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as exc:
            logger.error("Failed to write file '%s': %s", filepath, exc)
            return False

    def exists(self, subject, list_type):
        filepath = self.build_filename(subject, list_type)
        return os.path.exists(filepath)

