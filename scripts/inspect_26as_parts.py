import collections
import glob
import json
import os

fs = glob.glob(r'ais_extractor/test_output_26as/*.json')
c = collections.Counter()
keys = {}
examples = {}
for f in fs:
    d = json.load(open(f, encoding='utf-8'))
    for p, v in d.get('parts', {}).items():
        rows = v.get('rows') or []
        c[p] += len(rows)
        if rows:
            keys.setdefault(p, set()).update(rows[0])
            examples.setdefault(p, (os.path.basename(f), rows[0]))
print('PART ROW COUNTS', dict(c))
for p in sorted(keys):
    print('PART', p, 'KEYS', sorted(keys[p]))
    print('  EXAMPLE', examples[p][0])
    print('  ROW', examples[p][1])
