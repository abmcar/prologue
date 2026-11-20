#!/usr/bin/env bash
# Generate the plans of the six example codes and the CREATE2 records of the three example codes, and compare them with
# the files of the library measured in the paper. usage: plans/example/check.sh [WORKDIR]
set -euo pipefail
H=$(cd "$(dirname "$0")/.." && pwd); W=${1:-$(mktemp -d)}
"$H/build_library.sh" "$H/example/codes.tsv" "$W/lib" > "$W/build.log" 2>&1 || { tail "$W/build.log"; exit 1; }
(cd "$W/lib/plans" && sha256sum -c "$H/example/expected_plans.sha256")
${PYTHON:-python3} "$H/create2/c2sweep.py" "$H/example/create2_codes.tsv" 0 1 "$W/c2" > "$W/c2.log"
${PYTHON:-python3} - "$W/c2/c2records" "$H/example/expected_c2records" <<'PY'
import json, os, sys
a, b = sys.argv[1:]
for n in sorted(os.listdir(b)):
    x, y = json.load(open(f'{a}/{n}')), json.load(open(f'{b}/{n}'))
    x.pop('secs', None); y.pop('secs', None)   # wall-clock time of the analysis
    print(n, 'OK' if x == y else 'DIFFERENT'); assert x == y
PY
