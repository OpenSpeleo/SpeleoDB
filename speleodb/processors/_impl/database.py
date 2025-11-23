# -*- coding: utf-8 -*-

from __future__ import annotations

from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import FileFormat

# ruff: noqa: E501


class DatabaseFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [
        # -------------------------- KML and related formats ------------------------- #
        #
        # SQLite and related formats
        ".sqlite",  # SQLite database files.
        ".db",  # General database file extension, commonly used for SQLite.
        ".db3",  # Another extension for SQLite database files.
        ".sqlite3",  # SQLite3 database files, a more specific version of SQLite.
        #
        # -------------- MySQL, MariaDB, and other relational databases -------------- #
        #
        ".sql",  # SQL script files, typically containing queries for database creation or modification.
        ".frm",  # MySQL table format files, used to store metadata.
        ".ibd",  # InnoDB database files in MySQL/MariaDB.
        ".myd",  # MySQL Data file (MyISAM).
        ".myi",  # MySQL Index file (MyISAM).
        ".cnf",  # MySQL configuration files.
        #
        # ------------------------ PostgreSQL-related formats ------------------------ #
        #
        ".pgsql",  # PostgreSQL SQL scripts.
        ".pgd",  # PostgreSQL database files.
        ".pdb",  # PostgreSQL database file (alternative format).
        #
        # --------------------------- Microsoft SQL Server --------------------------- #
        #
        ".mdf",  # Master database file in SQL Server.
        ".ndf",  # Secondary data files in SQL Server.
        ".ldf",  # Log files for SQL Server databases.
        #
        # ------------------------------ NoSQL databases ----------------------------- #
        #
        ".bson",  # Binary JSON format used by MongoDB.
        ".ndb",  # NoSQL database file (can refer to various NoSQL databases).
        ".couch",  # CouchDB database files.
        #
        # -------------------------- Other database systems -------------------------- #
        #
        ".accdb",  # Microsoft Access database files (Access 2007+).
        ".mdb",  # Microsoft Access database files (older versions).
        ".dbf",  # Database files often used with dBASE and older systems.
        ".fdb",  # Firebird database file.
        ".gdb",  # Geodatabase used in GIS applications.
        ".kdbx",  # KeePass database files.
        ".sqlitedb",  # Alternative SQLite database file extension.
        ".h2.db",  # H2 database files, a Java-based relational database.
        ".cdb",  # Compressed database files, often used in mobile applications.
        #
        # --------------------- Spatial databases and containers --------------------- #
        #
        ".spatialite",  # SpatiaLite, a spatial database based on SQLite.
        #
        # ------------------- Other miscellaneous database formats ------------------- #
        #
        ".rdb",  # Redis database file.
        ".hdb",  # HBase database file (for Hadoop ecosystem).
        ".tdb",  # Trident database file.
        ".xbase",  # Xbase database format (used in legacy systems).
        ".prn",  # Oracle Parallel Query format.
    ]

    ALLOWED_MIMETYPES = ["*"]
    ASSOC_FILEFORMAT = FileFormat.OTHER

    TARGET_FOLDER = "databases"
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None
