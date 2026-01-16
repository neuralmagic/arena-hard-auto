import os
import json
import yaml

from pathlib import Path

# Directory of the current package
package_dir = os.path.dirname(__file__)

# Dictionaries to hold the loaded YAMLs and directories
yamls = {}
directories = {}

# Loop through files in the package directory
for fname in os.listdir(package_dir):
    if fname.endswith('.yaml') or fname.endswith('.yml'):
        full_path = os.path.join(package_dir, fname)
        directories["arenahard_config_path"] = str(Path(full_path).parents[0])
        with open(full_path, 'r') as f:
            yamls[fname] = yaml.safe_load(f)

# Expose YAMLs and directories dictionaries to package imports
__all__ = ['yamls', 'directories']
