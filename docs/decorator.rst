Basic Decorator Operations
==========================

Creating a datalite class
-------------------------

A datalite class is a special dataclass. It is created by using a decorator ``@aiodatalite.datalite``,
members of this class are, from Python's perspective, just normal classes. However, they have
additional methods and attributes. ``@datalite`` decorator needs a database path to be provided.
This database is the database the table for the dataclass will be created.

.. code-block:: python

    from aiodatalite import datalite
    @datalite(db_path='db.db')
    @dataclass
    class Student:
        student_id: int = 1
        student_name: str = "Kurt Gödel"
        student_gpa: float = 3.9

Here, ``datalite`` will create a table called ``student`` in the database file ``db.db``, this
file will include all the fields of the dataclass as columns. Default value of these columns
are same as the default value of the dataclass.

Special Methods
---------------

Each object initialised from a dataclass decorated with the ``@dataclass`` decorator automatically
gains access to three special methods. It should be noted, due to the nature of the library, extensions
such as ``mypy`` and IDEs such as PyCharm will not be able to see these methods and may raise exceptions.
So, aiodatalite introduces ``typed`` module and ``DataliteHinted`` class, from which you can inherit your dataclass.

.. code-block:: python

    from aiodatalite import datalite
    from aiodatalite.typed import DataliteHinted
    @datalite(db_path='db.db')
    @dataclass
    class Student(DataliteHinted):
        student_id: int = 1
        student_name: str = "Kurt Gödel"
        student_gpa: float = 3.9

With this in mind, let us create a new object and run the methods over this objects.

.. code-block:: python

    new_student = Student(0, "Albert Einstein", 4.0)

Marking up Table
#################
Due to the limitations of asynchronous programming, we cannot automatically create the table asynchronously,
so we provide two ways to do this.

First way is to create the table automatically in !synchronous! mode by explicitly passing an argument to the decorator.
We don't know what consequences this can lead to specifically in your application, but if you are confident in yourself,
use this method

.. code-block:: python

    ...
    @datalite(db_path='db.db', automarkup=True)
    @dataclass
    class Student(DataliteHinted):
    ...

The second way, which may be less convenient when using some frameworks but is more controllable, is to call the
asynchronous ``create_table`` method, which will be added to your dataclass after using ``@datalite`` decorator,
alongside with some other methods.

.. code-block:: python

    await new_student.markup_table()

Creating an Entry
##################

First special method is ``.create_entry()`` when called on an object of a class decorated with the
``@datalite`` decorator, this method creates an entry in the table of the bound database of the class,
in this case, table named ``student`` in the ``db.db``. Therefore, to create the entry of Albert Einstein
in the table:

.. code-block:: python

    await new_student.create_entry()

This also modifies the object in an intresting way, it adds a new attribute ``obj_id``, this is a unique,
autoincremented value in the database. It can be accessed by ``new_student.obj_id``.

Updating an Entry
##################

Second special method is ``.update_entry()``. If an object's attribute is changed, to update its
record in the database, this method must be called.

.. code-block:: python

    new_student.student_gpa = 5.0  # He is Einstein, after all.
    await new_student.update_entry()


Deleting an Entry
##################

To delete an entry from the record, the third and last special method, ``.remove_entry()`` should
be used.

.. code-block:: python

    await new_student.remove_entry()

.. warning::

    It should be noted that, if the ``new_student.obj_id`` attribute is modified, ``.update_entry()``
    and ``.remove_entry()`` may have unexpected results.


Tweaked Types
--------------
Sometimes your objects may be somewhat complex or use a nested structure. This fork allows nesting by using the pickle
module, which gives you the ability to turn your objects into pure bytes that can be written to and from the database.
When the ``tweaked`` parameter is enabled, data that can be written natively is written as is, and data that cannot be
written in this way is first processed by pickle.

.. code-block:: python

    from aiodatalite import datalite
    from aiodatalite.typed import DataliteHinted

    # Bag dataclass defined somewhere

    @datalite(db_path='db.db')
    @dataclass
    class Student(DataliteHinted):
        student_id: int = 1
        student_name: str = "Kurt Gödel"
        student_gpa: float = 3.9
        bag: Bag = Bag(
            size="big",
            items_number=88,
            ...
        )

But with great opportunity comes great responsibility, so using nested models can lead to difficulties in migrating data
and updating the structure of nested objects, so changing the ``Bag`` object in this example, in theory, can break the
database without the possibility of migration. We recommend using multiple tables and simple relationships between them
(must be organized independently) in such cases.

The tweaked functionality of types can be disabled by passing the tweaked parameter as False to the datalite decorator

.. code-block:: python

    from aiodatalite import datalite
    from aiodatalite.typed import DataliteHinted

    # Bag is defined somewhere as datalite table instance

    @datalite(db_path='db.db', tweaked=False)
    @dataclass
    class Student(DataliteHinted):
        bag_id: int
        student_id: int = 1
        student_name: str = "Kurt Gödel"
        student_gpa: float = 3.9
