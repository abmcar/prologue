//! offline instantiation of recorded frames with version-3 access plans (`src/frame_plan_v3`). Copy of
//! tools/fpct (built against `reth/frame-plan-ctcs`) with the family call records of version-3 plans.
//!
//! stdin, one frame per line, tab separated (as fp19 / fpct):
//!   id code_hash target caller origin value_hex input_hex number timestamp coinbase gas_limit basefee prevrandao_hex
//! stdout (columns 1-6 as fpct):
//!   `id<TAB>has_plan<TAB>n_cgroups<TAB>key,key,...<TAB>call;call;...<TAB>n_sload_nodes<TAB>n_fcgroups<TAB>family_capped<TAB>holes`
//!   call = `kind:target:payload_hex|-` for an index-free call group and `kind:target:payload_hex|-:f<g>.<v0>.<v1>` for a
//!   call from family call group g (index into the plan's family call groups) with key index values v0, v1
//!   (kind 0 CALL, 1 CALLCODE, 2 DELEGATECALL, 3 STATICCALL; payload `-` when an argument word did not evaluate);
//!   n_fcgroups = family call groups of the plan, family_capped = assignments dropped by the per-group / per-frame caps;
//!   column 9: per call (same order as column 5, comma separated) the payload bytes no argument word covers
//!   (Scratch::call_holes; 0 for an unknown payload).
//! usage: fpct3 [--legacy-payload] PLAN_DIR [PLAN_DIR ...] < frames.tsv > out.tsv
//!        fpct3 --check PLAN_DIR > files.tsv   (every file: parse, analyze, `to_bytes` equal to the file; one line per file
//!        `codehash version kind bytes n_cgroups n_fcgroups n_fcalts roundtrip_ok`, then a summary line on stderr)
//!   --legacy-payload: index-free calls of version-3 plans with the version-1/2 payload rule (Scratch::legacy_payload),
//!   for the comparison with fpct on the version-2 library.
//!   At the end a line on stderr: `timing frames F plans P load_ms L instantiate_ms I calls_ms C family_calls N`
//!   (wall-clock sums over the frames: plan file read + parse + analyze, `instantiate`, `instantiate_calls`).
use alloy_primitives::{hex, Address, B256, U256};
use frame_plan::{Frame, Plan, Scratch, N_ENV};
use std::collections::HashMap;
use std::io::{BufRead, BufWriter, Write};

fn a2u(a: Address) -> U256 {
    U256::from_be_slice(a.as_slice())
}

fn check(dir: &str) {
    let mut out = BufWriter::new(std::io::stdout());
    let (mut n, mut bad) = (0u64, 0u64);
    let mut ents: Vec<_> = std::fs::read_dir(dir).expect("plan dir").flatten().map(|e| e.path()).collect();
    ents.sort();
    let _ = writeln!(out, "codehash\tversion\tkind\tbytes\tn_cgroups\tn_fcgroups\tn_fcalts\troundtrip_ok");
    for path in ents {
        let Some(stem) = path.file_name().and_then(|n| n.to_str()).and_then(|n| n.strip_suffix(".eapf")) else { continue };
        let b = std::fs::read(&path).unwrap();
        let p = Plan::parse_analyzed(&b);
        let ok = p.to_bytes() == b;
        n += 1;
        bad += (!ok) as u64;
        let _ = writeln!(out, "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}", stem, p.version, p.kind, b.len(), p.cgroups.len(), p.fcgroups.len(), p.fcalts.len(), ok as u8);
    }
    eprintln!("files {n} roundtrip_bad {bad}");
}

fn main() {
    if std::env::args().nth(1).as_deref() == Some("--check") {
        check(&std::env::args().nth(2).expect("dir"));
        return
    }
    let mut plans: HashMap<B256, Option<Plan>> = HashMap::new();
    let mut paths: HashMap<B256, std::path::PathBuf> = HashMap::new();
    let mut legacy = false;
    for dir in std::env::args().skip(1) {
        if dir == "--legacy-payload" {
            legacy = true;
            continue
        }
        for e in std::fs::read_dir(&dir).expect("plan dir").flatten() {
            let name = e.file_name();
            let Some(stem) = name.to_str().and_then(|n| n.strip_suffix(".eapf")) else { continue };
            let Ok(h) = stem.trim_start_matches("0x").parse::<B256>() else { continue };
            paths.entry(h).or_insert(e.path());
        }
    }
    eprintln!("plan files: {} legacy_payload: {}", paths.len(), legacy);
    let mut sc = Scratch::default();
    sc.interval = true;
    sc.legacy_payload = legacy;
    let stdin = std::io::stdin();
    let mut out = BufWriter::new(std::io::stdout());
    let (mut t_load, mut t_inst, mut t_calls, mut nfr, mut nfam) = (0u128, 0u128, 0u128, 0u64, 0u64);
    for line in stdin.lock().lines() {
        let line = line.unwrap();
        let f: Vec<&str> = line.split('\t').collect();
        if f.len() < 13 {
            continue
        }
        let h: B256 = f[1].parse().unwrap_or_default();
        let t0 = std::time::Instant::now();
        let plan = plans.entry(h).or_insert_with(|| paths.get(&h).and_then(|p| std::fs::read(p).ok()).map(|b| Plan::parse_analyzed(&b)));
        t_load += t0.elapsed().as_nanos();
        let Some(plan) = plan.as_ref() else {
            let _ = writeln!(out, "{}\t0\t0\t\t\t0\t0\t0\t", f[0]);
            continue
        };
        let target: Address = f[2].parse().unwrap_or_default();
        let caller: Address = f[3].parse().unwrap_or_default();
        let origin: Address = f[4].parse().unwrap_or_default();
        let value = U256::from_str_radix(f[5].trim_start_matches("0x"), 16).unwrap_or_default();
        let input = hex::decode(f[6]).unwrap_or_default();
        let num = |s: &str| U256::from_str_radix(s.trim_start_matches("0x"), if s.starts_with("0x") { 16 } else { 10 }).unwrap_or_default();
        let coinbase: Address = f[9].parse().unwrap_or_default();
        let env: [U256; N_ENV] = [
            a2u(caller),
            a2u(origin),
            a2u(target),
            value,
            U256::from(input.len()),
            num(f[7]),
            num(f[8]),
            U256::from(1u8),
            a2u(coinbase),
            num(f[10]),
            num(f[11]),
            num(f[12]),
            U256::from(1u8),
            U256::ZERO,
        ];
        let fr = Frame { calldata: &input, env, sload: None };
        let t1 = std::time::Instant::now();
        sc.instantiate(plan, &fr);
        let t2 = std::time::Instant::now();
        sc.instantiate_calls(plan, &fr, true);
        t_inst += (t2 - t1).as_nanos();
        t_calls += t2.elapsed().as_nanos();
        nfr += 1;
        nfam += sc.c_family as u64;
        let keys: Vec<String> = sc.out.iter().map(|k| format!("{}", B256::from(*k))).collect();
        let calls: Vec<String> = sc
            .calls
            .iter()
            .zip(sc.call_idx.iter())
            .map(|(c, ix)| {
                let t = Address::from_slice(&c.target.to_be_bytes::<32>()[12..]);
                let p = c.payload.as_ref().map(|p| hex::encode(p)).unwrap_or_else(|| "-".to_string());
                match ix {
                    None => format!("{}:{}:{}", c.kind, t, p),
                    Some((g, v0, v1)) => format!("{}:{}:{}:f{}.{}.{}", c.kind, t, p, g, v0, v1),
                }
            })
            .collect();
        let n_sload = plan.nodes.iter().filter(|n| n.w0 & 0xff == frame_plan::T_SLOAD).count();
        let holes: Vec<String> = sc.call_holes.iter().map(|h| h.to_string()).collect();
        let _ = writeln!(
            out,
            "{}\t1\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
            f[0],
            plan.cgroups.len(),
            keys.join(","),
            calls.join(";"),
            n_sload,
            plan.fcgroups.len(),
            sc.c_family_capped,
            holes.join(",")
        );
    }
    eprintln!("timing frames {} plans {} load_ms {:.1} instantiate_ms {:.1} calls_ms {:.1} family_calls {}", nfr, plans.len(),
              t_load as f64 / 1e6, t_inst as f64 / 1e6, t_calls as f64 / 1e6, nfam);
}
