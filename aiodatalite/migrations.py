"""
Migrations module deals with migrating data when the object
definitions change. This functions deal with Schema Migrations.
"""
import shutil
import time
from dataclasses import Field
from os.path import exists
from typing import Any, Dict, List, Tuple, cast

import aiosqlite

from .commons import _get_table_cols, _tweaked_dump_value


async def _get_db_table(class_: type) -> Tuple[str, str]:
    """
    Check if the class is a datalite class, the database exists,
    and the table exists. Return database and table names.

    :param class_: A datalite class.
    :return: A tuple of database and table names.
    """
    database_name: str = getattr(class_, "db_path", None)
    if not database_name:
        raise TypeError(f"{class_.__name__} is not a datalite class.")
    table_name: str = class_.__name__.lower()
    if not exists(database_name):
        raise FileNotFoundError(f"{database_name} does not exist")
    async with aiosqlite.connect(database_name) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        await cur.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?;",
            (table_name,),
        )
        count: int = int((await cur.fetchone())[0])
    if not count:
        raise FileExistsError(f"Table, {table_name}, already exists.")
    return database_name, table_name


async def _get_table_column_names(database_name: str, table_name: str) -> Tuple[str]:
    """
    Get the column names of the table.

    :param database_name: The name of the database the table
        resides in.
    :param table_name: Name of the table.
    :return: A tuple holding the column names of the table.
    """
    async with aiosqlite.connect(database_name) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        cols: List[str] = await _get_table_cols(cur, table_name)
    return cast(Tuple[str], tuple(cols))


async def _copy_records(database_name: str, table_name: str):
    """
    Copy all records from a table.

    :param database_name: Name of the database.
    :param table_name: Name of the table.
    :return: A generator holding dataclass asdict representations.
    """
    async with aiosqlite.connect(database_name) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        await cur.execute(f"SELECT * FROM {table_name};")
        values = await cur.fetchall()
        keys = await _get_table_cols(cur, table_name)
        keys.insert(0, "obj_id")
    records = (dict(zip(keys, value)) for value in values)
    return records


async def _drop_table(database_name: str, table_name: str) -> None:
    """
    Drop a table.

    :param database_name: Name of the database.
    :param table_name: Name of the table to be dropped.
    :return: None.
    """
    async with aiosqlite.connect(database_name) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        await cur.execute(f"DROP TABLE {table_name};")
        await con.commit()


def _modify_records(
    data, col_to_del: Tuple[str], col_to_add: Tuple[str], flow: Dict[str, str]
) -> Tuple[Dict[str, str]]:
    """
    Modify the asdict records in accordance
        with schema migration rules provided.

    :param data: Data kept as asdict in tuple.
    :param col_to_del: Column names to delete.
    :param col_to_add: Column names to add.
    :param flow: A dictionary that explains
        if the data from a deleted column
        is transferred to a column
        to be added.
    :return: The modified data records.
    """
    records = []
    for record in data:
        record_mod = {}
        for key in record.keys():
            if key in col_to_del and key in flow:
                record_mod[flow[key]] = record[key]
            elif key in col_to_del:
                pass
            else:
                record_mod[key] = record[key]
        for key_to_add in col_to_add:
            if key_to_add not in record_mod:
                record_mod[key_to_add] = None
        records.append(record_mod)
    return cast(Tuple[Dict[str, str]], records)


async def _migrate_records(
    class_: type,
    database_name: str,
    data,
    col_to_del: Tuple[str],
    col_to_add: Tuple[str],
    flow: Dict[str, str],
    safe_migration_defaults: Dict[str, Any] = None,
) -> None:
    """
    Migrate the records into the modified table.

    :param class_: Class of entries.
    :param database_name: Name of the database.
    :param data: Data, asdict tuple.
    :param col_to_del: Columns to be deleted.
    :param col_to_add: Columns to be added.
    :param flow: Flow dictionary stating where
        column data will be transferred.
    :return: None.
    """
    if safe_migration_defaults is None:
        safe_migration_defaults = {}

    async with aiosqlite.connect(database_name) as con:
        cur: aiosqlite.Cursor = await con.cursor()
        # noinspection PyUnresolvedReferences
        await class_.markup_table(
            class_=class_, cursor=cur, type_overload=getattr(class_, "types_table")
        )
        await con.commit()
    new_records = _modify_records(data, col_to_del, col_to_add, flow)
    for record in new_records:
        del record["obj_id"]
        keys_to_delete = [key for key in record if record[key] is None]
        for key in keys_to_delete:
            del record[key]
        await class_(
            **{
                **record,
                **{
                    k: _tweaked_dump_value(class_, v)
                    for k, v in safe_migration_defaults.items()
                    if k not in record
                },
            }
        ).create_entry()


async def migrate(
    class_: type,
    column_transfer: dict = None,
    do_backup: bool = True,
    safe_migration_defaults: Dict[str, Any] = None,
) -> None:
    """
    Given a class, compare its previous table,
    delete the fields that no longer exist,
    create new columns for new fields. If the
    column_flow parameter is given, migrate elements
    from previous column to the new ones. It should be
    noted that the obj_ids do not persist.

    :param class_: Datalite class to migrate.
    :param column_transfer: A dictionary showing which
        columns will be copied to new ones.
    :param do_backup: Whether to copy a whole database before dropping table
    :param safe_migration_defaults: Key-value that will be written to old records in the database during
        migration so as not to break the schema
    :return: None.
    """
    database_name, table_name = await _get_db_table(class_)
    table_column_names: Tuple[str] = await _get_table_column_names(
        database_name, table_name
    )

    # noinspection PyUnresolvedReferences
    values: List[Field] = class_.__dataclass_fields__.values()

    data_fields: Tuple[Field] = cast(Tuple[Field], tuple(field for field in values))
    data_field_names: Tuple[str] = cast(
        Tuple[str], tuple(field.name for field in data_fields)
    )
    columns_to_be_deleted: Tuple[str] = cast(
        Tuple[str],
        tuple(
            column for column in table_column_names if column not in data_field_names
        ),
    )
    columns_to_be_added: Tuple[str] = cast(
        Tuple[str],
        tuple(
            column for column in data_field_names if column not in table_column_names
        ),
    )

    records = await _copy_records(database_name, table_name)
    if do_backup:
        shutil.copy(database_name, f"{database_name}-{time.time()}")
    await _drop_table(database_name, table_name)
    await _migrate_records(
        class_,
        database_name,
        records,
        columns_to_be_deleted,
        columns_to_be_added,
        column_transfer,
        safe_migration_defaults,
    )


__all__ = ["migrate"]
