import unittest
from dataclasses import asdict, dataclass
from math import floor
from sqlite3 import connect

from aiodatalite import datalite
from aiodatalite.constraints import ConstraintFailedError, Unique
from aiodatalite.fetch import (
    fetch_all,
    fetch_equals,
    fetch_from,
    fetch_if,
    fetch_range,
    fetch_where,
)
from aiodatalite.mass_actions import copy_many, create_many
from aiodatalite.migrations import _drop_table, migrate
from aiodatalite.typed import DataliteHinted


@datalite(db_path="test.db")
@dataclass
class TestClass(DataliteHinted):
    integer_value: int = 1
    byte_value: bytes = b"a"
    float_value: float = 0.4
    str_value: str = "a"
    bool_value: bool = True

    def __eq__(self, other):
        return asdict(self) == asdict(other)


@datalite(db_path="test.db")
@dataclass
class FetchClass(DataliteHinted):
    ordinal: int
    str_: str

    def __eq__(self, other):
        return asdict(self) == asdict(other)


@datalite(db_path="test.db")
@dataclass
class Migrate1(DataliteHinted):
    ordinal: int
    conventional: str


@datalite(db_path="test.db")
@dataclass
class Migrate2(DataliteHinted):
    cardinal: Unique[int] = 1
    str_: str = "default"


@datalite(db_path="test.db")
@dataclass
class ConstraintedClass(DataliteHinted):
    unique_str: Unique[str]


@datalite(db_path="test.db")
@dataclass
class MassCommit(DataliteHinted):
    str_: str


def getValFromDB(obj_id=1):
    with connect("test.db") as db:
        cur = db.cursor()
        cur.execute(f"SELECT * FROM testclass WHERE obj_id = {obj_id}")
        fields = list(TestClass.__dataclass_fields__.keys())
        fields.sort()
        repr = dict(zip(fields, cur.fetchall()[0][1:]))
        _ = {key: value.type for key, value in TestClass.__dataclass_fields__.items()}
        test_object = TestClass(**repr)
    return test_object


class DatabaseMain(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.test_object = TestClass(12, b"bytes", 0.4, "TestValue")
        await self.test_object.markup_table()

    async def test_creation(self):
        await self.test_object.create_entry()
        self.assertEqual(self.test_object, getValFromDB())

    async def test_update(self):
        await self.test_object.create_entry()
        self.test_object.integer_value = 40
        await self.test_object.update_entry()
        from_db = getValFromDB(getattr(self.test_object, "obj_id"))
        self.assertEqual(self.test_object.integer_value, from_db.integer_value)

    async def test_delete(self):
        with connect("test.db") as db:
            cur = db.cursor()
            cur.execute("SELECT * FROM testclass")
            objects = cur.fetchall()
        init_len = len(objects)
        await self.test_object.create_entry()
        await self.test_object.remove_entry()
        with connect("test.db") as db:
            cur = db.cursor()
            cur.execute("SELECT * FROM testclass")
            objects = cur.fetchall()
        self.assertEqual(len(objects), init_len)


class DatabaseFetchCalls(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.objs = [FetchClass(1, "a"), FetchClass(2, "b"), FetchClass(3, "b")]
        await self.objs[0].markup_table()
        [await obj.create_entry() for obj in self.objs]

    async def testFetchFrom(self):
        t_obj = await fetch_from(FetchClass, self.objs[0].obj_id)
        self.assertEqual(self.objs[0], t_obj)

    async def testFetchEquals(self):
        t_obj = await fetch_equals(FetchClass, "str_", self.objs[0].str_)
        self.assertEqual(self.objs[0], t_obj)

    async def testFetchAll(self):
        t_objs = await fetch_all(FetchClass)
        self.assertEqual(tuple(self.objs), t_objs)

    async def testFetchIf(self):
        t_objs = await fetch_if(FetchClass, 'str_ = "b"')
        self.assertEqual(tuple(self.objs[1:]), t_objs)

    async def testFetchWhere(self):
        t_objs = await fetch_where(FetchClass, "str_", "b")
        self.assertEqual(tuple(self.objs[1:]), t_objs)

    async def testFetchRange(self):
        t_objs = await fetch_range(
            FetchClass, range(self.objs[0].obj_id, self.objs[2].obj_id)
        )
        self.assertEqual(tuple(self.objs[0:2]), t_objs)

    async def asyncTearDown(self) -> None:
        [await obj.remove_entry() for obj in self.objs]


class DatabaseFetchPaginationCalls(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.objs = [FetchClass(i, f"{floor(i/10)}") for i in range(30)]
        await self.objs[0].markup_table()
        [await obj.create_entry() for obj in self.objs]

    async def testFetchAllPagination(self):
        t_objs = await fetch_all(FetchClass, 1, 10)
        self.assertEqual(tuple(self.objs[:10]), t_objs)

    async def testFetchWherePagination(self):
        t_objs = await fetch_where(FetchClass, "str_", "0", 2, 5)
        self.assertEqual(tuple(self.objs[5:10]), t_objs)

    async def testFetchIfPagination(self):
        t_objs = await fetch_if(FetchClass, 'str_ = "0"', 1, 5)
        self.assertEqual(tuple(self.objs[:5]), t_objs)

    async def asyncTearDown(self) -> None:
        [await obj.remove_entry() for obj in self.objs]


class DatabaseMigration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.objs = [Migrate1(i, "a") for i in range(10)]
        await self.objs[0].markup_table()
        [await obj.create_entry() for obj in self.objs]

    async def testBasicMigrate(self):
        global Migrate1, Migrate2
        Migrate1 = Migrate2
        Migrate1.__name__ = "Migrate1"
        await migrate(Migrate1, {"ordinal": "cardinal"})
        t_objs = await fetch_all(Migrate1)
        self.assertEqual(
            [obj.ordinal for obj in self.objs], [obj.cardinal for obj in t_objs]
        )
        self.assertEqual(["default" for _ in range(10)], [obj.str_ for obj in t_objs])

    async def asyncTearDown(self) -> None:
        t_objs = await fetch_all(Migrate1)
        [await obj.remove_entry() for obj in t_objs]
        await _drop_table("test.db", "migrate1")


async def helperFunc():
    obj = ConstraintedClass("This string is supposed to be unique.")
    await obj.create_entry()


class DatabaseConstraints(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.obj = ConstraintedClass("This string is supposed to be unique.")
        try:
            await _drop_table("test.db", "constraintedclass")
        except Exception as e:
            assert e
        await self.obj.markup_table()
        await self.obj.create_entry()

    async def testUniquness(self):
        try:
            await helperFunc()
        except Exception as e:
            self.assertEqual(e.__class__, ConstraintFailedError)
        else:
            self.fail("Did not raise")

    async def testNullness(self):
        try:
            await ConstraintedClass(None).create_entry()
        except Exception as e:
            self.assertEqual(e.__class__, ConstraintFailedError)
        else:
            self.fail("Did not raise")

    async def asyncTearDown(self) -> None:
        await self.obj.remove_entry()


class DatabaseMassInsert(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.objs = [MassCommit(f"cat + {i}") for i in range(30)]
        await self.objs[0].markup_table()

    async def testMassCreate(self):
        with connect("other.db") as con:
            cur = con.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS MASSCOMMIT (obj_id, str_)")

        start_tup = await fetch_all(MassCommit)
        await create_many(self.objs, protect_memory=False)
        _objs = await fetch_all(MassCommit)
        self.assertEqual(_objs, start_tup + tuple(self.objs))

    async def _testMassCopy(self):
        setattr(MassCommit, "db_path", "other.db")
        start_tup = await fetch_all(MassCommit)
        await copy_many(self.objs, "other.db", False)
        tup = await fetch_all(MassCommit)
        self.assertEqual(tup, start_tup + tuple(self.objs))

    async def asyncTearDown(self) -> None:
        [await obj.remove_entry() for obj in self.objs]


if __name__ == "__main__":
    unittest.main()
