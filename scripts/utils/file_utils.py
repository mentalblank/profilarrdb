import shutil
import os
from pathlib import Path

def clear_output_dirs(dirs):
    """Clear and recreate output directories."""
    for d in dirs:
        if d.exists():
            print(f"Cleaning {d}...")
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()
