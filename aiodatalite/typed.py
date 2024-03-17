from typing import Dict, Optional


def _datalite_hinted_direct_use():
    raise ValueError(
        "Don't use DataliteHinted directly. Inherited classes should also be wrapped in "
        "datalite and dataclass decorators"
    )


class DataliteHinted:
    db_path: str
    types_table: Dict[Optional[type], str]
    tweaked: bool
    obj_id: int

    # noinspection PyMethodMayBeStatic
    async def markup_table(self):
        _datalite_hinted_direct_use()

    # noinspection PyMethodMayBeStatic
    async def create_entry(self):
        _datalite_hinted_direct_use()

    # noinspection PyMethodMayBeStatic
    async def update_entry(self):
        _datalite_hinted_direct_use()

    # noinspection PyMethodMayBeStatic
    async def remove_entry(self):
        _datalite_hinted_direct_use()


__all__ = ["DataliteHinted"]
