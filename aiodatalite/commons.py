import sqlite3
from dataclasses import MISSING, Field
from pickle import HIGHEST_PROTOCOL, dumps, loads
from typing import Any, Dict, List, Optional

import aiosqlite
from aiosqlite import IntegrityError

from .constraints import Unique

type_table: Dict[Optional[type], str] = {
    None: "NULL",
    int: "INTEGER",
    float: "REAL",
    str: "TEXT",
    bytes: "BLOB",
    bool: "INTEGER",
}
type_table.update(
    {Unique[key]: f"{value} NOT NULL UNIQUE" for key, value in type_table.items()}
)


def _convert_type(
    type_: Optional[type], type_overload: Dict[Optional[type], str]
) -> str:
    """
    Given a Python type, return the str name of its
    SQLlite equivalent.
    :param type_: A Python type, or None.
    :param type_overload: A type table to overload the custom type table.
    :return: The str name of the sql type.
    >>> _convert_type(int)
    "INTEGER"
    """
    try:
        return type_overload[type_]
    except KeyError:
        raise TypeError(
            "Requested type not in the default or overloaded type table. Use @datalite(tweaked=True) to "
            "encode custom types"
        )


def _tweaked_convert_type(
    type_: Optional[type], type_overload: Dict[Optional[type], str]
) -> str:
    return type_overload.get(type_, "BLOB")


def _convert_sql_format(value: Any) -> str:
    """
    Given a Python value, convert to string representation
    of the equivalent SQL datatype.
    :param value: A value, ie: a literal, a variable etc.
    :return: The string representation of the SQL equivalent.
    """
    if value is None:
        return "NULL"
    elif isinstance(value, str):
        return f'"{value}"'
    elif isinstance(value, bytes):
        return '"' + str(value).replace("b'", "")[:-1] + '"'
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    else:
        return str(value)


async def _get_table_cols(cur: aiosqlite.Cursor, table_name: str) -> List[str]:
    """
    Get the column data of a table.

    :param cur: Cursor in database.
    :param table_name: Name of the table.
    :return: the information about columns.
    """
    await cur.execute(f"PRAGMA table_info({table_name});")
    return [row_info[1] for row_info in await cur.fetchall()][1:]


def _get_default(
    default_object: object,
    type_overload: Dict[Optional[type], str],
    mutable_def_params: list,
) -> str:
    """
    Check if the field's default object is filled,
    if filled return the string to be put in the,
    database.
    :param default_object: The default field of the field.
    :param type_overload: Type overload table.
    :return: The string to be put on the table statement,
    empty string if no string is necessary.
    """
    if type(default_object) in type_overload:
        return f" DEFAULT {_convert_sql_format(default_object)}"
    elif type(default_object) is type(MISSING):
        return ""
    else:
        mutable_def_params.append(
            bytes(dumps(default_object, protocol=HIGHEST_PROTOCOL))
        )
        return " DEFAULT ?"


def _get_creation_data(
    class_: type,
    type_overload: Dict[Optional[type], str],
    type_converter,
):
    fields: List[Field] = [
        class_.__dataclass_fields__[key] for key in class_.__dataclass_fields__.keys()
    ]
    fields.sort(key=lambda field: field.name)  # Since dictionaries *may* be unsorted.

    def_params = list()

    sql_fields = ", ".join(
        f"{field.name} {type_converter(field.type, type_overload)}"
        f"{_get_default(field.default, type_overload, def_params)}"
        for field in fields
    )

    sql_fields = "obj_id INTEGER PRIMARY KEY AUTOINCREMENT, " + sql_fields
    return sql_fields, def_params


# noinspection PyDefaultArgument
async def _tweaked_create_table(
    class_: type,
    cursor: aiosqlite.Cursor,
    type_overload: Dict[Optional[type], str] = type_table,
) -> None:
    await _create_table(
        class_, cursor, type_overload, type_converter=_tweaked_convert_type
    )


# noinspection PyDefaultArgument
async def _create_table(
    class_: type,
    cursor: aiosqlite.Cursor,
    type_overload: Dict[Optional[type], str] = type_table,
    type_converter=_convert_type,
) -> None:
    """
    Create the table for a specific dataclass given
    :param class_: A dataclass.
    :param cursor: Current cursor instance.
    :param type_overload: Overload the Python -> SQLDatatype table
    with a custom table, this is that custom table.
    :return: None.
    """
    sql_fields, def_params = _get_creation_data(
        class_, type_overload, type_converter=type_converter
    )
    print(sql_fields)
    print(def_params)
    await cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {class_.__name__.lower()} ({sql_fields});",
        def_params if def_params else None,
    )


# noinspection PyDefaultArgument
def _sync_create_table(
    class_: type,
    cursor: sqlite3.Cursor,
    type_overload: Dict[Optional[type], str] = type_table,
    type_converter=_convert_type,
) -> None:
    sql_fields, def_params = _get_creation_data(
        class_, type_overload, type_converter=type_converter
    )
    print(sql_fields)
    print(def_params)
    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {class_.__name__.lower()} ({sql_fields});",
        def_params if def_params else (),
    )


# noinspection PyDefaultArgument
def _tweaked_sync_create_table(
    class_: type,
    cursor: sqlite3.Cursor,
    type_overload: Dict[Optional[type], str] = type_table,
) -> None:
    _sync_create_table(
        class_, cursor, type_overload, type_converter=_tweaked_convert_type
    )


def _tweaked_dump_value(self, value):
    if type(value) in self.types_table:
        return value
    else:
        return bytes(dumps(value, protocol=HIGHEST_PROTOCOL))


def _tweaked_dump(self, name):
    value = getattr(self, name)
    field_types = {key: value.type for key, value in self.__dataclass_fields__.items()}
    if (
        "NOT NULL UNIQUE" not in self.types_table.get(field_types[name], "")
        or value is not None
    ):
        return _tweaked_dump_value(self, value)
    else:
        raise IntegrityError


def _tweaked_load_value(data):
    return loads(bytes(data))
