"""
Defines the Datalite decorator that can be used to convert a dataclass to
a class bound to an sqlite3 database.
"""
import sqlite3
from dataclasses import asdict, fields
from typing import Callable, Dict, Optional

import aiosqlite
from aiosqlite import IntegrityError

from .commons import (
    _create_table,
    _sync_create_table,
    _tweaked_create_table,
    _tweaked_dump,
    _tweaked_sync_create_table,
    type_table,
)
from .constraints import ConstraintFailedError


async def _create_entry(self) -> None:
    """
    Given an object, create the entry for the object. As a side effect,
    this will set the object_id attribute of the object to the unique
    id of the entry.
    :param self: Instance of the object.
    :return: None.
    """
    async with aiosqlite.connect(getattr(self, "db_path")) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        table_name: str = self.__class__.__name__.lower()
        kv_pairs = [item for item in asdict(self).items()]
        kv_pairs.sort(key=lambda item: item[0])  # Sort by the name of the fields.
        try:
            await cur.execute(
                f"INSERT INTO {table_name}("
                f"{', '.join(item[0] for item in kv_pairs)})"
                f" VALUES ({', '.join('?' for _ in kv_pairs)})",
                [item[1] for item in kv_pairs],
            )
            self.__setattr__("obj_id", cur.lastrowid)
            await con.commit()
        except IntegrityError:
            raise ConstraintFailedError("A constraint has failed.")
        finally:
            await cur.close()
            await con.close()


async def _tweaked_create_entry(self) -> None:
    async with aiosqlite.connect(getattr(self, "db_path")) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        table_name: str = self.__class__.__name__.lower()
        kv_pairs = [item for item in fields(self)]
        kv_pairs.sort(key=lambda item: item.name)  # Sort by the name of the fields.
        try:
            await cur.execute(
                f"INSERT INTO {table_name}("
                f"{', '.join(item.name for item in kv_pairs)})"
                f" VALUES ({', '.join('?' for _ in kv_pairs)})",
                [_tweaked_dump(self, item.name) for item in kv_pairs],
            )
            self.__setattr__("obj_id", cur.lastrowid)
            await con.commit()
        except IntegrityError:
            raise ConstraintFailedError("A constraint has failed.")
        finally:
            await cur.close()
            await con.close()


async def _update_entry(self) -> None:
    """
    Given an object, update the objects entry in the bound database.
    :param self: The object.
    :return: None.
    """
    async with aiosqlite.connect(getattr(self, "db_path")) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        table_name: str = self.__class__.__name__.lower()
        kv_pairs = [item for item in asdict(self).items()]
        kv_pairs.sort(key=lambda item: item[0])
        query = (
            f"UPDATE {table_name} "
            f"SET {', '.join(item[0] + ' = ?' for item in kv_pairs)} "
            f"WHERE obj_id = {getattr(self, 'obj_id')};"
        )
        await cur.execute(query, [item[1] for item in kv_pairs])
        await con.commit()


async def _tweaked_update_entry(self) -> None:
    async with aiosqlite.connect(getattr(self, "db_path")) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        table_name: str = self.__class__.__name__.lower()
        kv_pairs = [item for item in fields(self)]
        kv_pairs.sort(key=lambda item: item.name)
        query = (
            f"UPDATE {table_name} "
            f"SET {', '.join(item.name + ' = ?' for item in kv_pairs)} "
            f"WHERE obj_id = {getattr(self, 'obj_id')};"
        )
        await cur.execute(query, [_tweaked_dump(self, item.name) for item in kv_pairs])
        await con.commit()


async def remove_from(class_: type, obj_id: int):
    async with aiosqlite.connect(getattr(class_, "db_path")) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        await cur.execute(
            f"DELETE FROM {class_.__name__.lower()} WHERE obj_id = ?", (obj_id,)
        )
        await con.commit()


async def _remove_entry(self) -> None:
    """
    Remove the object's record in the underlying database.
    :param self: self instance.
    :return: None.
    """
    await remove_from(self.__class__, getattr(self, "obj_id"))


def _markup_table(markup_function):
    async def inner(self=None, **kwargs):
        if not kwargs:
            async with aiosqlite.connect(getattr(self, "db_path")) as con:
                cur: aiosqlite.Cursor = await con.cursor()
                await markup_function(self.__class__, cur, self.types_table)
        else:
            await markup_function(**kwargs)

    return inner


def datalite(
    db_path: str,
    type_overload: Optional[Dict[Optional[type], str]] = None,
    tweaked: bool = True,
    automarkup: bool = False,
) -> Callable:
    """Bind a dataclass to a sqlite3 database. This adds new methods to the class, such as
    `create_entry()`, `remove_entry()` and `update_entry()`.

    :param db_path: Path of the database to be bound.
    :param type_overload: Type overload dictionary.
    :param tweaked: Whether to use pickle type tweaks
    :param automarkup: Whether to use automarkup (synchronously)
    :return: The new dataclass.
    """

    def decorator(dataclass_: type, *_, **__):
        types_table = type_table.copy()
        if type_overload is not None:
            types_table.update(type_overload)

        setattr(dataclass_, "db_path", db_path)
        setattr(dataclass_, "types_table", types_table)
        setattr(dataclass_, "tweaked", tweaked)

        if automarkup:
            with sqlite3.connect(db_path) as con:
                cur: sqlite3.Cursor = con.cursor()
                if tweaked:
                    _tweaked_sync_create_table(dataclass_, cur, types_table)
                else:
                    _sync_create_table(dataclass_, cur, types_table)

        if tweaked:
            dataclass_.markup_table = _markup_table(_tweaked_create_table)
            dataclass_.create_entry = _tweaked_create_entry
            dataclass_.update_entry = _tweaked_update_entry
        else:
            dataclass_.markup_table = _markup_table(_create_table)
            dataclass_.create_entry = _create_entry
            dataclass_.update_entry = _update_entry
        dataclass_.remove_entry = _remove_entry

        return dataclass_

    return decorator
