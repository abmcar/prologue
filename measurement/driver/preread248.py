#!/usr/bin/python3
"""EXP-248 (Master 11-04 16:5x approved): read the node database file <DATADIR>/db/mdbx.dat once, in order, so that the page
cache of the calling process's control group starts full before the node starts. With a MemoryMax below the file size the
pages kept are the ones read last, the end of the file; without one, most of the file stays cached. Called by the driver's
run_f.sh after the eviction of each pass (scripts/apply_mem248.py), inside the run's scope, so the pages are charged to it.
Runs only with the node stopped (the check of the driver's evict_cache.py). Prints the bytes read, the time, the rate and the
group's memory.current, file pages and memory.max afterwards. Exit 1, which stops the pass, when (Master 11-04 16:5x):
  - fewer bytes than the file size were read;
  - PREREAD_EXPECT_MAX is set and the group's memory.max is not exactly it (bytes, or max for no cap);
  - the group's file pages are below 90% of the smaller of memory.max and the file size (with a cap) or below 80% of the
    file size (without one), i.e. the page cache of the run's scope did not fill. (The server's database file, 266.3 GB on
    11-04, is larger than every cap of EXP-248.)
usage: [PREREAD_EXPECT_MAX=<bytes|max>] preread248.py DATADIR"""
import os, sys, time

DATADIR = sys.argv[1]
F = os.path.join(DATADIR, 'db', 'mdbx.dat')
for pid in os.listdir('/proc'):
    if pid.isdigit():
        try:
            if os.path.basename(os.readlink(f'/proc/{pid}/exe')).startswith('reth'):
                sys.exit(f'reth running (pid {pid}); not reading')
        except OSError:
            pass
CG = '/sys/fs/cgroup' + next(line.split(':', 2)[2].strip() for line in open('/proc/self/cgroup') if line.startswith('0::'))


def rd(name):
    try:
        return open(os.path.join(CG, name)).read()
    except OSError:
        return ''


size = os.path.getsize(F)
buf = bytearray(16 << 20)
n = 0
t0 = time.monotonic()
with open(F, 'rb', buffering=0) as fh:
    os.posix_fadvise(fh.fileno(), 0, 0, os.POSIX_FADV_SEQUENTIAL)
    while True:
        k = fh.readinto(buf)
        if not k:
            break
        n += k
dt = time.monotonic() - t0
file_pages = next((line.split()[1] for line in rd('memory.stat').splitlines() if line.startswith('file ')), '0')
mmax = rd('memory.max').strip()
print(f'pre-read {F}: {n} of {size} bytes in {dt:.1f} s ({n / max(dt, 1e-9) / 1e6:.0f} MB/s); group {CG}: '
      f'memory.current {rd("memory.current").strip()}, file {file_pages}, memory.max {mmax}')
bad = []
if n != size:
    bad.append(f'read {n} of {size} bytes')
expect = os.environ.get('PREREAD_EXPECT_MAX')
if expect is not None and mmax != expect:
    bad.append(f'memory.max {mmax}, expected {expect}')
need = 0.8 * size if mmax == 'max' else 0.9 * min(int(mmax or 0), size)
if int(file_pages) < need:
    bad.append(f'file pages {file_pages} below {need:.0f} ({"80% of the file" if mmax == "max" else "90% of the smaller of memory.max and the file"})')
print('checks: ' + ('; '.join(bad) if bad else f'ok (memory.max {"as expected" if expect is not None else "not compared"}; '
                    f'file pages at least {need:.0f})'))
sys.exit(1 if bad else 0)
