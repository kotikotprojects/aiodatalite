Schema Migrations
==================

Datalite provides a module, ``aiodatalite.migrations`` that handles schema migrations. When a class
definition is modified, ``aiodatalite.migrations.migrate`` can be called to
transfer records to a table fitting the new definitions.

Let us say we have made changes to the fields of a dataclass called ``Student`` and now,
we want these changes to be made to the database. More specifically, we had a field called
``studentt_id`` and realised this was a typo, we want it to be named into ``student_id``,
and we want the values that was previously hold in this column to be persistent despite the
name change. We can achieve this easily by:

.. code-block:: python

    await migrate(Student, {'studentt_id': 'student_id'})

This will make all the changes, if we had not provided the second argument,
the values would be lost.

Also, ``migrate`` provides automatic backup before migration, you can turn it off by passing ``do_backup=False`` into
function.

We also introduce safe migration defaults. This parameter should be passed a key-value dictionary, where the key is the
name of the new required field, and the value is what should be written to the old records in the database.

.. code-block:: python

    from aiodatalite import datalite
    from aiodatalite.typed import DataliteHinted
    @datalite(db_path='db.db')
    @dataclass
    class Student(DataliteHinted):
        new_obligatory_field: str  # the database will break if not all records have this field
        student_id: int = 1
        student_name: str = "Kurt Gödel"
        student_gpa: float = 3.9

So in this situation basically what you need to do is:

.. code-block:: python

    await migrate(Student, safe_migration_defaults={
            "new_obligatory_field": "some value for records that already exist in the database"
        }
    )
