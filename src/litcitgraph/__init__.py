from typing import Final
import sys
import time
import logging
from pathlib import Path
import tomllib

__all__ = [
    'GRPHSTRY_PERS_ID',
    'GRPHSTRY_PERS_KEY',
]

logging.Formatter.converter = time.gmtime
LOG_FMT: Final[str] = '%(module)s:%(levelname)s | %(asctime)s | %(message)s'
LOG_DATE_FMT: Final[str] = '%Y-%m-%d %H:%M:%S +0000'
logging.basicConfig(
    stream=sys.stdout,
    format=LOG_FMT,
    datefmt=LOG_DATE_FMT,
)

USE_CONFIG: Final[bool] = False

if USE_CONFIG:
    package_directory = Path(__file__).parent
    config_path = package_directory / 'keys.toml'

    with open(config_path, 'rb') as config_file:
        config = tomllib.load(config_file)

    # ** Graphistry
    GRPHSTRY_PERS_ID: Final[str] = config['graphistry']['personal_key_id']
    GRPHSTRY_PERS_KEY: Final[str] = config['graphistry']['personal_secret_key']
