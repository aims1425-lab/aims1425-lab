# Synthetic data cleaning demonstration

An original sample created with AI assistance. Every item, code and quantity is invented. This is a demonstration, not client work or a report about real inventory.

The source contains 18 data-entry records for a fictional supplies list. The intended clean grain is one row per item code. `source_record` identifies the original data record, starting at 1 after the CSV header.

## Cleaning rules

1. Remove surrounding whitespace. Also collapse repeated whitespace inside item names. Preserve the remaining spelling.
2. Treat `item_code` and `storage_bin` as text. Item codes must have exactly five digits. Optional bin codes must have exactly four digits. Preserve leading zeroes; do not pad short codes or guess absent codes.
3. Map category spelling by case only to `Office`, `Storage` or `Accessories`. Flag any other category without guessing its meaning.
4. Require item code, item name, category and quantity. Quantity must be a nonnegative whole number. Normalize numeric quantity text such as `03` to `3`. Keep a real zero as zero. Keep missing quantities missing and exclude their rows. Leave an optional missing bin blank.
5. Compare all normalized fields for repeated valid item codes. If values conflict, exclude every record in the group for manual review. A valid-looking record cannot override its conflicting partner, even if that partner has a blank quantity.
6. For otherwise valid, identical normalized records, retain the first source record. Log a later record as `exact_duplicate` when its original fields are identical, or `normalized_duplicate` when only approved formatting differences remain. Similar descriptions under different codes are separate items.

`clean.csv` records the source record and changed field names. `exceptions.csv` preserves each excluded record's original field values, reason and related record numbers. `conflicting_identifier` requires an owner decision. Missing or invalid fields require a source correction; no value has been inferred.

## Verified result

- 18 source records = 9 clean records + 9 exception records, each appearing exactly once.
- One exact duplicate and one duplicate after normalization were removed from the clean output.
- Two records share conflicting quantities for item `00020`; both remain unresolved.
- Five other records have a missing or invalid required field/category.
- Clean quantity totals 41. As an audit of row disposition only, known source quantities total 75 = 41 clean + 34 excluded. These raw totals include duplicate and invalid records, including a negative quantity. They are not inventory totals. One source quantity is blank and remains blank.

`validation.json` contains the actual executed checks, including independent expected record sets, raw-value preservation, quantity controls, adversarial duplicate cases and byte-identical repeat output.

## Files and reproducibility

Read `source.csv`, `clean.csv` and `exceptions.csv` together. `clean.py` reproduces the two outputs; `verify.py` checks them and writes `validation.json`. Both require Python 3 and its standard library only. From this directory, run `python -B clean.py`, then `python -B verify.py`. `SHA256SUMS.txt` identifies the packaged files.

CSV files do not carry column types. To retain leading zeroes in spreadsheet software, use its CSV import workflow and explicitly set `item_code`, `storage_bin` and corresponding raw columns to **Text**. Quoting alone does not prevent automatic numeric conversion. The files preserve these identifiers as strings; native spreadsheet import has not been tested.

Scope is this small, fixed-schema synthetic example. No real buyer data, external validation, fuzzy matching, OCR, production-scale performance or customer delivery is claimed. No PDF or XLSX is included.
