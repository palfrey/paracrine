import shutil
from typing import Dict, Union, cast

options: Dict[str, object] = {}

MIN_DISK_FREE_KEY = "MIN_DISK_FREE"


# Example usage: (diskfree, {diskfree.MIN_DISK_FREE_KEY: 10})
def run():
    MIN_DISK_FREE = cast(Union[float, int], options.get(MIN_DISK_FREE_KEY, 10))
    disk_info = shutil.disk_usage("/")
    disk_free_percent = (disk_info.free * 1.0) / (disk_info.total / 100.0)
    if disk_free_percent < MIN_DISK_FREE:
        raise Exception(
            f"Disk free percent needs to be at least {MIN_DISK_FREE}, but it's {disk_free_percent}"
        )
