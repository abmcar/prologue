#!/usr/bin/python3
"""EXP-198 (Master 2026-10-30, README section 3): evict the node database files from the page cache before every pass, so
every pass starts from the same cache state (the unwind before a pass otherwise leaves the pages it rewrote warm; EXP-195 c1).
Runs only with the node stopped (refuses when a reth executable is running). Opens every regular file under
the node directory/data/{db,static_files,rocksdb} read-only and calls posix_fadvise(DONTNEED) on it; nothing is written.
Prints the files and bytes advised and /proc/meminfo Cached before and after.
usage: evict_cache.py"""
import os, sys
root = os.path.join(os.environ['PROLOGUE_NODE_HOME'], 'data')   # Prologue server copy: scripts/server/apply_server.py
for pid in os.listdir('/proc'):
    if pid.isdigit():
        try:
            if os.path.basename(os.readlink(f'/proc/{pid}/exe')).startswith('reth'):
                sys.exit(f'reth running (pid {pid}); not evicting')
        except OSError:
            pass
cached = lambda: int(next(l.split()[1] for l in open('/proc/meminfo') if l.startswith('Cached:'))) // 1024  # noqa: E731
c0 = cached(); n = 0; size = 0
for sub in ('db', 'static_files', 'rocksdb'):
    for d, _, fs in os.walk(os.path.join(root, sub)):
        for fn in fs:
            p = os.path.join(d, fn)
            try:
                if not os.path.isfile(p) or os.path.islink(p):
                    continue
                fd = os.open(p, os.O_RDONLY)
                try:
                    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED); n += 1; size += os.fstat(fd).st_size
                finally:
                    os.close(fd)
            except OSError as e:
                print(f'skip {p}: {e}')
print(f'evicted {n} files, {size / 2**30:.1f} GiB advised; Cached {c0} MiB -> {cached()} MiB')
