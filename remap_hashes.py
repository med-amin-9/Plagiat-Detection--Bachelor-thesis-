import json, hashlib, toml
from pathlib import Path
from glob import glob

# === Setup ===
#TOML_FILE = "exercise-tester.toml"
TOML_FILE = "cpp_test_config.toml"
#TOML_FILE = "python_test_config.toml"

RESULT_FILE = str(max(map(Path, glob("plagiarism_results*.json")), key=lambda p: p.stat().st_mtime))
OUTPUT_FILE = RESULT_FILE.replace(".json", "_remapped.json")

# === Build hash → folder map ===
cfg = toml.load(TOML_FILE)
mapping = {}

for repo_url in cfg["general"]["repositories"]:
    if repo_url.startswith("local://"):
        folder_path = repo_url.replace("local://", "")
        folder_name = Path(folder_path).name
        hash_id = hashlib.md5(folder_path.encode()).hexdigest()
        mapping[hash_id] = folder_name

# === Load and transform results ===
with open(RESULT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

remapped = []

for record in data:
    id1, file1 = record["file_1"].split("/", 1)
    id2, file2 = record["file_2"].split("/", 1)
    remapped.append({
        mapping.get(id1, id1): record["file_1"],
        mapping.get(id2, id2): record["file_2"],
        "similarity": record["similarity"]
    })

# === Save new JSON ===
with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    json.dump(remapped, out, indent=2)
    print(f"Saved remapped results to {OUTPUT_FILE}")
