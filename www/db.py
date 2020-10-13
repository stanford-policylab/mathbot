import datetime
import sqlite3
import click
from flask import current_app, g
from flask.cli import with_appcontext
import pandas as pd
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s %(message)s')


class BaseDatabase:
    def __init__(self, path, debug=False):
        self._path = path
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self.logger = logging.getLogger('Database: {}'.format(self._path))
        if debug:
            self.logger.setLevel(logging.DEBUG)
        # Todo: Hao using flask current_app's logger

        self.logger.info("DB connected: {}".format(str(self._path)))
        self._cursor = self._conn.cursor()

    def init_table(self, table, schema):
        # schema is a list of key in the db
        """
        if table in self.get_tables():
            self.backup(table)
        """
        primary_key = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
        cols = ", ".join(["`{}` TEXT".format(key) for key in schema] + primary_key)
        create_query = "CREATE TABLE IF NOT EXISTS {} ({});".format(table, cols)
        self._execute(create_query)

    def close(self):
        # close connection
        self._cursor.close()
        self._conn.close()

    def exists(self, table, kvals):
        # check if the table exist
        kvals_pairs = " AND ".join(['"{}" = "{}"'.format(k, v) for k, v in kvals.items()])
        search_query = 'SELECT * FROM {} WHERE {}'.format(table, kvals_pairs)
        exist = self._execute(search_query)
        return len(exist) != 0

    def backup(self, table):
        # rename table with a timestamp
        backup_table = table + '_backup_' + str(datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
        backup_query = "ALTER TABLE {} RENAME TO {};".format(table, backup_table)
        self._execute(backup_query)

    def insert(self, table, kvals):
        # insert kvals to table as a row
        kvals = dict(kvals)
        if len(kvals) == 0:
            return
        keys = kvals.keys()
        cols = ', '.join(['`' + str(k).strip() + '`' for k in keys])
        vals = ', '.join(['"' + self._clean(kvals[k]) + '"' for k in keys])
        insert_query = "INSERT INTO {} ({}) VALUES ({})".format(table, cols, vals)
        self._execute(insert_query)

    def fetch(self, table, keys=None):
        # fetch all result of certain keys
        cols = "*" if keys is None else ",".join(keys)
        fetch_query = "SELECT {} FROM {}".format(cols, table)
        return pd.read_sql(fetch_query, self._conn)

    def get_tables(self):
        get_query = "SELECT name FROM sqlite_master WHERE type = 'table'"
        return [t[0] for t in self._execute(get_query)]

    def _execute(self, sql_statement, retry_table=None):
        # execute sql_statement
        self.logger.info("Going to execute: {}".format(sql_statement))
        try:
            self._cursor.execute(sql_statement)
            self._conn.commit()
            return self._cursor.fetchall()
        except sqlite3.OperationalError as e:
            self.logger.warning("DB ERROR: {}".format(str(e)))
            self.logger.warning("DB WARNING: {}".format(str(e)))
            # Todo: fix the backup part
            """
            if retry_table is not None:
                self.backup(retry_table)
                self.init_table(current_app.config['EXP_DB_FIELDS'])
                self._execute(sql_statement, try_to_recreate_table=False)
            """
        except sqlite3.Error as e:
            self.logger.info(e)
            self.logger.error("DB ERROR: {}".format(str(e)))

    def _clean(self, val):
        # clean sql_statement
        val = str(val)
        try:
            val = val.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
            val = val.strip().replace(u'’', "'").replace('"', "''").replace("\n", " ")
            return val
        except:
            self.logger.error("[Failed to clean SQL val: {}]".format(val))


class ConfigDatabase(BaseDatabase):
    def __init__(self, _config):
        self._config = _config
        super(ConfigDatabase, self).__init__(path=self._config['DB_PATH'],
                                             debug=self._config['DB_DEBUG'])
        self.contextTable = ContextTable(self, self._config)
        self.experimentTable = ExperimentTable(self, self._config)
        self.rewardTable = RewardTable(self, self._config)
        self.actionTable = ActionTable(self, self._config)
        self.tables = [self.contextTable, self.experimentTable, self.rewardTable, self.actionTable]
        self.init_db()

    def init_db(self):
        for table in self.tables:
            table.create()

    def backup_db(self):
        for table in [self.contextTable, self.experimentTable, self.rewardTable, self.actionTable]:
            table.backup()


class Table:
    def __init__(self, db, table, schema, debug=False):
        self._table = table
        self._schema = schema
        self._db = db
        self.logger = logging.getLogger('Database: {}'.format(self._table))
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def create(self):
        self._db.init_table(self._table, self._schema)

    def insert(self, kvals):
        self._db.insert(self._table, kvals)

    def backup(self):
        self._db.backup(self._table)

    def fetch(self, keys=None):
        return self._db.fetch(self._table, keys)


class ModelTable(Table):
    pass


class ContextTable(Table):
    def __init__(self, db, _config=None):
        if _config is None:
            _config = current_app.config
        self._schema = _config['CONTEXT_SCHEMA']
        self._table = _config['CONTEXT_TABLE']
        self._debug = False
        super(ContextTable, self).__init__(db, table=self._table, schema=self._schema, debug=self._debug)


class RewardTable(Table):
    def __init__(self, db, _config=None):
        if _config is None:
            _config = current_app.config
        self._schema = _config['REWARD_SCHEMA']
        self._table = _config['REWARD_TABLE']
        self._debug = False
        super(RewardTable, self).__init__(db, table=self._table, schema=self._schema, debug=self._debug)


class ActionTable(Table):
    def __init__(self, db, _config=None):
        if _config is None:
            _config = current_app.config
        self._schema = _config['ACTION_SCHEMA']
        self._table = _config['ACTION_TABLE']
        self._debug = False
        super(ActionTable, self).__init__(db, table=self._table, schema=self._schema, debug=self._debug)


class ExperimentTable(Table):
    def __init__(self, db, _config=None):
        if _config is None:
            _config = current_app.config
        self._schema = _config['EXP_SCHEMA']
        self._table = _config['EXP_TABLE']
        self._debug = False
        super(ExperimentTable, self).__init__(db, table=self._table, schema=self._schema, debug=self._debug)

    def query_if_contains_user(self, user_id):
        query = 'SELECT * FROM %s WHERE "user-id" = "%s"' % (self._table, user_id)
        self._db._execute(query)
        exist = self._db._cursor.fetchone()
        if exist is None:
            return False
        else:
            return True

    def query_group_size(self, group_name, table):
        query = 'SELECT count(*) FROM %s WHERE "churn-on-page"=="Submitted" AND "user-group"=="%s" ' % (
            table, group_name)
        self._db._execute(query)
        values = self._db._cursor.fetchone()
        return values[0]

    def record_progress(self, _request):
        # global result_df
        # TODO: @Jerry why this?
        kvals = dict(_request.form)
        try:
            self.insert(kvals)
        except:
            self.logger.warning("Fail to find DB when inserting, re-creating db")
            # create table - will not be executed as exception as been captured in execute_sql, but just in case
            self.backup()
            self.create()
            self.insert(kvals)

    def assign_group(self):
        global group_names
        min_g_name = "MathBot"
        min_g_size = self.query_group_size("MathBot")
        print(min_g_name, min_g_size)
        for g_name in group_names:
            if g_name != min_g_name:
                g_size = self.query_group_size(g_name)
                print(g_name, g_size)
                if g_size < min_g_size:
                    min_g_name = g_name
                    min_g_size = g_size
        return str(min_g_name)


"""
==========================================
Helper function to tie the db with the app
==========================================
"""


def get_db():
    """Glue function to push an initialized db to the global context"""
    if 'db' not in g:
        g.db = ConfigDatabase(_config=current_app.config)
    return g.db


def close_db(e=None):
    """Close the db and pop up from the global context"""
    db = g.pop('db', None)

    if db is not None:
        db.close()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Register the initialization function to the cli"""
    db = get_db()
    db.init_db()
    click.echo('Initialized the database.')


@click.command('backup-db')
@with_appcontext
def backup_db_command():
    """Register the initialization function to the cli"""
    db = get_db()
    db.backup_db()
    click.echo('Backuped the database.')


def init_app(app):
    """Register the cli and teardown to the app"""
    app.cli.add_command(backup_db_command)
    app.cli.add_command(init_db_command)
    app.teardown_appcontext(close_db)
