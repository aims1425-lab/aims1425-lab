# Data cleanup work sample

Original work by Abdullah Alsmaeel, created with AI assistance. This is a self-directed demonstration using fictional data.

## Inspect the result

| Input | Clean output | Review queue |
|---|---|---|
| [18 source records](csv-cleanup/source.csv) | [9 clean records](csv-cleanup/clean.csv) | [9 documented exceptions](csv-cleanup/exceptions.csv) |

The sample preserves leading-zero identifiers, applies explicit formatting rules, distinguishes exact and normalized duplicates, and holds conflicting records for review instead of guessing a value.

- [Rules, scope and reproduction instructions](csv-cleanup/README.md)
- [Python implementation](csv-cleanup/clean.py)
- [Verification source](csv-cleanup/verify.py) and [recorded results: 22 checks](csv-cleanup/validation.json)
- [File checksums](csv-cleanup/SHA256SUMS.txt)

It demonstrates a small fixed CSV schema. Native spreadsheet import, production-scale performance and customer delivery are outside the verified scope.

## Request a paid pilot

For a small CSV-cleanup job, send the file/row counts, required output, agreed cleaning rules and deadline through [my LinkedIn service page](https://www.linkedin.com/services/page/0a9076347398a204b5/). Scope and price are confirmed before work starts. Keep sensitive files out of public GitHub issues.
