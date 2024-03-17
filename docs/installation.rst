Getting Started
=================

Welcome to the documentation of aiodatalite, an asynchronous fork of datalite. Datalite provides a simple, intuitive
way to bind dataclasses to sqlite3 databases. In its current version, it provides implicit support for conversion
between ``int``, ``float``, ``str``, ``bytes`` classes and their ``sqlite3`` counterparts, default values,
basic schema migration and fetching functions.
Also, aiodatalite introduces ``tweaked`` parameter (True by default), which allows using pickle to store any values
in database

Installation
############

Simply write:

.. code-block:: bash

    pip install aiodatalite

In the shell. And then, whenever you want to use it in Python, you can use:

.. code-block:: python

    import aiodatalite

