
import os

from dotenv import load_dotenv
load_dotenv()

import pymysql
import pymysql.cursors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

MYSQL_HOST = os.environ.get('CAT_MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('CAT_MYSQL_PORT', '3306'))
MYSQL_USER = os.environ.get('CAT_MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('CAT_MYSQL_PASSWORD', 'Sadp0685010452')
MYSQL_DATABASE = os.environ.get('CAT_MYSQL_DATABASE', 'cat_study_app')



class Connection:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        cur.execute(_to_mysql_placeholders(sql), tuple(_convert_params(params)))
        return cur

    def executemany(self, sql, seq_of_params):
        cur = self._conn.cursor()
        cur.executemany(_to_mysql_placeholders(sql), [tuple(_convert_params(p)) for p in seq_of_params])
        return cur

    def executescript(self, script):
       
        cur = self._conn.cursor()
        for statement in _split_statements(script):
            cur.execute(statement)
        self._conn.commit()

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def _to_mysql_placeholders(sql):
    
    return sql.replace('?', '%s')


def _convert_params(params):
    
    return [int(p) if isinstance(p, bool) else p for p in params]


def _split_statements(script):
    
    lines = [ln for ln in script.splitlines() if not ln.strip().startswith('--')]
    cleaned = '\n'.join(lines)
    return [s.strip() for s in cleaned.split(';') if s.strip()]



def get_db():
    
    raw = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    return Connection(raw)


def _ensure_database_exists():
    
    raw = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD, autocommit=True
    )
    cur = raw.cursor()
    cur.execute(f'CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}`')
    raw.close()


def init_db():
    
    _ensure_database_exists()

    conn = get_db()
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())

    existing = conn.execute('SELECT COUNT(*) AS count FROM grades').fetchone()['count']
    if existing == 0:
        conn.executemany(
            'INSERT INTO grades (name) VALUES (?)',
            [('Grade 10',), ('Grade 11',), ('Grade 12',)]
        )
        conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print(f'Database ready: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}')
