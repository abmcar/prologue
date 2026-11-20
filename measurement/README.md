# Measurement scripts

These are the scripts as they ran on the measurement servers. They assume the layout of those servers, and their
comments carry labels of the form `EXP-nnn` and `X-nnn`, which refer to the authors' development log; several checks
in `run/pre257.sh` look for such labels in the driver, so they are left in place.

| Directory | Contents |
|---|---|
| `replay/` | `replay.py`: Engine API client (`engine_newPayloadV4`, `engine_forkchoiceUpdatedV3`, timing of each call). `fetch.py`: beacon blocks to payload files |
| `driver/` | The per-block driver: `run_f.sh` (one run: passes, restore, cache eviction, checks), `session_f.sh`, `start_node.sh` (the reth command line), `run_xl_f.py` (rows and their control lines, block loop, waits, counters), `parse.py` (records to `blocks_*.csv`), `evict_cache.py`, `sched4_199.py` and `pairsched199.py` (block schedules) |
| `host/` | Server setup (`machine_setup.sh`: users, core assignment, `machine.env`), the run wrapper with the memory limit (`prologue_run.sh`), database copies (`make_base.sh`, `forward.sh`, `restore_reflink.sh`), block download and check (`fetch_blocks.sh`, `verify_blocks.py`), build (`build290.sh`), block classification (`prologue_classify.py`) |
| `run/` | `main270.sh` (one node process of a column and segment), `seq270.sh` (a machine's sequence of processes), `pre257.sh` (checks before a run), `check270.py` (checks after a run), `fio257.sh` (read latency of a device), `schedule_runs3.py` (row rotation of the ablation) |
| `block_classes.csv` | Class of each block 26,299,455–26,340,032: `cls_mint` is `mint` for batch-mint blocks and `nomint` for regular blocks |

Layout the scripts expect:

| Path on a server | Contents | In this repository |
|---|---|---|
| `/prologue/bin/` | reth binaries | built from `reth/` |
| `/prologue/data/plans_269`, `/prologue/data/c2rec_270` | plan library, CREATE2 records | `plans/` |
| `/prologue/scripts/` | host scripts | `measurement/host/` |
| `/prologue/engine-replay/` | replay client | `measurement/replay/` |
| `$PROLOGUE_DRIVER` | driver | `measurement/driver/` |
| `$PROLOGUE_REPO/experiments/EXP-270-final-measurement/scripts/`, `.../EXP-257-main-measurement/scripts/` | run scripts | `measurement/run/` |
| `$PROLOGUE_REPO/experiments/EXP-240-e2e-after-exec/results/prologue_class_26299455_26340032.csv` | block classes | `measurement/block_classes.csv` |
| `/data/node/base-<N>`, `/data/node/accflt-<N>.bin` | node database at block N and its account filter | made by `host/make_base.sh` |
| `/data/node/home` | the node's working directory, restored from a base before every pass | |
| `/work/runs/<run>/{raw,results}` | output of a run | `results/main/raw/<run>/` holds the block tables |

Order of the steps on a new server: `host/machine_setup.sh`; build the two binaries (`host/build290.sh`); download
the blocks (`host/fetch_blocks.sh`) and check them (`host/verify_blocks.py`); make the base of each segment
(`host/make_base.sh`, `host/forward.sh`); run the processes (`run/seq270.sh "up:0 ur:0 un:0 pn:0"`); check each run
(`run/check270.py`). `host/machine_setup.sh` assigns the last two physical cores to the driver and the rest to the node.
On our servers `machine_setup.sh` also generated the driver from a base version and a series of edits; `driver/` is
the generated result, so that step (the last lines of the script) is skipped. The attachment of the network volumes
for the storage comparison was done by hand and is not scripted here.

A base is restored with `cp --reflink=always`, so the database file system must be XFS with reflink. Before each pass
the driver calls `posix_fadvise(DONTNEED)` on every database file, starts the node, and replays the blocks; after each
block it waits until the node has been idle for 50 ms, at least 0.25 s and at most 5 s.
