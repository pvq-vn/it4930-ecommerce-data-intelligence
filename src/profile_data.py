"""Read-only structural profiling. Uses Python standard library only."""
from pathlib import Path
from collections import Counter
import json
import hashlib

ROOT = Path(__file__).resolve().parents[1]

def is_empty(value):
    return value is None or value == '' or value == [] or value == {}

def main():
    manifest = json.loads((ROOT / 'docs/input_manifest.json').read_text(encoding='utf-8'))
    results = []
    for item in manifest:
        path = ROOT / item['path']
        rows, errors, line_numbers = [], [], []
        with path.open(encoding='utf-8') as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    errors.append({'line': number, 'error': 'Blank line'})
                    continue
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError('Top-level JSON is not an object')
                    rows.append(value)
                    line_numbers.append(number)
                except (ValueError, TypeError) as exc:
                    errors.append({'line': number, 'error': str(exc)})
        keys = sorted({key for row in rows for key in row})
        fields = {}
        for key in keys:
            fields[key] = {
                'types': dict(Counter(type(row[key]).__name__ for row in rows if key in row)),
                'absent': sum(key not in row for row in rows),
                'empty': sum(is_empty(row[key]) for row in rows if key in row),
            }
        ids = {}
        for key in ('product_id_raw', 'parent_product_id_raw', 'variant_sku_raw', 'review_id_raw'):
            if key in keys:
                values = [row[key] for row in rows if key in row and not is_empty(row[key])]
                ids[key] = {'nonempty': len(values), 'distinct': len(set(values))}
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        result = {
            'file': item['path'], 'records': len(rows), 'errors': errors,
            'sha256': digest, 'matches_packaged_sha256': digest == item['sha256'],
            'matches_packaged_record_count': len(rows) == item['records'],
            'field_count_distribution': dict(Counter(len(row) for row in rows)),
            'fields': fields, 'keys': ids,
            'exact_duplicate_excess': len(rows) - len({json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows}),
        }
        results.append(result)
        print(f"{path.name}: {len(rows)} records, {len(errors)} errors")
    output = ROOT / 'reports'
    output.mkdir(exist_ok=True)
    (output / 'data_profile.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    text = ['# Data profile', '', 'Structural checks only; no raw edits or semantic validation.', '',
            '| File | Records | JSON errors | Exact duplicate excess | Hash matches |', '| --- | ---: | ---: | ---: | --- |']
    for result in results:
        text.append(f"| {result['file']} | {result['records']} | {len(result['errors'])} | {result['exact_duplicate_excess']} | {result['matches_packaged_sha256']} |")
    for result in results:
        text.extend(['', f"## {result['file']}", '', '| Field | Types | Absent | Empty |', '| --- | --- | ---: | ---: |'])
        for key, values in result['fields'].items():
            text.append(f"| {key} | {values['types']} | {values['absent']} | {values['empty']} |")
    (output / 'data_profile.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
    print('Done. See reports/data_profile.md and reports/data_profile.json')
    if any(x['errors'] or not x['matches_packaged_sha256'] or not x['matches_packaged_record_count'] for x in results):
        raise SystemExit(1)

if __name__ == '__main__':
    main()
