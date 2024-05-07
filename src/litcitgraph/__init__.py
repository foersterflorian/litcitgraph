from typing import Final
import sys
import logging
from pathlib import Path
import tomllib

__all__ = [
    'GRPHSTRY_PERS_ID',
    'GRPHSTRY_PERS_KEY',
]

logging.basicConfig(stream=sys.stdout)

package_directory = Path(__file__).parent
config_path = package_directory / 'keys.toml'

with open(config_path, 'rb') as config_file:
    config = tomllib.load(config_file)

# ** Graphistry
GRPHSTRY_PERS_ID: Final[str] = config['graphistry']['personal_key_id']
GRPHSTRY_PERS_KEY: Final[str] = config['graphistry']['personal_secret_key']