import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"


def _mysql_config():
    # WeChat Cloud Run injects MYSQL_ADDRESS=host:port
    address = os.environ.get("MYSQL_ADDRESS")
    if not address:
        return None
    if ":" in address:
        host, port = address.split(":", 1)
        port = int(port)
    else:
        host, port = address, 3306
    return {
        "host": host,
        "port": port,
        "user": os.environ.get("MYSQL_USERNAME", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": os.environ.get("MYSQL_DATABASE", "doudoutu"),
        "charset": "utf8mb4",
        "autocommit": False,
        "cursorclass": None,  # set below after import
    }


USE_MYSQL = _mysql_config() is not None


class _SQLiteConnection:
    def __init__(self, path):
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row

    def execute(self, sql, params=()):
        return self._conn.execute(sql, params)

    def executemany(self, sql, seq):
        return self._conn.executemany(sql, seq)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        self.close()
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        self.close()
        return False

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _MySQLConnection:
    def __init__(self, config):
        import pymysql
        from pymysql.cursors import DictCursor
        cfg = dict(config)
        cfg["cursorclass"] = DictCursor
        self._conn = pymysql.connect(**cfg)

    @staticmethod
    def _translate(sql):
        return sql.replace("?", "%s")

    def execute(self, sql, params=()):
        with self._conn.cursor() as cursor:
            cursor.execute(self._translate(sql), params)
            return cursor

    def executemany(self, sql, seq):
        with self._conn.cursor() as cursor:
            cursor.executemany(self._translate(sql), seq)
            return cursor

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg = _mysql_config()
    if cfg:
        return _MySQLConnection(cfg)
    return _SQLiteConnection(DB_PATH)


def placeholder():
    return "%s" if USE_MYSQL else "?"


def ensure_column(connection, table, column, column_type):
    if USE_MYSQL:
        sql = (
            "SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s"
        )
        row = connection.execute(sql, (table, column)).fetchone()
        exists = list(row.values())[0] if isinstance(row, dict) else row[0]
        if not exists:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
    else:
        columns = [r["name"] for r in connection.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
