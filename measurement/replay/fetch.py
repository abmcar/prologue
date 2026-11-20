#!/usr/bin/env python3
"""Fetch mainnet beacon blocks and store the execution-payload inputs of
engine_newPayloadV4, one JSON file per execution block number.

Usage: fetch.py --start-block N --count K --start-slot S [--out DIR]
S is any slot at or before the slot that carries block N; empty slots are skipped.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BEACON = os.environ.get("BEACON_API", "https://ethereum-beacon-api.publicnode.com")


def get_slot(slot, retries=6):
    url = f"{BEACON}/eth/v2/beacon/blocks/{slot}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "reth-engine-replay/0.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # missed slot
            if attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(2 ** attempt)


def minimal(doc):
    msg = doc["data"]["message"]
    body = msg["body"]
    return {
        "fork": doc["version"],
        "slot": int(msg["slot"]),
        "parent_root": msg["parent_root"],
        "payload": body["execution_payload"],
        "blob_kzg_commitments": body.get("blob_kzg_commitments", []),
        "execution_requests": body.get("execution_requests", {}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-block", type=int, required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--start-slot", type=int, required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocks"))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    want = set(range(args.start_block, args.start_block + args.count))
    slot = args.start_slot
    batch = max(args.workers * 4, 32)
    with ThreadPoolExecutor(args.workers) as pool:
        while want:
            slots = list(range(slot, slot + batch))
            for s, doc in zip(slots, pool.map(get_slot, slots)):
                if doc is None:
                    continue
                m = minimal(doc)
                n = int(m["payload"]["block_number"])
                if n in want:
                    with open(os.path.join(args.out, f"{n}.json"), "w") as f:
                        json.dump(m, f)
                    want.discard(n)
            slot += batch
            if want and min(want) < args.start_block + args.count and slot > args.start_slot + 2 * args.count + 1000:
                sys.exit(f"gave up: still missing {len(want)} blocks, first {min(want)}")
            print(f"slot<{slot} missing={len(want)}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
