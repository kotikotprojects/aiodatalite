"""
This module includes functions to insert multiple records
to a bound database at one time, with one time open and closing
of the database file.
"""
from dataclasses import asdict, fields
from typing import List, Tuple, TypeVar, Union
from warnings import warn

import aiosqlite

from .commons import _tweaked_dump
from .constraints import ConstraintFailedError

T = TypeVar("T")


class HeterogeneousCollectionError(Exception):
    """
    :raise : if the passed collection is not homogeneous.
        ie: If a List or Tuple has elements of multiple
        types.
    """

    pass


def _check_homogeneity(objects: Union[List[T], Tuple[T]]) -> None:
    """
    Check if all the members a Tuple or a List
    is of the same type.

    :param objects: Tuple or list to check.
    :return: If all the members of the same type.
    """
    class_ = objects[0].__class__
    if not all(
        [
            isinstance(obj, class_) or isinstance(objects[0], obj.__class__)
            for obj in objects
        ]
    ):
        raise HeterogeneousCollectionError("Tuple or List is not homogeneous.")


async def _toggle_memory_protection(
    cur: aiosqlite.Cursor, protect_memory: bool
) -> None:
    """
    Given a cursor to a sqlite3 connection, if memory protection is false,
        toggle memory protections off.

    :param cur: Cursor to an open SQLite3 connection.
    :param protect_memory: Whether should memory be protected.
    :return: Memory protections off.
    """
    if not protect_memory:
        warn(
            "Memory protections are turned off, "
            "if operations are interrupted, file may get corrupt.",
            RuntimeWarning,
        )
        await cur.execute("PRAGMA synchronous = OFF")
        await cur.execute("PRAGMA journal_mode = MEMORY")


async def _mass_insert(
    objects: Union[List[T], Tuple[T]], db_name: str, protect_memory: bool = True
) -> None:
    """
    Insert multiple records into an SQLite3 database.

    :param objects: Objects to insert.
    :param db_name: Name of the database to insert.
    :param protect_memory: Whether memory
        protections are on or off.
    :return: None
    """
    _check_homogeneity(objects)
    is_tweaked = getattr(objects[0], "tweaked")
    first_index: int = 0
    table_name = objects[0].__class__.__name__.lower()

    for i, obj in enumerate(objects):
        setattr(obj, "obj_id", first_index + i + 1)
    async with aiosqlite.connect(db_name) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        try:
            await _toggle_memory_protection(cur, protect_memory)
            await cur.execute(
                f"SELECT obj_id FROM {table_name} ORDER BY obj_id DESC LIMIT 1"
            )
            index_tuple = await cur.fetchone()
            if index_tuple:
                _ = index_tuple[0]

            await cur.execute("BEGIN TRANSACTION;")

            for i, obj in enumerate(objects):
                if is_tweaked:
                    kv_pairs = [item for item in fields(obj)]
                    kv_pairs.sort(key=lambda item: item.name)
                    column_names = ", ".join(item.name for item in kv_pairs)
                    vals = tuple(_tweaked_dump(obj, item.name) for item in kv_pairs)
                else:
                    kv_pairs = [item for item in asdict(obj).items()]
                    kv_pairs.sort(key=lambda item: item[0])
                    column_names = ", ".join(column[0] for column in kv_pairs)
                    vals = tuple(column[1] for column in kv_pairs)
                setattr(obj, "obj_id", first_index + i + 1)

                placeholders = ", ".join("?" for _ in kv_pairs)
                sql_statement = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders});"

                await cur.execute(sql_statement, vals)

            await cur.execute("END TRANSACTION;")

        except aiosqlite.IntegrityError:
            raise ConstraintFailedError
        await con.commit()


async def create_many(
    objects: Union[List[T], Tuple[T]], protect_memory: bool = True
) -> None:
    """
    Insert many records corresponding to objects
    in a tuple or a list.

    :param protect_memory: If False, memory protections are turned off,
        makes it faster.
    :param objects: A tuple or a list of objects decorated
        with datalite.
    :return: None.
    """
    if objects:
        await _mass_insert(objects, getattr(objects[0], "db_path"), protect_memory)
    else:
        raise ValueError("Collection is empty.")


async def copy_many(
    objects: Union[List[T], Tuple[T]], db_name: str, protect_memory: bool = True
) -> None:
    """
    Copy many records to another database, from
    their original database to a new database, do
    not delete old records.

    :param objects: Objects to copy.
    :param db_name: Name of the new database.
    :param protect_memory: Whether to protect memory during operation,
        Setting this to False will quicken the operation, but if the
        operation is cut short, the database file will corrupt.
    :return: None
    """
    if objects:
        async with aiosqlite.connect(db_name) as con:
            cur = await con.cursor()
            await objects[0].markup_table(class_=objects[0].__class__, cursor=cur)
            await con.commit()
        await _mass_insert(objects, db_name, protect_memory)
    else:
        raise ValueError("Collection is empty.")


__all__ = ["copy_many", "create_many", "HeterogeneousCollectionError"]
