"""Independent fixture expectations and adversarial checks for this small demo."""
import csv
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from clean import FIELDS, clean_rows, run

ROOT = Path(__file__).parent
checks = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


source = read(ROOT / 'source.csv')
clean = read(ROOT / 'clean.csv')
exceptions = read(ROOT / 'exceptions.csv')
check('18 source records', len(source) == 18)
check('9 clean and 9 exception records', (len(clean), len(exceptions)) == (9, 9))
check('every source record appears exactly once across both outputs',
      Counter(int(row['source_record']) for row in clean + exceptions) == Counter(range(1, 19)))
expected_clean = {1, 2, 3, 10, 12, 15, 16, 17, 18}
check('clean record set equals independently specified fixture', {int(row['source_record']) for row in clean} == expected_clean)
expected_reasons = {4: 'exact_duplicate', 5: 'conflicting_identifier', 6: 'conflicting_identifier',
                    7: 'missing_item_code', 8: 'missing_quantity', 9: 'invalid_quantity',
                    11: 'normalized_duplicate', 13: 'unmapped_category', 14: 'missing_item_name'}
check('all expected exceptions have exact reasons', {int(row['source_record']): row['reasons'] for row in exceptions} == expected_reasons)
check('exception raw payloads exactly preserved', all(
    {field: row['raw_' + field] for field in FIELDS} == source[int(row['source_record']) - 1] for row in exceptions))
by_record = {int(row['source_record']): row for row in clean + exceptions}
check('duplicates point to their retained source records', by_record[4]['related_source_records'] == '3' and by_record[11]['related_source_records'] == '10')
check('conflicting pair points to each other and never enters clean output',
      by_record[5]['related_source_records'] == '6' and by_record[6]['related_source_records'] == '5' and
      '00020' not in {row['item_code'] for row in clean})
check('clean identifiers remain unique strings with leading zeroes',
      len({row['item_code'] for row in clean}) == 9 and all(isinstance(row['item_code'], str) and len(row['item_code']) == 5 and row['item_code'].startswith('0') for row in clean))
check('identifier and bin characters preserved after outer whitespace removal', all(
    row['item_code'] == source[int(row['source_record']) - 1]['item_code'].strip() and
    row['storage_bin'] == source[int(row['source_record']) - 1]['storage_bin'].strip() for row in clean))
check('zero stays zero; missing quantity remains missing in exceptions', by_record[2]['quantity'] == '0' and by_record[8]['raw_quantity'] == '')
check('optional blank bin stays blank', by_record[18]['storage_bin'] == '')
check('declared whitespace/category/quantity transformations occur',
      by_record[1]['item_name'] == 'Cable tray' and by_record[2]['category'] == 'Office' and by_record[10]['quantity'] == '3')
check('changed_fields accurately identifies every changed source field', all(
    row['changed_fields'].split(';') == [field for field in FIELDS if row[field] != source[int(row['source_record']) - 1][field]]
    if row['changed_fields'] else all(row[field] == source[int(row['source_record']) - 1][field] for field in FIELDS) for row in clean))
check('clean quantity control total is independently expected 41', sum(int(row['quantity']) for row in clean) == 41)
known_source_quantity = sum(int(row['quantity']) for row in source if row['quantity'].strip())
exception_quantity = sum(int(row['raw_quantity']) for row in exceptions if row['raw_quantity'].strip())
check('known source quantities reconcile without imputing the blank', known_source_quantity == 75 and exception_quantity == 34 and known_source_quantity == 41 + exception_quantity)

# These changes test decisions not present together in the delivered fixture.
base = dict(item_code='00101', item_name='Demo item', category='office', quantity='2', storage_bin='0001')
out, exc = clean_rows([base, dict(base, quantity='')])
check('valid row is also withheld when its duplicate key has a missing quantity', not out and len(exc) == 2 and all('conflicting_identifier' in row['reasons'] for row in exc))
out, exc = clean_rows([base, dict(base), dict(base, quantity='3')])
check('an exact duplicate within a conflict group cannot silently survive', not out and len(exc) == 3 and all('conflicting_identifier' in row['reasons'] for row in exc))
out, exc = clean_rows([base, dict(base, item_code='101')])
check('short identifiers are not padded or merged', len(out) == 1 and len(exc) == 1 and exc[0]['reasons'] == 'invalid_item_code')
out, exc = clean_rows([base, dict(base, item_code='00102')])
check('same description under different valid identifiers is not deduplicated', len(out) == 2 and not exc)
before_source = digest(ROOT / 'source.csv')
with tempfile.TemporaryDirectory(prefix='verify-', dir=ROOT) as temporary:
    run(ROOT / 'source.csv', temporary)
    check('repeat run produces byte-identical clean and exception CSVs', all(
        (ROOT / name).read_bytes() == (Path(temporary) / name).read_bytes() for name in ['clean.csv', 'exceptions.csv']))
check('verification leaves source bytes unchanged', digest(ROOT / 'source.csv') == before_source)
result = dict(status='passed', checks_passed=len(checks), checks=checks, source_records=18,
              clean_records=9, exception_records=9, exceptions_by_reason=dict(Counter(row['reasons'] for row in exceptions)),
              clean_quantity=41, known_source_quantity=75, known_exception_quantity=34, missing_source_quantity_records=1,
              source_sha256=before_source, limitations=['Synthetic fixed-schema demo only.',
              'CSV has no stored column types: import item_code and storage_bin as Text in spreadsheet software.',
              'No native spreadsheet import or visual review was performed.'])
(ROOT / 'validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
