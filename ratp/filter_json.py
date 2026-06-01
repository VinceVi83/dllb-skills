import json
import sys
import os
from rapidfuzz import fuzz

class JSONProcessor:
    def __init__(self, filepath):
        self.filepath = filepath
        self.data = self._load_json(filepath)
        self.pool = self._build_flat_list(self.data)
        self.current_page = 0
        self.page_size = 5
        self.last_key = "filter"
        self.last_value = "results"

    def _load_json(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)

    def _build_flat_list(self, node):
        flat = []
        if isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    flat.append(item)
                else:
                    flat.extend(self._build_flat_list(item))
        elif isinstance(node, dict):
            flat.append(node)
        return flat

    def get_skeleton(self, data):
        if isinstance(data, dict):
            return {k: self.get_skeleton(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.get_skeleton(data[0])] if data else []
        return data

    def display_page(self):
        total = len(self.pool)
        total_pages = (total + self.page_size - 1) // self.page_size
        start = self.current_page * self.page_size
        page_items = self.pool[start:start + self.page_size]

        print(f"\n--- POOL CONTENT: Page {self.current_page + 1}/{max(1, total_pages)} ({total} total) ---")
        print(json.dumps(page_items, indent=4, ensure_ascii=False))
        print("-" * 50)

    def filter_data(self, is_fuzz=False):
        key = input("Enter key to filter: ").strip()
        val = input(f"Enter {'approximated' if is_fuzz else 'exact'} value: ").strip()
        
        filtered = []
        occurrences = {}
        
        for item in self.pool:
            if key in item:
                item_val = str(item[key])
                match = (fuzz.partial_ratio(item_val.lower(), val.lower()) >= 70) if is_fuzz else (item_val.lower() == val.lower())
                
                if match:
                    filtered.append(item)
                    occurrences[item_val] = occurrences.get(item_val, 0) + 1
        
        print(f"\n-> Filter applied. Remaining: {len(filtered)}")
        for v, count in sorted(occurrences.items(), key=lambda x: x[1], reverse=True):
            print(f" - '{v}': {count} occurrences")
        
        input("\nPress Enter to continue...")
        self.pool = filtered
        self.last_key, self.last_value = key, val
        self.current_page = 0

    def export(self):
        if not self.pool:
            print("Pool is empty, nothing to export.")
            return False
        
        base = os.path.splitext(self.filepath)[0]
        safe_key = "".join(c for c in self.last_key if c.isalnum() or c in ('_', '-'))
        safe_val = "".join(c for c in self.last_value if c.isalnum() or c in ('_', '-'))
        out_path = f"{base}_extract_{safe_key}_{safe_val}.json"
        
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(self.pool, f, indent=4, ensure_ascii=False)
            print(f"\n[SUCCESS] Saved to: {out_path}")
            return True
        except Exception as e:
            print(f"Error writing file: {e}")
            return False

    def run(self):
        print("\n--- JSON STRUCTURE SKELETON ---")
        print(json.dumps(self.get_skeleton(self.data), indent=4, ensure_ascii=False))
        
        while True:
            self.display_page()
            print("Options: [1] Fuzz Filter | [2] Strict Filter | [n] Next | [p] Prev | [y] Export | [q] Quit")
            choice = input("Choice: ").strip().lower()

            if choice == 'q': break
            elif choice == 'n': self.current_page = min(self.current_page + 1, (len(self.pool) - 1) // self.page_size)
            elif choice == 'p': self.current_page = max(self.current_page - 1, 0)
            elif choice == '1': self.filter_data(is_fuzz=True)
            elif choice == '2': self.filter_data(is_fuzz=False)
            elif choice == 'y':
                if self.export(): break

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <file.json>")
    else:
        JSONProcessor(sys.argv[1]).run()