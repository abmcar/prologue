#!/usr/bin/env bash
# Generate access plans for the codes of a code table that a base plan library lacks, and assemble the completed library.
#   1. generate/prep222.py          codes without a plan in BASE_LIB -> WORK/codes/<codehash>.hex, WORK/jobs<i>.json
#   2. generate/eap_plan_gen_x23.py static analysis of each code (analyzer/), one summary per code -> WORK/sum
#   3. generate/eap_plan_export_calls_v3.py   summaries -> plan files -> WORK/plans_new
#   4. generate/merge229.py         merge of equivalent loop-call groups -> WORK/plans_new_m
#   5. WORK/plans = BASE_LIB's files plus WORK/plans_new_m, with a MANIFEST (file count, hash of the sorted file list,
#      hash of the sorted `sha256sum` lines); evaluator/fpct3 --check reads every plan back when the tool is built.
# usage: plans/build_library.sh CODES_TSV WORK [BASE_LIB] [NSHARDS=1]
#   CODES_TSV  header line, then `codehash<TAB>bytecode hex` per line (the node writes one with EAP_CODES_OUT)
#   BASE_LIB   directory of existing <codehash>.eapf files (default: an empty library)
# Environment: PYPY (default pypy3, else python3) runs steps 2 and 4; PYTHON (default python3) the others.
# The settings are those of the library measured in the paper: chain v1e10, work cap 209644284, 3,000,000 steps,
# AFFINE_MEM=1, SAS_MASKED_CALL=1, PYTHONHASHSEED=0, chunks of 100 codes per analyzer process.
set -euo pipefail
H=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "$1"); W=$(realpath -m "$2"); NSH=${4:-1}
PYTHON=${PYTHON:-python3}; PYPY=${PYPY:-$(command -v pypy3 || echo python3)}
mkdir -p "$W/sum" "$W/plans_new" "$W/empty_base"
BASE=$(realpath "${3:-$W/empty_base}")
csha() { (cd "$1" && find . -maxdepth 1 -name '*.eapf' -printf '%f\n' | LC_ALL=C sort | xargs -r sha256sum | sha256sum | cut -c1-64); }
"$PYTHON" "$H/generate/prep222.py" "$SRC" "$BASE" "$W" "$NSH" | tee "$W/prep.json"
ulimit -n 65536 2>/dev/null || true
for i in $(seq 0 $((NSH - 1))); do
  ( T=$(mktemp -d "$W/.chunks$i.XXXX")
    "$PYTHON" -c "
import json, sys
hs = json.load(open(sys.argv[1]))
for i in range(0, len(hs), 100): json.dump(hs[i:i + 100], open(f'{sys.argv[2]}/c{i // 100:04d}.json', 'w'))" "$W/jobs$i.json" "$T"
    for c in "$T"/c*.json; do
      [ -e "$c" ] || continue
      EAP_CODES="$W/codes" SAS_MASKED_CALL=${SAS_MASKED_CALL:-1} AFFINE_MEM=1 PYTHONHASHSEED=0 "$PYPY" "$H/generate/eap_plan_gen_x23.py" \
        produce "$c" "$W/sum" "$W/gen_$i.csv" --chain v1e10 --max-work 209644284 --wk 100,8,17,33,957,4,14,0,0 --max-steps 3000000
    done; rm -rf "$T" ) > "$W/gen_$i.log" 2>&1 &
done
wait
"$PYTHON" - "$W" <<'PY'
import csv, glob, sys, collections
w = sys.argv[1]; ok = set(); err = collections.Counter()
for f in glob.glob(f'{w}/gen_*.csv'):
    for r in csv.DictReader(open(f)):
        if r['error']: err[r['error'][:60]] += 1
        else: ok.add(r['id'])
open(f'{w}/gen_ok.txt', 'w').write(''.join(h + '\n' for h in sorted(ok)))
print('analysis ok', len(ok), 'errors', sum(err.values()), dict(err.most_common(5)))
PY
SUMMARY_DIRS="$W/sum" CODES_DIRS="$W/codes${CODES_DIRS:+:$CODES_DIRS}" "$PYTHON" "$H/generate/eap_plan_export_calls_v3.py" \
  "$W/gen_ok.txt" "$W/plans_new" "$W/export.csv" --nproc 1 --unkval > "$W/export.log" 2>&1
tail -n 2 "$W/export.log"
mkdir -p "$W/plans_new_m"
"$PYPY" "$H/generate/merge229.py" "$W/plans_new" "$W/plans_new_m" "$W/merge.csv" > "$W/merge.log" 2>&1
rm -rf "$W/plans"; mkdir -p "$W/plans"
find "$BASE" -maxdepth 1 -name '*.eapf' -exec cp -t "$W/plans/" {} +
for f in "$W"/plans_new_m/*.eapf; do [ -e "$W/plans/$(basename "$f")" ] || cp "$f" "$W/plans/"; done
N=$(find "$W/plans" -maxdepth 1 -name '*.eapf' | wc -l)
L=$(find "$W/plans" -maxdepth 1 -name '*.eapf' -printf '%f\n' | sort | sha256sum | cut -c1-64)
printf 'files\t%s\nlist_sha256\t%s\ncontent_sha256\t%s\n' "$N" "$L" "$(csha "$W/plans")" | tee "$W/plans/MANIFEST"
F="$H/evaluator/fpct3/target/release/fpct3"
if [ -x "$F" ]; then "$F" --check "$W/plans" > "$W/check.tsv"
  awk -F'\t' 'NR > 1 { n++; if ($8 != 1) bad++ } END { print "checked", n, "round-trip failures", bad + 0 }' "$W/check.tsv"
else echo "evaluator/fpct3 is not built; skipping the read-back check"; fi
