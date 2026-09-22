"""Reproduce CSV retry behavior locally. Python standard library only.

All data is synthetic. No network calls, external services or persistent DBs.
"""

import csv
import hashlib
import io
import json
import platform
import sqlite3


SOURCE = "order_ref,amount_cents\nA-101,100\nA-102,200\nA-103,300\n"


class InjectedFailure(Exception):
    pass


def rows_from(text):
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != ["order_ref", "amount_cents"]:
        raise ValueError("Unexpected CSV header")
    rows = []
    for row in reader:
        if set(row) != {"order_ref", "amount_cents"}:
            raise ValueError("Unexpected CSV fields")
        ref = row["order_ref"]
        cents = int(row["amount_cents"])
        if not ref or cents < 0:
            raise ValueError("Invalid order")
        rows.append((ref, cents))
    return rows


def connect(unique=False):
    db = sqlite3.connect(":memory:", isolation_level=None)
    key = " PRIMARY KEY" if unique else " NOT NULL"
    db.execute(
        f"CREATE TABLE orders (order_ref TEXT{key}, "
        "amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0))"
    )
    db.execute(
        "CREATE TABLE imports (request_key TEXT PRIMARY KEY, "
        "source_sha256 TEXT NOT NULL)"
    )
    return db


def count(db, table="orders"):
    if table not in {"orders", "imports"}:
        raise ValueError("Unknown table")
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def insert_rows(db, rows, fail_after=None):
    for position, row in enumerate(rows, start=1):
        db.execute("INSERT INTO orders VALUES (?, ?)", row)
        if position == fail_after:
            raise InjectedFailure("Simulated interruption after row insertion")


def row_by_row(db, text, fail_after=None):
    # With isolation_level=None and no BEGIN, each INSERT commits separately.
    insert_rows(db, rows_from(text), fail_after)


def atomic_only(db, text, fail_after=None):
    rows = rows_from(text)
    db.execute("BEGIN IMMEDIATE")
    try:
        insert_rows(db, rows, fail_after)
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise


def import_once(db, request_key, text, fail_after=None):
    if not request_key:
        raise ValueError("A stable request key is required")
    rows = rows_from(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    db.execute("BEGIN IMMEDIATE")
    try:
        previous = db.execute(
            "SELECT source_sha256 FROM imports WHERE request_key = ?",
            (request_key,),
        ).fetchone()
        if previous is not None:
            if previous[0] != digest:
                raise ValueError("Request key reused for different file bytes")
            db.execute("COMMIT")
            return "already_imported"
        db.execute("INSERT INTO imports VALUES (?, ?)", (request_key, digest))
        insert_rows(db, rows, fail_after)
        db.execute("COMMIT")
        return "imported"
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise


def expect(exception, operation):
    try:
        operation()
    except exception:
        return
    raise AssertionError(f"Expected {exception.__name__}")


def main():
    results = {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version}

    db = connect()
    expect(InjectedFailure, lambda: row_by_row(db, SOURCE, fail_after=2))
    assert count(db) == 2
    row_by_row(db, SOURCE)
    assert count(db) == 5
    results["row_by_row"] = {"after_failure": 2, "after_retry": 5}
    db.close()

    db = connect()
    expect(InjectedFailure, lambda: atomic_only(db, SOURCE, fail_after=2))
    assert count(db) == 0
    atomic_only(db, SOURCE)
    assert count(db) == 3
    atomic_only(db, SOURCE)
    assert count(db) == 6
    results["atomic_only"] = {"after_failure": 0, "after_success": 3, "after_replay": 6}
    db.close()

    db = connect(unique=True)
    expect(InjectedFailure, lambda: import_once(db, "batch-1", SOURCE, fail_after=2))
    assert (count(db), count(db, "imports")) == (0, 0)
    assert import_once(db, "batch-1", SOURCE) == "imported"
    assert import_once(db, "batch-1", SOURCE) == "already_imported"
    assert (count(db), count(db, "imports")) == (3, 1)
    expect(ValueError, lambda: import_once(db, "batch-1", SOURCE.replace("300", "301")))
    assert db.execute("SELECT SUM(amount_cents) FROM orders").fetchone()[0] == 600
    expect(sqlite3.IntegrityError, lambda: import_once(db, "batch-2", SOURCE))
    assert (count(db), count(db, "imports")) == (3, 1)
    results["atomic_receipt"] = {
        "after_failure": {"orders": 0, "receipts": 0},
        "after_success_and_replay": {"orders": 3, "receipts": 1},
        "changed_bytes_same_key": "rejected_without_changes",
        "existing_orders_new_key": "rejected_without_orphan_receipt",
        "total_cents": 600,
    }
    db.close()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
