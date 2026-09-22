# SQLite transactions don't make a CSV import safe to retry

By Abdullah · 9 September 2026

> **Disclosure:** This is an original synthetic portfolio experiment prepared with AI assistance, not a client incident. The recorded output is existing output; this sample makes no claim of a new run.

The experiment asks a small question with a clear answer: if a CSV import fails halfway through, what happens when it runs again? Three synthetic orders were enough to expose the problem. The first importer left five rows. Adding a transaction fixed that failure, but replaying a successful import still left six.

The missing piece was a record of the request, committed alongside its data. That distinction matters whenever an application cannot tell whether its previous attempt completed.

This is a reproducible local exercise, not a production incident. The accompanying [Python script](retry_demo.py) uses only the standard library, in-memory databases and invented order references. No API, customer data or payment system is involved.

## Three orders, two ways to get the wrong result

The input is deliberately ordinary:

```csv
order_ref,amount_cents
A-101,100
A-102,200
A-103,300
```

The first version opens SQLite with `isolation_level=None` and inserts each row without an explicit transaction. Under Python 3.12's default legacy transaction control, this leaves transaction boundaries to SQLite. Each standalone insert completes independently. The [Python transaction documentation](https://docs.python.org/3.12/library/sqlite3.html#transaction-control-via-the-isolation-level-attribute) describes this setting; it is an intentional choice here, not advice to rely on unspecified defaults.

After inserting the second row, the script raises an exception. Two rows remain. Running the full import again appends all three, giving five rows. Nothing tells the database that A-101 and A-102 are repeats: this first table allows duplicate references.

The next version wraps the inserts in one transaction. An exception rolls it back, leaving zero rows. A successful retry creates three. But a second successful invocation creates another three.

Here is the recorded result from Python 3.12.14 with SQLite 3.53.1:

| Importer | After injected failure | After successful retry | After another replay |
| --- | ---: | ---: | ---: |
| Separate inserts | 2 | 5 | Not run |
| One transaction | 0 | 3 | 6 |
| Transaction plus request receipt | 0 | 3 | 3 |

The second failure is more instructive. The transaction did exactly what it was supposed to do. It kept an attempt together. It had no reason to reject a completely new invocation of the same SQL.

## Give the request an identity

The third version adds two constraints. Each order reference is unique, and each import request has a stable key:

```sql
CREATE TABLE imports (
    request_key TEXT PRIMARY KEY,
    source_sha256 TEXT NOT NULL
);
```

The caller reuses `batch-1` when retrying that same import. It does not generate a fresh identifier for every attempt.

The stored digest is SHA-256 of the supplied CSV text encoded as UTF-8. It answers a narrower question than “are these logically equivalent orders?”: has the same key been used with exactly the same encoded input? That conservative choice makes changes visible. Even a newline change can be rejected. A system that wants semantic equivalence needs an explicit normalization rule.

The algorithm is short:

1. Parse and validate the small input before opening the transaction.
2. Begin the write transaction and look up the request key.
3. If the key exists with the same digest, return `already_imported` without inserting orders.
4. If the key exists with a different digest, reject the request.
5. Otherwise insert the receipt and orders, then commit them together.

The core is:

```python
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
```

`BEGIN IMMEDIATE` starts a write transaction before the receipt lookup. SQLite allows only one write transaction at a time; obtaining it up front avoids starting this decision as a read transaction and upgrading later. It can still fail with a busy database. The [SQLite transaction reference](https://www.sqlite.org/lang_transaction.html) explains that tradeoff. This example does not implement lock retries.

The important boundary is the final commit. The receipt cannot survive a rolled-back batch, and a committed batch has its receipt in the same database transaction. A receipt saved afterward would leave a gap in which the data exists but a retry cannot identify it.

## Test the receipt, not just the row count

The test injects a failure after two order inserts. Both orders and the newly inserted receipt disappear on rollback. After a successful attempt and an identical replay, there are three orders and one receipt.

Then it changes the final amount from 300 to 301 while retaining `batch-1`. The importer rejects it. The total remains 600 cents. Silently treating that request as an old success would conceal a changed input.

A final check submits the original orders under a new key, `batch-2`. The unique order references reject the collision. Crucially, the attempted receipt for `batch-2` also rolls back. This importer intentionally treats a new key containing existing orders as a conflict; it does not guess that the caller meant to retry another batch.

That is why this implementation avoids `INSERT OR IGNORE`. SQLite can skip a conflicting row and continue for several constraint types. That behavior is useful in some workflows, but it would obscure the strict “this entire new batch was accepted” contract here. See SQLite's [conflict-resolution rules](https://www.sqlite.org/lang_conflict.html).

## Where this experiment stops

Run the checks with:

```sh
python retry_demo.py
```

The program prints the observed counts after its assertions pass. [The recorded output](run-output.json) includes the runtime versions.

These checks exercise sequential calls and injected Python exceptions. They do not test power loss, file-system durability, concurrent processes or multi-database transactions. The input fits in memory. Request keys need appropriate tenant and operation scoping in a shared service, and deleting old receipts changes how long retries remain recognizable.

Most importantly, the transaction says nothing about an external side effect. Sending an email between the inserts does not make that email roll back. An outbox can record an intent to send in the same transaction, but a worker still has to handle the gap between provider acceptance and recording its response. That requires a separate delivery design.

The rule from this experiment is precise: ask what identifies the operation, what proves it committed, and whether that proof shares the transaction with the data. If one of those answers is missing, a successful rollback test is not enough to trust the retry button.

## Included files

- [retry_demo.py](retry_demo.py) — original Python experiment, copied unchanged.
- [run-output.json](run-output.json) — existing recorded output, copied unchanged.
