# Prologue

Prologue is a block-execution runtime for the reth Ethereum client that issues a storage read as soon as its key is
determined. At compile time it derives one *access plan* per contract code: the expressions of the keys the code reads
and the conditions under which it reads them, as functions of a call's inputs. At run time, pre-execution threads
evaluate the plan of every call when the call starts and hand the keys to reader threads, which load them from the
database while the execution thread is still working on earlier transactions.

This repository holds the implementation on reth 2.9.0, the plan analyzer and generator, the scripts that drive the
measurements, and the data and scripts behind every figure and table of the paper.

## Contents and the paper

| Directory | Contents | Paper |
|---|---|---|
| `reth/` | Prologue as patches to reth v2.9.0 and to reth's EVM and compiler (evm2), with a script that applies them and checks the result | Sections 4–6 |
| `plans/analyzer/` | Static analyzer of EVM bytecode (symbolic execution that records the key expression and path condition of every storage read and the target and arguments of every call), with its tests | Section 4.2 |
| `plans/generate/` | Plan generation: analysis, export to plan files, merge of equivalent loop-call groups | Section 4.2 |
| `plans/create2/` | Records of how contracts compute CREATE2 salts, used to predict the addresses of contracts a batch transaction creates | Section 4.4 |
| `plans/evaluator/` | Plan file format and offline evaluator in Rust (the node carries its own copy, `crates/frame-plan`) | Section 4.3 |
| `measurement/` | Block replay client, per-block driver, host setup and run scripts of the node measurements; the block classification | Section 7.1 |
| `results/main/` | Per-block tables of every node process, the analysis scripts and their outputs | Sections 7.3–7.7, Tables 2–4 |
| `results/blockreads/` | Slot reads of each of the 10,000 measured blocks | Section 7.4, Figure 8 |
| `paper/` | Figure sources, figure data, and the scripts that compute the data and the numbers in the text | all figures and tables |

Figures and tables:

| | Source | Data | Computed by |
|---|---|---|---|
| Figure 1 (the reads of one call under prewarming and under Prologue) | `paper/fig/binding.tex` | diagram | |
| Figure 2 (execution time without and with prewarming) | `paper/fig/bg_split.tex` | `paper/data/f270_motiv.csv` | `paper/scripts/final270.py` |
| Table 1 (binding times) | | `paper/data/offline/binding_dataflow_eval.txt`, `binding_dataflow_repeated_eval.txt` | `paper/scripts/offline/binding_dataflow.py`, `binding_dataflow_repeated.py`, `binding_repeated_weights.py` |
| Figure 3 (where prewarming is late) | `paper/fig/prewarm_late.tex` | `paper/data/offline/lateslots_m3_eval.txt` | `paper/scripts/offline/lateslots_eval.py` |
| Figure 4 (an access plan) | `paper/fig/plan.tex` | diagram | |
| Figure 5 (overview) | `paper/fig/overview.tex` | diagram | |
| Table 2 (main comparison) | | `paper/data/f270_main.txt`, `f270_table2_ci.txt`, `results/main/results/ana270.txt` | `paper/scripts/final270.py`, `table2_ci270.py`, `results/main/scripts/ana257.py` |
| Figure 6 (offline prediction) | `paper/fig/eval_pred.tex` | `paper/data/m3_pred_scatter.csv` | `paper/scripts/offline/pred_eval_weights.py`, `fig_pred.py` |
| Figure 7 (distribution over blocks) | `paper/fig/eval_dist.tex` | `paper/data/f270_ccdf_{np,exec}.csv`, `f270_dist_pct.csv` | `paper/scripts/final270.py` |
| Figure 8 (time against reads per block) | `paper/fig/eval_blockreads.tex` | `paper/data/f273_blockreads_*.csv` | `results/blockreads/scripts/br273.py`, `paper/scripts/blockreads_e273.py`, `blockreads_e273_points.py` |
| Figure 9 (three kinds of storage) | `paper/fig/eval_storage.tex` | `paper/data/f270_storage.csv` | `results/main/scripts/cmp270.py`, `paper/scripts/fig_storage270.py` |
| Table 3 (ablation) | | `results/main/results/ana270.txt` section [6], `paper/data/f270_abl.txt` | `results/main/scripts/ana257.py`, `paper/scripts/final270.py` |
| Table 4 (reads of the execution thread) | | `paper/data/f270_readcost.txt` | `paper/scripts/readcost_e270.py` |

Other numbers of Section 7: storage, memory and core-count comparisons in `results/main/results/cmp270_{sd,sm,mem,cpu}.txt`;
waits by block class in `paper/data/f270_wait_by_class.txt`; plans by reads in `f270_plans_by_reads.txt`; per-transaction
costs in `f270_restcost.txt`; reuse and reader statistics in `reuse_redo_e270.txt` and `reader_reads_split_e270.txt`.
The line counts of Section 6 are in `reth/lines_of_code.txt`.

## Environment

- Measurement servers: Alibaba Cloud `ecs.i4.8xlarge` (Xeon Platinum 8369B, 32 hardware threads, 256 GiB of memory, two
  local NVMe SSDs with XFS and reflink), Ubuntu 26.04. The node runs on 28 hardware threads under a 32 GiB
  memory limit; the driver runs on the other four. The storage comparison adds ESSD PL1 and PL0 network volumes, the
  machine comparison one `ecs.i2.8xlarge`.
- reth 2.9.0 (tag `v2.9.0`, commit `c9a780f`), Rust 1.98.1, LLVM 23.1 (for the compiler crate `evm2-jit`).
- Plan generation: PyPy 3.12 (or CPython 3.12+, slower) with `pycryptodome`. Analysis: Python 3 with `numpy`.
  Figures: TeX Live with LuaLaTeX and pgfplots. Unpacking: `zstd`.

## Building reth with Prologue

```
reth/apply.sh ~/prologue-build
```

fetches reth `v2.9.0` and evm2 at the revision reth 2.9.0 pins (`f93318f`), applies the patches, and compares the git
tree hashes of the results with those of the measured sources. It leaves `~/prologue-build/reth-2.9.0-prologue` with two
branches and `~/prologue-build/evm2-x290`:

- branch `stock` is reth 2.9.0 plus `patches/reth/0001`, which adds the flags `--jit.timeout` and
  `--jit.log-compilations` with unchanged defaults. This is the stock reth of the paper's comparisons.
- branch `prologue` adds `patches/reth/0002`, all of Prologue: 65 files, 36,366 added lines including tests, switches that
  are off in the measured configuration, and the plan evaluator `crates/frame-plan`. Its manifest takes evm2 from
  `../evm2-x290`, which carries `patches/evm2/0001` (hooks that keep compiled code running under the call-start hook).

Build each branch with the settings of the measured binaries:

```
cd ~/prologue-build/reth-2.9.0-prologue
export LLVM_SYS_231_PREFIX=<LLVM 23 prefix> CARGO_PROFILE_RELEASE_STRIP=none JEMALLOC_SYS_WITH_LG_VADDR=48
cargo build --release --locked --bin reth
```

`measurement/host/build290.sh` is the script used on the servers; it also runs the unit tests of the changed crates.
The patches are single commits. The comments in the source carry labels of the form `EXP-nnn` and `X-nnn`, which refer
to the authors' development log.

## Generating plans

```
plans/example/check.sh
```

generates the plans of six contract codes and the CREATE2 records of three, and compares them with the files of the
library used in the paper. For a set of codes:

```
plans/build_library.sh CODES.tsv WORK [BASE_LIBRARY] [SHARDS]
python3 plans/create2/c2sweep.py CREATE2_CODES.tsv 0 1 OUT
python3 plans/create2/c2assemble270.py NODE_DIR OUT/c2records
```

`CODES.tsv` has a header line and one `codehash<TAB>bytecode` line per code. A Prologue node writes this table for the
codes it executes when the environment variable `EAP_CODES_OUT` names a file. `build_library.sh` analyzes every code
that the base library lacks, exports and merges its plan, and writes the completed library with a `MANIFEST`.
The tests of the analyzer are `plans/analyzer/test_*.py`; those of the plan format and evaluator run with
`cargo test --lib` in `plans/evaluator/frame_plan_v3`.

The library of the paper holds 71,170 plans (6.3 GiB, 549 MB compressed); `plans/manifests/plans_269.MANIFEST` gives
its file count and hashes. Its 19,376 most recent plans were generated by `build_library.sh` as it is here. The
other 51,794 were built in earlier steps, and for part of them the storage sections were exported from analysis
summaries computed with earlier versions of the analyzer: of 60 of these plans drawn at random and regenerated from
bytecode with this version, 41 are identical to the library's files and 19 differ.
The library itself and the code table are distributed separately from this repository (see *Large inputs*).
The CREATE2 records of the paper are `plans/create2/c2rec_270.tar.zst` (7,324 files, 370 with records).

## Running the measurements

`measurement/README.md` describes the server layout and the order of the steps. In outline, for each of the ten
segments of 1,000 blocks (blocks 26,306,131–26,316,130 of Ethereum mainnet):

1. Prepare a node database at the block before the segment's warm-up (`host/make_base.sh`, `host/forward.sh`) and the
   account filter for it (`reth db eap-acc-filter`, a subcommand of the Prologue build).
2. Fetch the blocks as engine payloads from a beacon node (`host/fetch_blocks.sh`).
3. Run one node process per column (`run/main270.sh <column> <segment>`): restore the database copy, drop its pages
   from the page cache, start reth without peers, replay 300 warm-up blocks and 1,000 measured blocks through
   `engine_newPayloadV4` and `engine_forkchoiceUpdatedV3`, waiting at least 0.25 s after each block.
   Columns: `up` stock reth, `ur` stock reth with `--engine.prewarm-reuse`, `un` stock reth with
   `--engine.disable-prewarming`, `pn` Prologue; `abl` rotates the nine ablation rows block by block, `rec` runs the
   recording rows.

The block validation time of a block is the duration of its `engine_newPayloadV4` call, measured by the client.

### Measured configuration

- Binaries: branch `prologue` for Prologue, branch `stock` for the three stock columns.
- Compiler flags, every process: `--jit --jit.timeout 60s --jit.worker-count 8 --jit.max-pending-jobs 8192 --jit.log-compilations`.
- Threads: 12 pre-execution threads and 8 reader threads; the execution thread alone on one physical core; reth's own
  pools at their defaults. Node memory limit 32 GiB.
- Node environment of Prologue: `EAP_PLANS` (plan library), `EAP_C2REC` (CREATE2 records), `EAP_ACCFILTER` (account
  filter), `EAP_PLAN_CACHE_MB=5120`, `EAP_CODE_VICTIM_ENTRIES=1048576`, `EAP_CTRL` (a file the driver rewrites before
  each block with the control line).
- Control line of Prologue, followed by `srdiag=0 ctlcache=1` in the timing processes:

```
prewarm=1 insp=0 cs=0 tx=1 code=1 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1
reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4 reusebalsend=1 ixpf=256 ixpfw=1 ewcore=1 ewpool=1
exslice=100 exrt=1 ewnear=0 exio=1 srrt=1 accflt=1 accfltchk=1000 bigra=1 ccv=1 ewinf=1 rdpeek=1 sysn=1 readers=8
rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=0 pwnbval=1 pwnbgas=5000000
pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000
pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1
pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 rdpool=1 rdjoinlate=1 logq=1 rdasync=1 excore=1 exsmt=1
exphys=1 exclean=1 rddefer=1 prep=1 rdkick=1 srleafselect=1 rdscratch=1
```

Rows in the data (`cfg` column of the block tables; the control line of every row is in
`results/main/results/rows270_G4qaxepkS.txt`):

| Row | Configuration |
|---|---|
| `U8` | stock reth (columns `up`, `ur`, `un`; the stock build ignores the control line) |
| `F8` | Prologue (column `pn`); identical to `H4` |
| `H0` | Prologue build with every mechanism off: reth's own prewarming only |
| `H1` | `H0` plus pre-execution and reuse |
| `H2` | `H1` plus scheduling |
| `H3` | `H2` plus the read path and state-root changes: Prologue without plans |
| `H4` | `H3` plus plans and reader threads: Prologue |
| `H5` | `H0` plus plans and reader threads only |
| `HX`, `HC`, `HXC` | `H4` without loop extrapolation, without path conditions, without both |
| `H0n` | `H0` with reth's prewarming off (recording processes only) |
| `P8` | Prologue without plans, in the storage, memory and core-count comparisons |

## Reproducing the figures and tables from the data

```
./unpack.sh                                   # per-block tables -> results/main/raw (220 MB)
python3 paper/scripts/final270.py             # Table 2, Figures 2 and 7, Table 3 -> paper/data/f270_*
python3 paper/scripts/table2_ci270.py > paper/data/f270_table2_ci.txt
(cd results/main && bash results/ana270.cmd > results/ana270.txt)          # Tables 2 and 3 with intervals
(cd results/main && for t in sd sm mem cpu; do bash results/cmp270_$t.cmd > results/cmp270_$t.txt; done)
python3 paper/scripts/fig_storage270.py       # Figure 9
python3 paper/scripts/blockreads_e270.py > paper/data/f270_blockreads.txt
(cd results/blockreads && python3 scripts/br273.py > results/br273.txt)
python3 paper/scripts/blockreads_e273.py > paper/data/f273_blockreads.txt  # Figure 8
python3 paper/scripts/blockreads_e273_points.py >> paper/data/f273_blockreads.txt
python3 paper/scripts/plans_by_reads270.py > paper/data/f270_plans_by_reads.txt
python3 paper/scripts/restcost247_e270.py > paper/data/f270_restcost.txt
python3 paper/scripts/reuse_redo_e270.py > paper/data/reuse_redo_e270.txt
python3 paper/scripts/reader_reads_split_e270.py > paper/data/reader_reads_split_e270.txt
POP=eval python3 paper/scripts/offline/fig_pred.py                         # Figure 6 from the per-predictor sums
paper/build_figures.sh                        # all nine figures -> paper/build/*.pdf
```

Every command above reproduces the files in the repository from the data in the repository. The standalone figures
are set in Times; the paper sets the diagrams in its own text font.

`results/main/raw/<run>/` holds, for each node process, its block table (`results/blocks_*.csv`: one line per block
with the validation time, the execution time, gas, processor time, and for the recording rows the counts and times of
the execution thread's reads by outcome), the block schedule, and the node-log lines the scripts read. Run names:
`e270{up,ur,un,pn}-<k>` main comparison of segment `k`; `e270abl-<k>` ablation; `e270rec-<k>` recording; the names
with `slocal`, `spl1`, `spl0`, `m16`/`m32`/`m64`, `h14` and `cs` are the storage, memory, core-count and
second-machine processes of segment 6.

Three computations start from records that are not in the repository: Table 4 (`paper/scripts/readcost_e270.py`) and
the per-transaction tables (`extract247_e270.sh`) read the recording processes' per-read records, 923 MB; Table 1,
Figure 3 and the per-predictor sums behind Figure 6 (`paper/scripts/offline/`) read per-read traces of an offline
replay and the outputs of the other predictors, 8 GB. Their outputs are in `paper/data/`, and the scripts take the
location of the records from `TRACE_ROOT`.

## Large inputs

| Input | Size | How to obtain |
|---|---|---|
| Plan library of the paper | 549 MB compressed | to be published with the repository's first release; hashes in `plans/manifests/plans_269.MANIFEST` |
| Code table of the measured blocks (46,082 codes) | 96 MB compressed | written by a Prologue node with `EAP_CODES_OUT` over blocks 26,305,831–26,316,130; to be published with the plan library |
| Block payloads | 10,300 blocks | `measurement/host/fetch_blocks.sh` from any beacon node API |
| Node database | | a reth mainnet snapshot at or before block 26,305,830, moved to the segment starts with `reth stage unwind` and `host/forward.sh` |
| Per-read records and traces | 9 GB | available from the authors |

## License

Licensed under either of the Apache License, Version 2.0 (`LICENSE-APACHE`) or the MIT license (`LICENSE-MIT`), at
your option, as reth is. The patches in `reth/patches` apply to reth and evm2 and are offered under the same terms.
