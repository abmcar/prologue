#!/usr/bin/env python3
"""Replay stored blocks into a reth node through the Engine API
(engine_newPayloadV4 + engine_forkchoiceUpdatedV3), one block at a time, the
same path a node following the chain takes. Writes one JSONL record per block.

Usage: replay.py --from N --to M --out runs/x.jsonl [--blocks DIR]
The node's canonical head must be N-1.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPRO = os.environ.get("WITNESS_REPRO", "five-engine-repro")   # only used by the witness capture
FETCH_WITNESS = f"{REPRO}/reth-line/reth/adapter-subject-backends/witness-db/fetch-witness.sh"
VERIFY_WITNESS = f"{REPRO}/artifacts/verify-witness"


def load_block(path, wait_s):
    """Wait for the fetcher to produce the block file; tolerate a file still being written."""
    deadline = time.time() + wait_s
    while True:
        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            if time.time() > deadline:
                raise
            time.sleep(2)


def capture_witness(n, block_hash, out_dir, rpc_url):
    """Same fetch and acceptance check as five-engine-repro/orchestration/capture-corpus.sh."""
    path = os.path.join(out_dir, f"block-{n}-{block_hash}.json")
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}
    env.update(NO_PROXY="*", no_proxy="*", TMPDIR=f"{REPRO}/tmp/capture")
    os.makedirs(env["TMPDIR"], exist_ok=True)
    t0 = time.perf_counter()
    for attempt in range(1, 4):
        r = subprocess.run(["timeout", "--signal=TERM", "--kill-after=30s", "35m", FETCH_WITNESS, rpc_url, block_hash, path],
                           env=env, capture_output=True, text=True)
        if r.returncode == 0:
            break
        if os.path.exists(path):
            os.rename(path, f"{path}.failed-fetch-attempt-{attempt}.{int(time.time())}")
        print(f"witness fetch attempt {attempt} failed for {n}: {r.stderr.strip()[-300:]}", file=sys.stderr, flush=True)
        time.sleep(2 * attempt)
    else:
        sys.exit(f"block {n}: witness capture failed")
    t1 = time.perf_counter()
    v = subprocess.run([VERIFY_WITNESS, "--require-target-block", path], capture_output=True, text=True)
    t2 = time.perf_counter()
    try:
        j = json.loads(v.stdout)
    except json.JSONDecodeError:
        j = {}
    ok = (j.get("status") == "verified" and j.get("targetBlockNumber") == n
          and str(j.get("targetBlockHash", "")).lower() == block_hash.lower()
          and j.get("rawBlockBound") is True and j.get("bodyCommitmentsVerified") is True
          and j.get("targetBlockBinding") == "rawBlock")
    if not ok:
        os.rename(path, f"{path}.failed-verification.{int(time.time())}")
        sys.exit(f"block {n}: witness failed verification: {v.stdout[:300]} {v.stderr[-300:]}")
    return {"witness_s": t1 - t0, "verify_s": t2 - t1, "witness_bytes": os.path.getsize(path)}


def b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class Rpc:
    def __init__(self, url, jwt_secret=None):
        self.url = url
        self.secret = jwt_secret
        self.id = 0

    def token(self):
        head = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        claims = b64url(json.dumps({"iat": int(time.time())}).encode())
        sig = hmac.new(self.secret, f"{head}.{claims}".encode(), hashlib.sha256).digest()
        return f"{head}.{claims}.{b64url(sig)}"

    def call(self, method, params):
        self.id += 1
        data = json.dumps({"jsonrpc": "2.0", "id": self.id, "method": method, "params": params}).encode()
        req = urllib.request.Request(self.url, data=data, headers={"Content-Type": "application/json"})
        if self.secret:
            req.add_header("Authorization", f"Bearer {self.token()}")
        t0 = time.perf_counter_ns()
        with urllib.request.urlopen(req, timeout=600) as r:
            body = json.load(r)
        dt = time.perf_counter_ns() - t0
        if "error" in body:
            raise RuntimeError(f"{method}: {body['error']}")
        return body["result"], dt


def q(x):
    return hex(int(x))


def payload_v3(p):
    return {
        "parentHash": p["parent_hash"],
        "feeRecipient": p["fee_recipient"],
        "stateRoot": p["state_root"],
        "receiptsRoot": p["receipts_root"],
        "logsBloom": p["logs_bloom"],
        "prevRandao": p["prev_randao"],
        "blockNumber": q(p["block_number"]),
        "gasLimit": q(p["gas_limit"]),
        "gasUsed": q(p["gas_used"]),
        "timestamp": q(p["timestamp"]),
        "extraData": p["extra_data"],
        "baseFeePerGas": q(p["base_fee_per_gas"]),
        "blockHash": p["block_hash"],
        "transactions": p["transactions"],
        "withdrawals": [
            {"index": q(w["index"]), "validatorIndex": q(w["validator_index"]),
             "address": w["address"], "amount": q(w["amount"])}
            for w in p["withdrawals"]
        ],
        "blobGasUsed": q(p["blob_gas_used"]),
        "excessBlobGas": q(p["excess_blob_gas"]),
    }


def versioned_hash(commitment_hex):
    return "0x01" + hashlib.sha256(bytes.fromhex(commitment_hex[2:])).hexdigest()[2:]


def u64le(x):
    return int(x).to_bytes(8, "little")


def h(x):
    return bytes.fromhex(x[2:])


def execution_requests(r):
    """EIP-7685 request list: type byte || SSZ-concatenated items, empty types omitted."""
    out = []
    deps = r.get("deposits", [])
    if deps:
        out.append(b"\x00" + b"".join(
            h(d["pubkey"]) + h(d["withdrawal_credentials"]) + u64le(d["amount"]) + h(d["signature"]) + u64le(d["index"])
            for d in deps))
    wds = r.get("withdrawals", [])
    if wds:
        out.append(b"\x01" + b"".join(
            h(w["source_address"]) + h(w["validator_pubkey"]) + u64le(w["amount"]) for w in wds))
    cons = r.get("consolidations", [])
    if cons:
        out.append(b"\x02" + b"".join(
            h(c["source_address"]) + h(c["source_pubkey"]) + h(c["target_pubkey"]) for c in cons))
    return ["0x" + x.hex() for x in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, required=True)
    ap.add_argument("--to", dest="end", type=int, required=True, help="inclusive")
    ap.add_argument("--out", required=True)
    ap.add_argument("--blocks", default=os.path.join(HERE, "blocks"))
    ap.add_argument("--engine", default="http://127.0.0.1:8551")
    ap.add_argument("--http", default="http://127.0.0.1:8545")
    ap.add_argument("--jwt", default=os.path.join(HERE, "..", "data", "jwt.hex"))
    ap.add_argument("--finality-lag", type=int, default=64)
    ap.add_argument("--wait", type=float, default=0.0, help="seconds to sleep between blocks")
    ap.add_argument("--witness-dir", help="capture a five-engine witness bundle for every block into this directory")
    ap.add_argument("--block-wait", type=float, default=3600, help="max seconds to wait for a block file from the fetcher")
    args = ap.parse_args()

    secret = bytes.fromhex(open(args.jwt).read().strip().removeprefix("0x"))
    engine = Rpc(args.engine, secret)
    http = Rpc(args.http)

    head = int(http.call("eth_blockNumber", [])[0], 16)
    if head != args.start - 1:
        sys.exit(f"node head is {head}, expected {args.start - 1}")
    head_hash = http.call("eth_getBlockByNumber", [hex(head), False])[0]["hash"]
    hashes = {head: head_hash}

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "a") as out:
        for n in range(args.start, args.end + 1):
            b = load_block(os.path.join(args.blocks, f"{n}.json"), args.block_wait)
            p = b["payload"]
            params = [
                payload_v3(p),
                [versioned_hash(c) for c in b["blob_kzg_commitments"]],
                b["parent_root"],
                execution_requests(b["execution_requests"]),
            ]
            res, np_ns = engine.call("engine_newPayloadV4", params)
            if res["status"] != "VALID":
                sys.exit(f"block {n}: newPayload {res}")
            hashes[n] = p["block_hash"]
            fin = hashes.get(max(n - args.finality_lag, args.start - 1), head_hash)
            fcu, fcu_ns = engine.call("engine_forkchoiceUpdatedV3", [
                {"headBlockHash": p["block_hash"], "safeBlockHash": fin, "finalizedBlockHash": fin}, None])
            if fcu["payloadStatus"]["status"] != "VALID":
                sys.exit(f"block {n}: forkchoiceUpdated {fcu}")
            hashes.pop(n - args.finality_lag - 1, None)
            rec = {"block": n, "slot": b["slot"], "txs": len(p["transactions"]), "gas_used": int(p["gas_used"]),
                   "new_payload_ms": np_ns / 1e6, "fcu_ms": fcu_ns / 1e6, "t": time.time()}
            if args.witness_dir:
                rec.update(capture_witness(n, p["block_hash"], args.witness_dir, args.http))
            out.write(json.dumps(rec) + "\n")
            out.flush()
            if n % 50 == 0 or n == args.end:
                print(f"{n} np={rec['new_payload_ms']:.1f}ms gas={rec['gas_used']/1e6:.1f}M", file=sys.stderr, flush=True)
            if args.wait:
                time.sleep(args.wait)


if __name__ == "__main__":
    main()
