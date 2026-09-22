"""Original synthetic CSV cleaning demonstration. Standard library only."""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

FIELDS = ['item_code', 'item_name', 'category', 'quantity', 'storage_bin']
CATEGORIES = {'office': 'Office', 'storage': 'Storage', 'accessories': 'Accessories'}


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError('Unexpected source columns or order')
        rows = list(reader)
    if any(set(row) != set(FIELDS) or None in row.values() for row in rows):
        raise ValueError('Malformed source row; no outputs written')
    return rows


def clean_rows(rows):
    prepared, groups = [], defaultdict(list)
    for record, raw in enumerate(rows, 1):
        normalized = {field: raw[field].strip() for field in FIELDS}
        normalized['item_name'] = ' '.join(normalized['item_name'].split())
        normalized['category'] = CATEGORIES.get(normalized['category'].casefold(), normalized['category'])
        if re.fullmatch(r'[0-9]+', normalized['quantity']):
            normalized['quantity'] = str(int(normalized['quantity']))
        issues = []
        for field in ['item_code', 'item_name', 'category', 'quantity']:
            if not normalized[field]:
                issues.append('missing_' + field)
        if normalized['item_code'] and not re.fullmatch(r'[0-9]{5}', normalized['item_code']):
            issues.append('invalid_item_code')
        if normalized['quantity'] and not re.fullmatch(r'[0-9]+', normalized['quantity']):
            issues.append('invalid_quantity')
        if normalized['category'] and normalized['category'] not in CATEGORIES.values():
            issues.append('unmapped_category')
        if normalized['storage_bin'] and not re.fullmatch(r'[0-9]{4}', normalized['storage_bin']):
            issues.append('invalid_storage_bin')
        item = dict(record=record, raw=raw, normalized=normalized, issues=issues)
        prepared.append(item)
        if re.fullmatch(r'[0-9]{5}', normalized['item_code']):
            groups[normalized['item_code']].append(item)

    clean, exceptions, retained = [], [], {}
    for item in prepared:
        record, raw, normalized = item['record'], item['raw'], item['normalized']
        group = groups.get(normalized['item_code'], [])
        variants = {tuple(member['normalized'][field] for field in FIELDS) for member in group}
        reasons, related = list(item['issues']), ''
        # A conflict blocks every row in the group, including a superficially valid one.
        if len(variants) > 1:
            reasons.insert(0, 'conflicting_identifier')
            related = ';'.join(str(member['record']) for member in group if member['record'] != record)
        elif not reasons and normalized['item_code'] in retained:
            first = retained[normalized['item_code']]
            reasons = ['exact_duplicate' if raw == first['raw'] else 'normalized_duplicate']
            related = str(first['record'])
        if reasons:
            exceptions.append(dict(source_record=str(record), reasons=';'.join(reasons),
                                   related_source_records=related, **{'raw_' + k: v for k, v in raw.items()}))
        else:
            retained[normalized['item_code']] = item
            changes = ';'.join(field for field in FIELDS if raw[field] != normalized[field])
            clean.append(dict(source_record=str(record), **normalized, changed_fields=changes))
    return clean, exceptions


def write_csv(path, columns, rows):
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, quoting=csv.QUOTE_ALL, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def run(source, output):
    rows = read_csv(source)
    clean, exceptions = clean_rows(rows)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / 'clean.csv', ['source_record'] + FIELDS + ['changed_fields'], clean)
    write_csv(output / 'exceptions.csv', ['source_record', 'reasons', 'related_source_records'] +
              ['raw_' + field for field in FIELDS], exceptions)
    return len(rows), len(clean), len(exceptions)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).with_name('source.csv'))
    parser.add_argument('--output', type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    print('source, clean, exceptions:', run(args.source, args.output))
