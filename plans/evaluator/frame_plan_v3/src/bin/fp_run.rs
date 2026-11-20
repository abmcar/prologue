//! fp_run: drive the single-frame instantiator over exported frame inputs.
//!   fp_run diff  PLANS_DIR FRAMES.bin OUT.tsv            one line per frame: i, n_keys, counters, keys (hex)
//!   fp_run time  PLANS_DIR FRAMES.bin OUT.csv PASSES     one warm-up pass, then PASSES timed passes in block order
//!   fp_run load  PLANS_DIR CODEHASH_LIST OUT.csv REPS    per-plan read+parse time (page cache hot), RSS after loading all
//! additions; plans are loaded with Plan::parse_analyzed (condition analysis for interval solving):
//!   fp_run diff  ... [--interval]                         as above, single-index conditions solved as intervals
//!   fp_run check PLANS_DIR FRAMES.bin OUT.csv             solver check: every satisfying set computed both ways
//!   fp_run time2 PLANS_DIR FRAMES.bin OUT.csv PASSES      warm-up old + interval, then PASSES x (old pass, interval pass)
//!   fp_run prof  PLANS_DIR FRAMES.bin OUT.csv [--interval] per-frame rdtsc composition (build with --features prof)
//! `time` honours --interval / --improved.
//!   fp_run load2 PLANS_DIR CODEHASH_LIST OUT.csv REPS     per-plan read+parse time without / with condition analysis
//! Timed region per frame: building the evaluation environment from the frame inputs + Scratch::instantiate (which ends
//! with sorting and deduplicating the output). Code hash -> plan and delegate address -> code hash lookups happen
//! before the timed region and are counted.
use alloy_primitives::U256;
use frame_plan::{Frame, Plan, Scratch, N_ENV};
use std::collections::HashMap;
use std::io::Write;
use std::time::Instant;

struct Blk { number: u64, ts: u64, coinbase: [u8; 20], gaslimit: U256, basefee: U256, prevrandao: U256, deleg: HashMap<[u8; 20], [u8; 32]>, frames: Vec<Fr> }
struct Fr { ch: [u8; 32], addr: [u8; 20], caller: [u8; 20], origin: [u8; 20], value: U256, cd: Vec<u8> }

fn rd<const K: usize>(b: &[u8], p: &mut usize) -> [u8; K] { let v: [u8; K] = b[*p..*p + K].try_into().unwrap(); *p += K; v }
fn u32le(b: &[u8], p: &mut usize) -> u32 { u32::from_le_bytes(rd::<4>(b, p)) }
fn u64le(b: &[u8], p: &mut usize) -> u64 { u64::from_le_bytes(rd::<8>(b, p)) }

fn load_frames(path: &str) -> Vec<Blk> {
    let b = std::fs::read(path).unwrap(); assert!(&b[..4] == b"EAPI");
    let mut p = 4; let nb = u32le(&b, &mut p); let mut out = Vec::new();
    for _ in 0..nb {
        let number = u64le(&b, &mut p); let ts = u64le(&b, &mut p); let coinbase = rd::<20>(&b, &mut p);
        let gaslimit = U256::from_be_bytes(rd::<32>(&b, &mut p)); let basefee = U256::from_be_bytes(rd::<32>(&b, &mut p));
        let prevrandao = U256::from_be_bytes(rd::<32>(&b, &mut p));
        let nd = u32le(&b, &mut p); let mut deleg = HashMap::new();
        for _ in 0..nd { let a = rd::<20>(&b, &mut p); let c = rd::<32>(&b, &mut p); deleg.insert(a, c); }
        let nf = u32le(&b, &mut p); let mut frames = Vec::with_capacity(nf as usize);
        for _ in 0..nf {
            let ch = rd::<32>(&b, &mut p); let addr = rd::<20>(&b, &mut p); let caller = rd::<20>(&b, &mut p); let origin = rd::<20>(&b, &mut p);
            let value = U256::from_be_bytes(rd::<32>(&b, &mut p)); let n = u32le(&b, &mut p) as usize;
            let cd = b[p..p + n].to_vec(); p += n;
            frames.push(Fr { ch, addr, caller, origin, value, cd });
        }
        out.push(Blk { number, ts, coinbase, gaslimit, basefee, prevrandao, deleg, frames });
    }
    assert_eq!(p, b.len()); out
}

fn hex32(s: &str) -> [u8; 32] { let mut o = [0u8; 32]; for i in 0..32 { o[i] = u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap(); } o }

fn load_plans(dir: &str) -> (Vec<Plan>, HashMap<[u8; 32], usize>) {
    let mut v = Vec::new(); let mut m = HashMap::new();
    let mut names: Vec<_> = std::fs::read_dir(dir).unwrap().map(|e| e.unwrap().file_name().into_string().unwrap()).filter(|n| n.ends_with(".eapf")).collect();
    names.sort();
    for n in names { let b = std::fs::read(format!("{dir}/{n}")).unwrap(); m.insert(hex32(&n[..64]), v.len()); v.push(Plan::parse_analyzed(&b)); }
    (v, m)
}

fn a2u(a: &[u8; 20]) -> U256 { U256::from_be_slice(a) }

/// resolve the plan of a frame (outside the timed region); returns (plan index or None, address->codehash lookups)
fn resolve(plans: &[Plan], pm: &HashMap<[u8; 32], usize>, blk: &Blk, fr: &Fr) -> (Option<usize>, u32) {
    let Some(&pi) = pm.get(&fr.ch) else { return (None, 1) };
    if plans[pi].kind == 1 {
        let Some(ch2) = blk.deleg.get(&plans[pi].delegate) else { return (None, 2) };
        if *ch2 == fr.ch { return (None, 2); }
        return (pm.get(ch2).copied(), 2);
    }
    (Some(pi), 1)
}

#[inline]
fn env(blk: &Blk, fr: &Fr) -> [U256; N_ENV] {
    [a2u(&fr.caller), a2u(&fr.origin), a2u(&fr.addr), fr.value, U256::from(fr.cd.len()), U256::from(blk.number), U256::from(blk.ts),
     U256::from(1u8), a2u(&blk.coinbase), blk.gaslimit, blk.basefee, blk.prevrandao, U256::from(1u8), U256::ZERO]
}

fn rss_kb() -> u64 {
    std::fs::read_to_string("/proc/self/status").unwrap().lines().find(|l| l.starts_with("VmRSS:")).unwrap()
        .split_whitespace().nth(1).unwrap().parse().unwrap()
}

fn hexs(x: &[u8]) -> String { x.iter().map(|b| format!("{b:02x}")).collect() }

fn main() {
    let all: Vec<String> = std::env::args().collect();
    let improved = all.iter().any(|x| x == "--improved");
    let interval = improved || all.iter().any(|x| x == "--interval");
    #[allow(unused_variables)] let nocond = all.iter().any(|x| x == "--nocond");
    let a: Vec<String> = all.into_iter().filter(|x| !x.starts_with("--")).collect();
    match a[1].as_str() {
        "diff" => {
            let (plans, pm) = load_plans(&a[2]); let blks = load_frames(&a[3]);
            let mut o = std::io::BufWriter::new(std::fs::File::create(&a[4]).unwrap());
            writeln!(o, "i\tblock\tn_keys\tplan\tlookups\trecords\tkeccak\tcons_evals\twide\tsatsets\tkeys").unwrap();
            let mut sc = Scratch::default(); sc.interval = interval; sc.improved = improved; let mut i = 0usize;
            for blk in &blks { for fr in &blk.frames {
                let (pi, lk) = resolve(&plans, &pm, blk, fr);
                let f = Frame { calldata: &fr.cd, env: env(blk, fr), sload: None };
                let pl = match pi { Some(pi) => { sc.instantiate(&plans[pi], &f); plans[pi].kind as i32 } None => { sc.out.clear(); sc.c = Default::default(); -1 } };
                let keys: Vec<String> = sc.out.iter().map(|k| format!("{:064x}", k)).collect();
                writeln!(o, "{i}\t{}\t{}\t{pl}\t{lk}\t{}\t{}\t{}\t{}\t{}\t{}", blk.number, keys.len(), sc.c.records, sc.c.keccak, sc.c.cons_evals, sc.c.wide, sc.c.satsets, keys.join(",")).unwrap();
                i += 1;
            } }
        }
        "time" => {
            let r0 = rss_kb();
            let (plans, pm) = load_plans(&a[2]); let r1 = rss_kb();
            let blks = load_frames(&a[3]); let passes: usize = a[5].parse().unwrap();
            let mut sc = Scratch::default();
            // honour --interval / --improved in the timing mode as well
            sc.interval = interval; sc.improved = improved;
            let jobs: Vec<(usize, usize, Option<usize>, u32)> = blks.iter().enumerate().flat_map(|(bi, blk)| blk.frames.iter().enumerate().map(move |(fi, fr)| (bi, fi, fr))).map(|(bi, fi, fr)| {
                let (pi, lk) = resolve(&plans, &pm, &blks[bi], fr); (bi, fi, pi, lk) }).collect();
            let mut ns = vec![0u64; jobs.len() * passes];
            let mut cpu = vec![0u16; jobs.len() * passes]; // processor at the start of the timed region; 0x8000 set if it changed
            let tsc_aux = || { let mut a = 0u32; unsafe { core::arch::x86_64::__rdtscp(&mut a); } (a & 0xfff) as u16 };
            let mut cnt = vec![frame_plan::Counters::default(); jobs.len()]; let mut nk = vec![0u32; jobs.len()];
            for pass in 0..=passes {
                for (j, &(bi, fi, pi, _)) in jobs.iter().enumerate() {
                    let blk = &blks[bi]; let fr = &blk.frames[fi];
                    let c0 = tsc_aux();
                    let t = Instant::now();
                    let f = Frame { calldata: &fr.cd, env: env(blk, fr), sload: None };
                    if let Some(pi) = pi { sc.instantiate(&plans[pi], &f); } else { sc.out.clear(); }
                    let d = t.elapsed().as_nanos() as u64;
                    std::hint::black_box(&sc.out);
                    let c1 = tsc_aux();
                    if pass > 0 { ns[(pass - 1) * jobs.len() + j] = d; cpu[(pass - 1) * jobs.len() + j] = c0 | if c1 != c0 { 0x8000 } else { 0 }; } else { cnt[j] = sc.c; nk[j] = sc.out.len() as u32; }
                }
            }
            let mut o = std::io::BufWriter::new(std::fs::File::create(&a[4]).unwrap());
            writeln!(o, "i,block,{},{},records,keccak,cons_evals,satsets,family_alts,wide,lookups,n_keys,cdlen,has_plan", (1..=passes).map(|p| format!("ns_p{p}")).collect::<Vec<_>>().join(","), (1..=passes).map(|p| format!("cpu_p{p}")).collect::<Vec<_>>().join(",")).unwrap();
            for (j, &(bi, fi, pi, lk)) in jobs.iter().enumerate() {
                let c = cnt[j];
                writeln!(o, "{j},{},{},{},{},{},{},{},{},{},{},{},{},{}", blks[bi].number, (0..passes).map(|p| ns[p * jobs.len() + j].to_string()).collect::<Vec<_>>().join(","),
                    (0..passes).map(|p| cpu[p * jobs.len() + j].to_string()).collect::<Vec<_>>().join(","),
                    c.records, c.keccak, c.cons_evals, c.satsets, c.family_alts, c.wide, lk, nk[j], blks[bi].frames[fi].cd.len(), pi.is_some() as u8).unwrap();
            }
            eprintln!("plans {} rss_before_kb {} rss_after_plans_kb {} rss_end_kb {}", plans.len(), r0, r1, rss_kb());
        }
        "check" => {
            let (plans, pm) = load_plans(&a[2]); let blks = load_frames(&a[3]);
            let mut sc = Scratch::default(); sc.interval = true; sc.check = true; sc.improved = improved;
            let names: HashMap<usize, [u8; 32]> = pm.iter().map(|(k, v)| (*v, *k)).collect();
            // (plan, list, cap) -> (sets, mismatches)
            let mut g: std::collections::BTreeMap<(usize, u32, u32), (u64, u64)> = Default::default();
            let mut bad: Vec<String> = Vec::new(); let (mut nf, mut ns, mut nb) = (0u64, 0u64, 0u64);
            let mut cnt = frame_plan::SolveCounters::default();
            for blk in &blks { for fr in &blk.frames {
                let (pi, _) = resolve(&plans, &pm, blk, fr); nf += 1;
                let Some(pi) = pi else { continue };
                let f = Frame { calldata: &fr.cd, env: env(blk, fr), sload: None };
                sc.chk_first_bad = None;
                sc.instantiate(&plans[pi], &f);
                cnt.solved += sc.sc.solved; cnt.wrap_fallback += sc.sc.wrap_fallback; cnt.unk_all += sc.sc.unk_all; cnt.after_empty += sc.sc.after_empty;
                for &(li, cap, eq) in &sc.chk_log {
                    let e = g.entry((pi, li, cap)).or_default(); e.0 += 1; ns += 1;
                    if !eq { e.1 += 1; nb += 1; }
                }
                if let Some((li, cap, r, b)) = sc.chk_first_bad.take() {
                    if bad.len() < 20 { bad.push(format!("{} block {} list {li} cap {cap} interval {:?} valuewise {:?}", hexs(&names[&pi]), blk.number, r, b)); }
                }
            } }
            let mut o = std::io::BufWriter::new(std::fs::File::create(&a[4]).unwrap());
            writeln!(o, "codehash,list,cap,sets,mismatches").unwrap();
            for ((pi, li, cap), (n, m)) in &g { writeln!(o, "{},{li},{cap},{n},{m}", hexs(&names[pi])).unwrap(); }
            eprintln!("frames {nf} sets {ns} groups {} mismatches {nb} solved_conditions {} wrap_fallback {} unevaluable_all {} solved_after_empty {}", g.len(), cnt.solved, cnt.wrap_fallback, cnt.unk_all, cnt.after_empty);
            for b in bad { eprintln!("BAD {b}"); }
        }
        "time2" => {
            let (plans, pm) = load_plans(&a[2]);
            let blks = load_frames(&a[3]); let passes: usize = a[5].parse().unwrap();
            let mut sc = Scratch::default();
            let jobs: Vec<(usize, usize, Option<usize>)> = blks.iter().enumerate().flat_map(|(bi, blk)| blk.frames.iter().enumerate().map(move |(fi, fr)| (bi, fi, fr))).map(|(bi, fi, fr)| {
                let (pi, _) = resolve(&plans, &pm, &blks[bi], fr); (bi, fi, pi) }).collect();
            let nj = jobs.len();
            let mut ns = vec![0u64; nj * passes * 2];   // [(pass * 2 + method) * nj + j], method 0 old, 1 interval
            let mut cpu = vec![0u16; nj * passes * 2];
            let tsc_aux = || { let mut a = 0u32; unsafe { core::arch::x86_64::__rdtscp(&mut a); } (a & 0xfff) as u16 };
            let mut cnt = vec![[frame_plan::Counters::default(); 2]; nj]; let mut nk = vec![[0u32; 2]; nj];
            let mut sv = vec![frame_plan::SolveCounters::default(); nj];
            let mut order: Vec<(usize, usize)> = vec![(0, 0), (0, 1)];      // warm-up: old, interval
            for pass in 1..=passes { order.push((pass, 0)); order.push((pass, 1)); }
            let mut log = std::fs::OpenOptions::new().create(true).append(true).open(format!("{}.passes.log", &a[4])).unwrap();
            for &(pass, m) in &order {
                sc.interval = m == 1; sc.improved = m == 1 && improved;
                let t_pass = Instant::now();
                for (j, &(bi, fi, pi)) in jobs.iter().enumerate() {
                    let blk = &blks[bi]; let fr = &blk.frames[fi];
                    let c0 = tsc_aux();
                    let t = Instant::now();
                    let f = Frame { calldata: &fr.cd, env: env(blk, fr), sload: None };
                    if let Some(pi) = pi { sc.instantiate(&plans[pi], &f); } else { sc.out.clear(); }
                    let d = t.elapsed().as_nanos() as u64;
                    std::hint::black_box(&sc.out);
                    let c1 = tsc_aux();
                    if pass > 0 { let k = ((pass - 1) * 2 + m) * nj + j; ns[k] = d; cpu[k] = c0 | if c1 != c0 { 0x8000 } else { 0 }; }
                    else { cnt[j][m] = sc.c; nk[j][m] = sc.out.len() as u32; if m == 1 { sv[j] = sc.sc; } }
                }
                writeln!(log, "pass {pass} method {} wall_ms {:.3}", if m == 0 { "old" } else if improved { "interval_improved" } else { "interval" }, t_pass.elapsed().as_secs_f64() * 1e3).unwrap();
            }
            let mut o = std::io::BufWriter::new(std::fs::File::create(&a[4]).unwrap());
            let mut hdr = vec!["i".to_string(), "block".to_string()];
            for m in ["old", "int"] { for p in 1..=passes { hdr.push(format!("ns_{m}_p{p}")); } }
            for m in ["old", "int"] { for p in 1..=passes { hdr.push(format!("cpu_{m}_p{p}")); } }
            for m in ["old", "int"] { for c in ["cons_evals", "satsets", "keccak", "n_keys"] { hdr.push(format!("{c}_{m}")); } }
            for c in ["solved", "wrap_fallback", "unk_all", "rest_evals", "family_alts", "records", "cdlen", "has_plan"] { hdr.push(c.to_string()); }
            writeln!(o, "{}", hdr.join(",")).unwrap();
            for (j, &(bi, fi, pi)) in jobs.iter().enumerate() {
                let mut r = vec![j.to_string(), blks[bi].number.to_string()];
                for m in 0..2 { for p in 0..passes { r.push(ns[(p * 2 + m) * nj + j].to_string()); } }
                for m in 0..2 { for p in 0..passes { r.push(cpu[(p * 2 + m) * nj + j].to_string()); } }
                for m in 0..2 { let c = cnt[j][m]; r.extend([c.cons_evals.to_string(), c.satsets.to_string(), c.keccak.to_string(), nk[j][m].to_string()]); }
                let v = sv[j]; let c = cnt[j][0];
                r.extend([v.solved.to_string(), v.wrap_fallback.to_string(), v.unk_all.to_string(), v.rest_evals.to_string(), c.family_alts.to_string(), c.records.to_string(), blks[bi].frames[fi].cd.len().to_string(), (pi.is_some() as u8).to_string()]);
                writeln!(o, "{}", r.join(",")).unwrap();
            }
            let bad = (0..nj).filter(|&j| nk[j][0] != nk[j][1]).count();
            eprintln!("frames {nj} passes {passes} key_count_mismatch_old_vs_interval {bad}");
        }
        #[cfg(feature = "prof")]
        "prof" => {
            let (plans, pm) = load_plans(&a[2]); let blks = load_frames(&a[3]);
            let mut sc = Scratch::default(); sc.interval = interval; sc.improved = improved; sc.prof_cond = !nocond;
            let mut o = std::io::BufWriter::new(std::fs::File::create(&a[4]).unwrap());
            let cls: Vec<String> = (0..=frame_plan::N_CLS).map(|k| k.to_string()).collect();
            writeln!(o, "i,block,codehash,total,sfree,sat,solve,multi,keys,{},{},solve_n,multi_n,keys_n,keccak,satsets,sat_full,sat_full_n,sat_n",
                cls.iter().map(|k| format!("cyc_c{k}")).collect::<Vec<_>>().join(","), cls.iter().map(|k| format!("n_c{k}")).collect::<Vec<_>>().join(",")).unwrap();
            // warm-up pass (not written), then one recorded pass
            for rec in 0..2 { let mut i = 0usize; for blk in &blks { for fr in &blk.frames {
                let (pi, _) = resolve(&plans, &pm, blk, fr);
                let f = Frame { calldata: &fr.cd, env: env(blk, fr), sload: None };
                if let Some(pi) = pi { sc.instantiate(&plans[pi], &f); } else { sc.out.clear(); sc.prof = Default::default(); sc.c = Default::default(); }
                if rec == 1 {
                    let q = sc.prof;
                    writeln!(o, "{i},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}", blk.number, hexs(&fr.ch), q.total, q.sfree, q.sat, q.solve, q.multi, q.keys,
                        q.cond_cyc.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(","), q.cond_n.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(","),
                        q.solve_n, q.multi_n, q.keys_n, sc.c.keccak, sc.c.satsets, q.sat_full, q.sat_full_n, q.sat_n).unwrap();
                }
                i += 1;
            } } }
        }
        "forms" => {   // fp_run forms PLANS_DIR CODEHASH : single-index conditions with their class
            let b = std::fs::read(format!("{}/{}.eapf", a[2], a[3])).unwrap(); let p = Plan::parse_analyzed(&b);
            for li in 0..p.sl_id.len() { if p.sl_id[li] == frame_plan::NONE32 { continue; }
                for &it in p.list_items(li as u32) { let j = it & 0x7FFF_FFFF;
                    println!("list {li}\tidx {}\tclass {}\twant {}\t{}", p.sl_id[li], p.cls[j as usize], it >> 31, p.fmt_node(j, 0)); } }
        }
        "load2" => {
            let dir = &a[2]; let list: Vec<String> = std::fs::read_to_string(&a[3]).unwrap().split_whitespace().map(|s| s.to_string()).collect();
            let reps: usize = a[5].parse().unwrap();
            let mut o = std::io::BufWriter::new(std::fs::File::create(&a[4]).unwrap());
            writeln!(o, "codehash,bytes,{},{}", (1..=reps).map(|r| format!("ns_plain_r{r}")).collect::<Vec<_>>().join(","), (1..=reps).map(|r| format!("ns_analyzed_r{r}")).collect::<Vec<_>>().join(",")).unwrap();
            for ch in &list { let _ = std::fs::read(format!("{dir}/{ch}.eapf")).unwrap(); } // page cache hot
            let mut t = vec![vec![[0u64; 2]; list.len()]; reps];
            for r in 0..reps { for (i, ch) in list.iter().enumerate() { for m in 0..2 {
                let s = Instant::now(); let b = std::fs::read(format!("{dir}/{ch}.eapf")).unwrap();
                let p = if m == 0 { Plan::parse(&b) } else { Plan::parse_analyzed(&b) };
                t[r][i][m] = s.elapsed().as_nanos() as u64; std::hint::black_box(&p);
            } } }
            for (i, ch) in list.iter().enumerate() {
                let sz = std::fs::metadata(format!("{dir}/{ch}.eapf")).unwrap().len();
                writeln!(o, "{ch},{sz},{},{}", (0..reps).map(|r| t[r][i][0].to_string()).collect::<Vec<_>>().join(","), (0..reps).map(|r| t[r][i][1].to_string()).collect::<Vec<_>>().join(",")).unwrap();
            }
        }
        "load" => {
            let dir = &a[2]; let list: Vec<String> = std::fs::read_to_string(&a[3]).unwrap().split_whitespace().map(|s| s.to_string()).collect();
            let reps: usize = a[5].parse().unwrap();
            let mut o = std::io::BufWriter::new(std::fs::File::create(&a[4]).unwrap());
            writeln!(o, "codehash,bytes,{}", (1..=reps).map(|r| format!("ns_r{r}")).collect::<Vec<_>>().join(",")).unwrap();
            for ch in &list { let _ = std::fs::read(format!("{dir}/{ch}.eapf")).unwrap(); } // page cache hot
            let mut t = vec![vec![0u64; list.len()]; reps];
            let mut keep: Vec<Plan> = Vec::new();
            let r0 = rss_kb();
            for r in 0..reps { for (i, ch) in list.iter().enumerate() {
                let s = Instant::now(); let b = std::fs::read(format!("{dir}/{ch}.eapf")).unwrap(); let p = Plan::parse(&b);
                t[r][i] = s.elapsed().as_nanos() as u64;
                if r == 0 { keep.push(p); } else { std::hint::black_box(&p); }
            } }
            for (i, ch) in list.iter().enumerate() {
                let sz = std::fs::metadata(format!("{dir}/{ch}.eapf")).unwrap().len();
                writeln!(o, "{ch},{sz},{}", (0..reps).map(|r| t[r][i].to_string()).collect::<Vec<_>>().join(",")).unwrap();
            }
            eprintln!("plans {} rss_before_kb {} rss_after_kb {}", keep.len(), r0, rss_kb());
        }
        m => panic!("mode {m}"),
    }
}
