"""A safe, in-memory SQL practice sandbox with auto-grading."""
import re
import sqlite3
import time

CUSTOMERS = [(1, "Asha", "Hyderabad", "2025-01-15"), (2, "Ben", "Mumbai", "2025-02-03"), (3, "Chitra", "Hyderabad", "2025-02-20"), (4, "Dev", "Delhi", "2025-03-11"),
             (5, "Esha", "Mumbai", "2025-04-02"), (6, "Farid", "Chennai", "2025-04-18"), (7, "Gita", "Delhi", "2025-05-07"), (8, "Hari", "Hyderabad", "2025-06-01")]
ORDERS = [(1, 1, "2025-02-01", 1200.0, "paid"), (2, 1, "2025-03-05", 800.0, "paid"), (3, 2, "2025-03-10", 450.0, "paid"), (4, 3, "2025-03-15", 300.0, "refunded"),
          (5, 3, "2025-04-01", 950.0, "paid"), (6, 4, "2025-04-12", 150.0, "paid"), (7, 5, "2025-05-02", 2200.0, "paid"), (8, 5, "2025-05-20", 600.0, "pending"),
          (9, 1, "2025-06-02", 500.0, "paid"), (10, 6, "2025-06-10", 75.0, "paid"), (11, 2, "2025-06-15", 1300.0, "paid"), (12, 7, "2025-06-20", 400.0, "pending")]
MAX_ROWS = 200
TIME_LIMIT = 1.0


class SqlError(Exception):
    pass


def build_db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.executescript("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT, signup_date TEXT);"
                    "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), order_date TEXT, amount REAL, status TEXT);")
    c.executemany("INSERT INTO customers VALUES (?,?,?,?)", CUSTOMERS)
    c.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", ORDERS)
    c.commit()
    c.execute("PRAGMA query_only = ON")
    return c


def clean_sql(sql: str) -> str:
    s = re.sub(r"--[^\n]*", "", sql or "").strip()
    s = s.rstrip(";").strip()
    if not s:
        raise SqlError("Write a query first.")
    if ";" in re.sub(r"'[^']*'", "", s):
        raise SqlError("Run one statement at a time.")
    if not re.match(r"(?i)^(select|with)\b", s):
        raise SqlError("Only SELECT queries (or WITH ... SELECT) are allowed in the sandbox.")
    return s


def run_query(sql: str, max_rows: int = MAX_ROWS) -> dict:
    s = clean_sql(sql)
    conn = build_db()
    start = time.time()
    conn.set_progress_handler(lambda: 1 if time.time() - start > TIME_LIMIT else 0, 10000)
    try:
        cur = conn.execute(s)
        rows = cur.fetchmany(max_rows + 1)
        cols = [d[0] for d in cur.description or []]
    except sqlite3.Error as e:
        raise SqlError("Query stopped: it took too long." if "interrupted" in str(e) else f"SQL error: {e}") from None
    finally:
        conn.close()
    return {"columns": cols, "rows": [list(r) for r in rows[:max_rows]], "truncated": len(rows) > max_rows}


def _norm(rows, ordered: bool):
    out = [tuple(round(v, 2) if isinstance(v, float) else v for v in r) for r in rows]
    return out if ordered else sorted(out, key=repr)


def grade(user_sql: str, solution_sql: str, ordered: bool) -> dict:
    user = run_query(user_sql)
    expected = run_query(solution_sql)
    u, e = _norm(user["rows"], ordered), _norm(expected["rows"], ordered)
    if u == e:
        return {"ok": True, "message": "Correct! Your result matches the expected answer.", "result": user}
    if len(u) != len(e):
        msg = f"Not quite: your query returned {len(u)} row(s) but {len(e)} were expected."
    elif len(user["columns"]) != len(expected["columns"]):
        msg = f"Not quite: expected {len(expected['columns'])} column(s) but got {len(user['columns'])}."
    elif ordered and sorted(u, key=repr) == sorted(e, key=repr):
        msg = "Right rows, wrong order. Check your ORDER BY."
    else:
        msg = "Right number of rows, but some values differ. Check your filter or calculation."
    return {"ok": False, "message": msg, "result": user}
