# frame-plan: the access-plan file format and its evaluator

This crate loads access plans (`.eapf` files, format versions 1 to 3) and evaluates a plan for one call frame:
given the call's input data, caller, value and the block environment, it returns the storage keys the frame will read
and the calls it will make (target and arguments), following the plan's path conditions and loop families.

- `src/lib.rs`: `Plan::parse` / `Plan::to_bytes`, `Scratch`, `instantiate`, `instantiate_calls`; unit tests in the
  same file (`cargo test --lib`).
- `src/bin/fp_run.rs`: reads frames and prints the predicted keys, for differential checks against the Python
  reference (`plans/analyzer/predict.py`) and for timing.
- `../fpct3`: reads frames on stdin and prints keys and calls; `fpct3 --check DIR` parses every plan of a library
  and writes it back, reporting plans that do not round-trip.

The node uses its own copy of this evaluator, `crates/frame-plan` in the reth patch.

File versions: version 1 holds storage groups (key expressions over call data and environment fields), their path
conditions as alternative sets, and loop families with at most two indices; version 2 adds call groups without a loop
index (kind, target expression, argument words); version 3 adds call groups that depend on a loop index.
