from ...helpers.config import other_config_file
from ...helpers.fs import delete
from .common import MASTER_FILE


def run():
    pass


def parse_return(infos: object) -> None:
    delete(other_config_file(MASTER_FILE), True)
