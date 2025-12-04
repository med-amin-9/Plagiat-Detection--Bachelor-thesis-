# This script generates a TOML configuration file for the exercise_tester.
# It scans all directories inside the specified base path, treats each as a local repository,
# and writes their paths into a config file called "exercise-tester.toml".
# The config includes the list of repositories, a working directory, and a simulation flag.
from pathlib import Path
import toml, os

base = Path(r"\exercise-tester\gdi-ue1")
repos = [f"local://{p.as_posix()}" for p in base.iterdir() if p.is_dir()]
cfg = {
    "general": {
        "repositories": repos,
        "directory": (base / "workdir").as_posix(),
        "simulate": False
    }
}
toml.dump(cfg, open("exercise-tester.toml", "w"))
print(f"Wrote {len(repos)} repositories to local_windows.toml")