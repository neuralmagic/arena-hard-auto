import os
import json
import yaml
import glob
from pathlib import Path

# Directory of the current package
package_dir = os.path.dirname(__file__)

# Dictionaries to hold the loaded JSONLs and directories
jsonls = {}
directories = {"package_dir": package_dir }

# Loop through files in the package directory
for fname in glob.glob(os.path.join(package_dir,"**/*.jsonl"), recursive=True):
    full_path = os.path.join(package_dir, fname)
    if "question" in fname:
        directories["question_dir"] = str(Path(full_path).parents[0])
        jsonls["question_path"] = full_path
    if "answer" in fname:
        directories["answer_dir"] = str(Path(full_path).parents[0])
        jsonls["answer_path"] = full_path
    if "judgment" in fname:
        directories["judgment_dir"] = str(Path(full_path).parents[0])
        jsonls["judgment_path"] = full_path

# Expose JSONLs and directories dictionaries to package imports
__all__ = ['jsonls', 'directories']
