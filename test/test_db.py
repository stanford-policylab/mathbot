import unittest
from www.db import BaseDatabase
import tempfile
import shutil
import os


class TestBaseDatabase(unittest.TestCase):
    def setUp(self):
        self.DIR = tempfile.mkdtemp()
        self.PATH = os.path.join(self.DIR, "test.db")
        self.DATABASE = BaseDatabase(path=self.PATH, debug=False)
        self.TABLE = "TESTTABLE"
        self.SCHEMA = ["A", "B", "C"]
        self.KVALS = {"A": "a", "B": "b", "C": "c"}

    def tearDown(self):
        shutil.rmtree(self.DIR)

    def testGetTable(self):
        tables = self.DATABASE.get_tables()
        self.assertEqual(tables, [])

    def testInitTable(self):
        self.DATABASE.init_table(table=self.TABLE, schema=self.SCHEMA)
        tables = self.DATABASE.get_tables()
        self.assertIn(self.TABLE, tables)

    def testInsertFetch(self):
        self.DATABASE.init_table(table=self.TABLE, schema=self.SCHEMA)
        self.DATABASE.insert(table=self.TABLE, kvals=self.KVALS)
        data = self.DATABASE.fetch(table=self.TABLE)

        self.assertEqual(len(data), 1)
        for k, v in self.KVALS.items():
            self.assertEqual(data[k][0], v)

    def testBackup(self):
        self.DATABASE.init_table(table=self.TABLE, schema=self.SCHEMA)
        self.DATABASE.insert(table=self.TABLE, kvals=self.KVALS)
        self.DATABASE.backup(table=self.TABLE)

        tables = self.DATABASE.get_tables()
        self.assertNotIn(self.TABLE, tables)

        backup = [t for t in tables if self.TABLE in t]
        self.assertEqual(len(backup), 1)

        data = self.DATABASE.fetch(table=backup[0])
        self.assertEqual(len(data), 1)
        for k, v in self.KVALS.items():
            self.assertEqual(data[k][0], v)

    def testExist(self):
        self.DATABASE.init_table(table=self.TABLE, schema=self.SCHEMA)

        self.assertFalse(self.DATABASE.exists(self.TABLE, self.KVALS))
        self.DATABASE.insert(table=self.TABLE, kvals=self.KVALS)

        self.assertTrue(self.DATABASE.exists(self.TABLE, self.KVALS))
