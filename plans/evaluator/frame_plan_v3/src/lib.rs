//! Single-frame storage access plan: loader and instantiator.
//!
//! optional satisfying-set cache by class. `set_sat_classes(true)` before loading
//! makes `Plan::analyze` class the single-index condition lists by exact structure with the solved loop index as a
//! placeholder (`Plan::sat_cls`; `Plan::classify_lists` does it for a plan already loaded); `Scratch::sat_classes` then
//! keys the frame's satisfying-set cache by class. Both off (the default): behaviour as at 40464f47. Outputs (keys, calls,
//! their family annotation, caps, holes) are the same either way. With both on, a
//! class hit skips the whole computation of a satisfying set, so the work counters (`c`, `solved`, `rest_evals`, ...),
//! `chk_log` and the number of storage-read callbacks made while solving conditions can be lower (the skipped reads repeat
//! keys already read in the frame). Turn `Scratch::sat_classes` on or off between frames only.
//!
//! copy (`src/frame_plan_v3`, from `src/frame_plan` = `reth/frame-plan-ctcs`, lib.rs sha256 431b7ff7):
//! file version 3 adds family call records (call groups that depend on a loop index, appended after the version-2
//! sections, see `Plan::parse`), expanded by `Scratch::instantiate_calls` with the same satisfying-set enumeration as the
//! family storage groups (`Scratch::family_assignments`). Version-1/2 plans give the same storage keys and calls as the
//! original library (README section 6).
//!
//! The plan is a mechanical encoding of the StateAccessSummary predictor's grouped summary records (see README.md).
//! Instantiation follows predict.py `Predictor._frame` at level 1 (no call following) with PRED_TAGS=1,
//! FAMILY_IFREE_CONS=sel, TIER_POLICY=t0t1 and a storage oracle that always raises Unknown; expression evaluation
//! follows evm_static_v2.py `evaluate` / `eval_segments` / `eval_region`.

use alloy_primitives::{keccak256, U256};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};

/// whether `Plan::analyze` classes the single-index condition lists (see the crate header; off by default)
static SAT_CLASSES: AtomicBool = AtomicBool::new(false);
/// turn the load-time classing of condition lists on or off for plans analyzed afterwards
pub fn set_sat_classes(on: bool) { SAT_CLASSES.store(on, Ordering::Relaxed); }

pub const T_CONST: u32 = 0;
pub const T_CD: u32 = 1;
pub const T_ENV: u32 = 2;
pub const T_LIN: u32 = 3;
pub const T_OP: u32 = 4;
pub const T_KEC: u32 = 5;
pub const T_KECB: u32 = 6;
pub const T_BYTES: u32 = 7;
pub const T_REGCD: u32 = 8;
pub const T_IDX: u32 = 9;
/// storage read in a call record's target / argument / constraint expression; child a = key node.
/// Served by `Frame::sload`, unknown when absent. Only call records may contain it (export keeps site keys unchanged).
pub const T_SLOAD: u32 = 10;
/// value of an argument word the exporter could not convert (exporter option --unkval): never evaluates.
/// sub 0: a word (its nb bytes are unknown), sub 1: a REGION (unknown from its offset to the end of the buffer).
/// Version-1/2 rule (`payload` without `pyoff`): a call record containing one has an unknown payload, as the exporter
/// without --unkval drops such payloads.
pub const T_UNK: u32 = 11;
pub const NONE32: u32 = 0xFFFF_FFFF;
pub const HI_NONE: u32 = 0x7FFF_FFFF;
/// family call assignments per call group: the first MAX_FAMILY_CALLS of the deduplicated assignments in
/// ascending (key 0, key 1) order, as predict.py `MAX_FAMILY_CALLS` (`for n, asg in enumerate(sorted(asgs))`).
pub const MAX_FAMILY_CALLS: usize = 512;
/// family call assignments per frame over all family call groups (no counterpart in predict.py; bounds the
/// work per frame). Assignments beyond either cap are counted in `Scratch::c_family_capped`.
pub const MAX_FAMILY_CALLS_FRAME: usize = 4096;
/// predict.py MAX_FAMILY under the export environment (iterations of an argument word with an expression offset)
const MAX_FAMILY: u32 = 512;
pub const N_ENV: usize = 14; // CALLER ORIGIN ADDRESS CALLVALUE CALLDATASIZE NUMBER TIMESTAMP CHAINID COINBASE GASLIMIT BASEFEE PREVRANDAO BLOBBASEFEE CODESIZE

// opcode ids (scripts/eap_plan_export.py OPS order)
const ADD: u32 = 0; const MUL: u32 = 1; const SUB: u32 = 2; const DIV: u32 = 3; const SDIV: u32 = 4; const MOD: u32 = 5;
const SMOD: u32 = 6; const ADDMOD: u32 = 7; const MULMOD: u32 = 8; const EXP: u32 = 9; const SIGNEXTEND: u32 = 10;
const LT: u32 = 11; const GT: u32 = 12; const SLT: u32 = 13; const SGT: u32 = 14; const EQ: u32 = 15; const ISZERO: u32 = 16;
const AND: u32 = 17; const OR: u32 = 18; const XOR: u32 = 19; const NOT: u32 = 20; const BYTE: u32 = 21; const SHL: u32 = 22;
const SHR: u32 = 23; const SAR: u32 = 24;

#[derive(Clone, Copy, Debug)]
pub struct Node { pub w0: u32, pub a: u32, pub b: u32, pub n: u32 }
impl Node {
    #[inline] fn tag(&self) -> u32 { self.w0 & 0xff }
    #[inline] fn sub(&self) -> u32 { (self.w0 >> 8) & 0xff }
    #[inline] fn dep(&self) -> bool { (self.w0 >> 16) & 1 == 1 }
}

#[derive(Default)]
pub struct Plan {
    pub kind: u32, // 0 plan, 1 EIP-7702 delegate, 2 no summary
    pub delegate: [u8; 20],
    pub consts: Vec<U256>,
    pub nodes: Vec<Node>,
    pub side: Vec<u32>,
    pub list_off: Vec<u32>,
    pub list_data: Vec<u32>,
    pub sgroups: Vec<u32>,
    pub salts: Vec<[u32; 4]>,  // group, has_sel, sel, list
    pub fgroups: Vec<[u32; 4]>, // key node, nkey, key id 0, key id 1
    pub falts: Vec<[u32; 9]>,  // group, has_sel, sel, off, n_extra_sel, n_fixed, key list 0, key list 1, multi list
    pub side2: Vec<u32>,
    pub n_idx: u32,
    // ---- call records (file version 2); index-free groups only
    /// [kind (0 CALL, 1 CALLCODE, 2 DELEGATECALL, 3 STATICCALL), target node, argsize node (NONE32: payload unknown),
    ///  cside offset, number of argument words, flags]
    pub cgroups: Vec<[u32; 6]>,
    /// per argument word: [offset node (i64 two's complement after evaluation), value node, byte count (NONE32: 32)]
    pub cside: Vec<u32>,
    pub calts: Vec<[u32; 4]>, // group, has_sel, sel, list (as salts)
    /// call groups skipped at export because they depend on a loop index (informational; version 3 exports them below)
    pub n_family_calls: u32,
    // ---- file version; family call records (file version 3)
    pub version: u32,
    /// [kind, target node, argsize node (NONE32: payload unknown), cside offset, n argwords, nkey, key id 0, key id 1];
    /// argument words in `cside` as for `cgroups`, their nodes may depend on the key indices
    pub fcgroups: Vec<[u32; 8]>,
    /// family-site alternative layout over fcgroups / cside2: [group, has_sel, sel, cside2 offset, n_extra_sel, n_fixed,
    /// key list 0, key list 1, multi list]
    pub fcalts: Vec<[u32; 9]>,
    /// extra selectors and (index, list) pairs of the fixed indices of `fcalts` (as `side2` for `falts`)
    pub cside2: Vec<u32>,
    fc_generic: usize,
    fc_sel: Vec<(u32, u32, u32)>,
    c_generic: usize,
    c_sel: Vec<(u32, u32, u32)>,
    s_generic: usize,          // salts[..s_generic] carry no selector
    s_sel: Vec<(u32, u32, u32)>, // (sel, start, end) into salts
    f_generic: usize,
    f_sel: Vec<(u32, u32, u32)>,
    // ---- per single-index condition list, the conditions solved directly as intervals
    pub analyzed: bool,
    pub sl_id: Vec<u32>,               // loop index of a single-index list (NONE32: not a single-index list)
    pub sl_off: Vec<[u32; 3]>,         // per list: solved items [s0, s1) in sl_shape, remaining items [r0, r1) in sl_rest
    pub sl_shape: Vec<Shape>,
    pub sl_rest: Vec<u32>,             // list_data-format items checked value by value
    pub cls: Vec<u8>,                  // condition form class per node (CLS_*), 255 when not classified
    /// per list, the representative of its class (single-index lists equal in
    /// structure with the solved index as a placeholder), NONE32 for a list given more than one index, the list itself
    /// otherwise; empty when not classed. Single-index lists, classes, lists given more than one index.
    pub sat_cls: Vec<u32>, pub n_sat_lists: u32, pub n_sat_classes: u32, pub n_sl_conflict: u32,
}

/// Condition form classes, in priority order 4, 3, 1, 2, 5.
pub const CLS_LIN_CONST: u8 = 0; // LT/GT/SLT/SGT: linear in the index vs. an index-free constant
pub const CLS_LIN_INPUT: u8 = 1; // ... vs. an index-free value depending on calldata or environment fields
pub const CLS_EQ: u8 = 2;        // EQ (linear vs. index-free) or the linear expression itself (!= 0 / == 0)
pub const CLS_MODBIT: u8 = 3;    // index-dependent subtree contains modulo, division or bitwise operations
pub const CLS_MAYFAIL: u8 = 4;   // index-dependent subtree contains byte concatenation, keccak over bytes or a calldata region
pub const CLS_OTHER: u8 = 5;     // anything else (e.g. calldata read at an index-dependent offset, both sides index-dependent)
pub const N_CLS: usize = 6;

/// A directly solvable single-index condition: (cmp(f(i), c) == want), f affine in the index.
#[derive(Clone, Copy, Debug)]
pub struct Shape { pub op: u8 /* 0: f < c, 1: f > c, 2: f == c */, pub signed: bool, pub want: bool, pub f: u32, pub c: u32 /* NONE32: 0 */, pub cls: u8 }

pub struct Reader<'a> { b: &'a [u8], p: usize }
impl<'a> Reader<'a> {
    fn u32(&mut self) -> u32 { let v = u32::from_le_bytes(self.b[self.p..self.p + 4].try_into().unwrap()); self.p += 4; v }
    fn u32s(&mut self, n: usize) -> Vec<u32> {
        let s = &self.b[self.p..self.p + 4 * n]; self.p += 4 * n;
        s.chunks_exact(4).map(|c| u32::from_le_bytes(c.try_into().unwrap())).collect()
    }
    fn arr<const K: usize>(&mut self, n: usize) -> Vec<[u32; K]> {
        let v = self.u32s(n * K); v.chunks_exact(K).map(|c| c.try_into().unwrap()).collect()
    }
}

fn sel_ranges<const K: usize>(alts: &[[u32; K]]) -> (usize, Vec<(u32, u32, u32)>) {
    let g = alts.iter().take_while(|a| a[1] == 0).count();
    let mut out = Vec::new();
    let mut i = g;
    while i < alts.len() {
        let s = alts[i][2]; let st = i;
        while i < alts.len() && alts[i][2] == s { i += 1; }
        out.push((s, st as u32, i as u32));
    }
    (g, out)
}

impl Plan {
    pub fn parse(b: &[u8]) -> Plan {
        assert!(&b[0..4] == b"EAPF", "bad magic");
        let mut r = Reader { b, p: 4 };
        let ver = r.u32(); assert!((1..=3).contains(&ver), "bad version {ver}");
        let mut p = Plan { kind: r.u32(), version: ver, ..Default::default() };
        if p.kind == 1 { p.delegate.copy_from_slice(&b[12..32]); return p; }
        if p.kind == 2 { return p; }
        let nc = r.u32() as usize;
        p.consts = (0..nc).map(|i| U256::from_be_slice(&b[r.p + 32 * i..r.p + 32 * i + 32])).collect(); r.p += 32 * nc;
        let nn = r.u32() as usize;
        p.nodes = r.arr::<4>(nn).into_iter().map(|w| Node { w0: w[0], a: w[1], b: w[2], n: w[3] }).collect();
        let ns = r.u32() as usize; p.side = r.u32s(ns);
        let nl = r.u32() as usize; p.list_off = r.u32s(nl + 1);
        let nd = r.u32() as usize; p.list_data = r.u32s(nd);
        let ng = r.u32() as usize; p.sgroups = r.u32s(ng);
        let na = r.u32() as usize; p.salts = r.arr::<4>(na);
        let nf = r.u32() as usize; p.fgroups = r.arr::<4>(nf);
        let nfa = r.u32() as usize; p.falts = r.arr::<9>(nfa);
        let n2 = r.u32() as usize; p.side2 = r.u32s(n2);
        p.n_idx = r.u32();
        if ver >= 2 {
            let ncg = r.u32() as usize; p.cgroups = r.arr::<6>(ncg);
            let ncs = r.u32() as usize; p.cside = r.u32s(ncs);
            let nca = r.u32() as usize; p.calts = r.arr::<4>(nca);
            p.n_family_calls = r.u32();
        }
        if ver >= 3 {
            let n = r.u32() as usize; p.fcgroups = r.arr::<8>(n);
            let n = r.u32() as usize; p.fcalts = r.arr::<9>(n);
            let n = r.u32() as usize; p.cside2 = r.u32s(n);
        }
        assert_eq!(r.p, b.len());
        let (g, s) = sel_ranges(&p.salts); p.s_generic = g; p.s_sel = s;
        let (g, s) = sel_ranges(&p.falts); p.f_generic = g; p.f_sel = s;
        let (g, s) = sel_ranges(&p.calts); p.c_generic = g; p.c_sel = s;
        let (g, s) = sel_ranges(&p.fcalts); p.fc_generic = g; p.fc_sel = s;
        p
    }
    /// the file `parse` read (same version; `parse(b).to_bytes() == b` for every exported file)
    pub fn to_bytes(&self) -> Vec<u8> {
        fn w(o: &mut Vec<u8>, x: u32) { o.extend_from_slice(&x.to_le_bytes()); }
        fn ws(o: &mut Vec<u8>, v: &[u32]) { for &x in v { w(o, x); } }
        fn wl(o: &mut Vec<u8>, v: &[u32]) { w(o, v.len() as u32); ws(o, v); }
        fn wa<const K: usize>(o: &mut Vec<u8>, v: &[[u32; K]]) { w(o, v.len() as u32); for r in v { ws(o, r); } }
        let mut o = b"EAPF".to_vec();
        w(&mut o, self.version); w(&mut o, self.kind);
        if self.kind == 1 { o.extend_from_slice(&self.delegate); return o; }
        if self.kind == 2 { return o; }
        w(&mut o, self.consts.len() as u32); for c in &self.consts { o.extend_from_slice(&c.to_be_bytes::<32>()); }
        w(&mut o, self.nodes.len() as u32); for n in &self.nodes { ws(&mut o, &[n.w0, n.a, n.b, n.n]); }
        wl(&mut o, &self.side);
        w(&mut o, self.n_lists() as u32); ws(&mut o, &self.list_off); wl(&mut o, &self.list_data);
        wl(&mut o, &self.sgroups); wa(&mut o, &self.salts); wa(&mut o, &self.fgroups); wa(&mut o, &self.falts);
        wl(&mut o, &self.side2); w(&mut o, self.n_idx);
        if self.version >= 2 { wa(&mut o, &self.cgroups); wl(&mut o, &self.cside); wa(&mut o, &self.calts); w(&mut o, self.n_family_calls); }
        if self.version >= 3 { wa(&mut o, &self.fcgroups); wa(&mut o, &self.fcalts); wl(&mut o, &self.cside2); }
        o
    }
    /// loop index ids occurring in the subtree of node j (appended to `out`, unsorted, may repeat)
    pub fn idx_ids(&self, j: u32, out: &mut Vec<u32>) {
        let mut st = vec![j]; let mut ch = Vec::new();
        while let Some(x) = st.pop() {
            let nd = self.nodes[x as usize];
            if !nd.dep() { continue; }
            if nd.tag() == T_IDX { out.push(nd.a); continue; }
            ch.clear(); self.children(x, &mut ch); st.extend_from_slice(&ch);
        }
    }
    /// parse + condition analysis (needed by the interval solver and by the profiling counters)
    pub fn parse_analyzed(b: &[u8]) -> Plan { let mut p = Plan::parse(b); p.analyze(); p }

    fn children(&self, j: u32, out: &mut Vec<u32>) {
        let nd = self.nodes[j as usize]; let b = nd.b as usize; let n = nd.n as usize;
        match nd.tag() {
            T_CD | T_SLOAD => out.push(nd.a),
            T_LIN => for k in 0..n { out.push(self.side[b + 2 * k + 1]) },
            T_OP | T_KEC => for k in 0..n { out.push(self.side[b + k]) },
            T_KECB | T_BYTES => for k in 0..n { out.push(self.side[b + 3 * k]) },
            T_REGCD => { out.push(nd.a); out.push(nd.b) }
            _ => {}
        }
    }
    #[inline] fn dep(&self, j: u32) -> bool { self.nodes[j as usize].dep() }
    /// affine in loop index `id`: built from IDX(id), LIN, ADD, SUB, MUL by an index-free factor and index-free subtrees
    fn is_affine(&self, j: u32, id: u32) -> bool {
        let nd = self.nodes[j as usize];
        if !nd.dep() { return true; }
        match nd.tag() {
            T_IDX => nd.a == id,
            T_LIN => (0..nd.n as usize).all(|k| self.is_affine(self.side[nd.b as usize + 2 * k + 1], id)),
            T_OP => {
                let (x, y) = (self.side[nd.b as usize], self.side[nd.b as usize + 1]);
                match nd.sub() {
                    ADD | SUB => self.is_affine(x, id) && self.is_affine(y, id),
                    MUL => (!self.dep(x) && self.is_affine(y, id)) || (!self.dep(y) && self.is_affine(x, id)),
                    _ => false,
                }
            }
            _ => false,
        }
    }
    /// (has modulo/bitwise op, has may-fail node) in the index-dependent part of the subtree of j
    fn dep_scan(&self, j: u32) -> (bool, bool) {
        let mut st = vec![j]; let mut ch = Vec::new(); let (mut mb, mut mf) = (false, false);
        while let Some(x) = st.pop() {
            let nd = self.nodes[x as usize];
            if !nd.dep() { continue; }
            match nd.tag() {
                T_OP => if !matches!(nd.sub(), ADD | SUB | MUL | LT | GT | SLT | SGT | EQ | ISZERO) { mb = true },
                T_KECB | T_BYTES | T_REGCD => mf = true,
                _ => {}
            }
            ch.clear(); self.children(x, &mut ch); st.extend_from_slice(&ch);
        }
        (mb, mf)
    }
    fn reads_input(&self, j: u32) -> bool {
        let mut st = vec![j]; let mut ch = Vec::new();
        while let Some(x) = st.pop() {
            if matches!(self.nodes[x as usize].tag(), T_CD | T_ENV | T_REGCD | T_SLOAD) { return true; }
            ch.clear(); self.children(x, &mut ch); st.extend_from_slice(&ch);
        }
        false
    }
    /// classify one condition item (list_data format) of a single-index list over loop index `id`
    pub fn classify(&self, it: u32, id: u32) -> (u8, Option<Shape>) {
        let (mut j, mut want) = (it & 0x7FFF_FFFF, it >> 31 == 1);
        loop {
            let nd = self.nodes[j as usize];
            if nd.tag() == T_OP && nd.sub() == ISZERO { j = self.side[nd.b as usize]; want = !want; continue; }
            break;
        }
        let (mb, mf) = self.dep_scan(j);
        if mf { return (CLS_MAYFAIL, None); }
        if mb { return (CLS_MODBIT, None); }
        let nd = self.nodes[j as usize];
        if nd.tag() == T_OP && matches!(nd.sub(), LT | GT | SLT | SGT | EQ) {
            let (x, y) = (self.side[nd.b as usize], self.side[nd.b as usize + 1]);
            let o = nd.sub();
            let base = match o { LT | SLT => 0u8, GT | SGT => 1, _ => 2 };
            let signed = matches!(o, SLT | SGT);
            let sh = if self.dep(x) && !self.dep(y) && self.is_affine(x, id) { Some((x, y, base)) }
                     else if !self.dep(x) && self.dep(y) && self.is_affine(y, id) { Some((y, x, match base { 0 => 1, 1 => 0, b => b })) }
                     else { None };
            if let Some((f, c, op)) = sh {
                let cls = if op == 2 { CLS_EQ } else if self.reads_input(c) { CLS_LIN_INPUT } else { CLS_LIN_CONST };
                return (cls, Some(Shape { op, signed, want, f, c, cls }));
            }
            return (CLS_OTHER, None);
        }
        if nd.dep() && self.is_affine(j, id) {
            // truthy(f) == want  <=>  (f == 0) == !want
            return (CLS_EQ, Some(Shape { op: 2, signed: false, want: !want, f: j, c: NONE32, cls: CLS_EQ }));
        }
        (CLS_OTHER, None)
    }
    /// readable form of node j (debugging and the README's condition examples)
    pub fn fmt_node(&self, j: u32, depth: u32) -> String {
        if depth > 12 { return "…".into(); }
        const OPN: [&str; 25] = ["ADD","MUL","SUB","DIV","SDIV","MOD","SMOD","ADDMOD","MULMOD","EXP","SIGNEXTEND","LT","GT","SLT","SGT","EQ","ISZERO","AND","OR","XOR","NOT","BYTE","SHL","SHR","SAR"];
        const ENV: [&str; 14] = ["CALLER","ORIGIN","ADDRESS","CALLVALUE","CALLDATASIZE","NUMBER","TIMESTAMP","CHAINID","COINBASE","GASLIMIT","BASEFEE","PREVRANDAO","BLOBBASEFEE","CODESIZE"];
        let nd = self.nodes[j as usize]; let mut ch = Vec::new(); self.children(j, &mut ch);
        let args = |s: &Self| ch.iter().map(|&c| s.fmt_node(c, depth + 1)).collect::<Vec<_>>().join(", ");
        match nd.tag() {
            T_CONST => { let v = self.consts[nd.a as usize]; if v < U256::from(1u64 << 32) { format!("{v}") } else { format!("0x{v:x}") } }
            T_IDX => format!("i{}", nd.a),
            T_ENV => ENV[nd.sub() as usize].into(),
            T_CD => format!("CD({})", args(self)),
            T_SLOAD => format!("SLOAD({})", args(self)),
            T_LIN => { let mut t = vec![self.fmt_node_c(nd.a)]; for k in 0..nd.n as usize { let o = nd.b as usize + 2 * k; t.push(format!("{}*{}", self.fmt_node_c(self.side[o]), self.fmt_node(self.side[o + 1], depth + 1))); } format!("LIN({})", t.join(" + ")) }
            T_OP => format!("{}({})", OPN[nd.sub() as usize], args(self)),
            T_KEC => format!("KEC({})", args(self)), T_KECB => format!("KECB({})", args(self)), T_UNK => "UNK".into(),
            T_BYTES => format!("BYTES({})", args(self)), T_REGCD => format!("REGION_CD({})", args(self)),
            t => format!("?{t}"),
        }
    }
    fn fmt_node_c(&self, c: u32) -> String { let v = self.consts[c as usize]; if v < U256::from(1u64 << 32) { format!("{v}") } else { format!("0x{v:x}") } }
    /// interned structural form of node j with loop index `id` as a placeholder (other indices by number);
    /// equal results mean equal node kind, sub-kind, dependency flag, constant values, child forms and remaining fields
    fn canon(&self, j: u32, id: u32, intern: &mut HashMap<Vec<u64>, u32>, memo: &mut HashMap<(u32, u32), u32>) -> u32 {
        let nd = self.nodes[j as usize];
        let mk = (j, if nd.dep() { id } else { NONE32 });
        if let Some(&v) = memo.get(&mk) { return v; }
        let (b, n) = (nd.b as usize, nd.n as usize);
        let mut k: Vec<u64> = vec![nd.tag() as u64, nd.sub() as u64, nd.dep() as u64];
        match nd.tag() {
            T_CONST => k.extend_from_slice(self.consts[nd.a as usize].as_limbs()),
            T_IDX => { if nd.a == id { k.push(1) } else { k.push(0); k.push(nd.a as u64) } }
            T_ENV => {}
            T_CD | T_SLOAD => { let c = self.canon(nd.a, id, intern, memo); k.push(c as u64) }
            T_LIN => {
                k.extend_from_slice(self.consts[nd.a as usize].as_limbs()); k.push(n as u64);
                for i in 0..n {
                    k.extend_from_slice(self.consts[self.side[b + 2 * i] as usize].as_limbs());
                    let c = self.canon(self.side[b + 2 * i + 1], id, intern, memo); k.push(c as u64);
                }
            }
            T_OP | T_KEC => { k.push(n as u64); for i in 0..n { let c = self.canon(self.side[b + i], id, intern, memo); k.push(c as u64); } }
            T_KECB | T_BYTES => {
                k.push(n as u64);
                for i in 0..n {
                    let c = self.canon(self.side[b + 3 * i], id, intern, memo);
                    k.push(c as u64); k.push(self.side[b + 3 * i + 1] as u64); k.push(self.side[b + 3 * i + 2] as u64);
                }
            }
            T_REGCD => { let c1 = self.canon(nd.a, id, intern, memo); let c2 = self.canon(nd.b, id, intern, memo); k.push(c1 as u64); k.push(c2 as u64) }
            _ => { k.push(nd.a as u64); k.push(nd.b as u64); k.push(nd.n as u64); }
        }
        let next = intern.len() as u32;
        let v = *intern.entry(k).or_insert(next);
        memo.insert(mk, v);
        v
    }
    /// class the single-index condition lists of an analyzed plan (idempotent): lists equal in structure
    /// with the solved index (`sl_id`) as a placeholder share the first one's slot in the satisfying-set cache; a list given
    /// more than one loop index joins no class (its requests keep one per-list slot, as the cache by list does)
    pub fn classify_lists(&mut self) {
        if !self.analyzed || self.kind != 0 || !self.sat_cls.is_empty() { return; }
        let nl = self.n_lists();
        let mut bad = vec![false; nl];
        for al in &self.falts {
            let off = al[3] as usize; let nx = al[4] as usize; let nfix = al[5] as usize;
            for k in 0..nfix { let (id, li) = (self.side2[off + nx + 2 * k], self.side2[off + nx + 2 * k + 1]); if self.sl_id[li as usize] != id { bad[li as usize] = true; } }
            let fg = self.fgroups[al[0] as usize];
            for k in 0..fg[1] as usize { let li = al[6 + k]; if li != NONE32 && self.sl_id[li as usize] != fg[2 + k] { bad[li as usize] = true; } }
        }
        for al in &self.fcalts {
            let off = al[3] as usize; let nx = al[4] as usize; let nfix = al[5] as usize;
            for k in 0..nfix { let (id, li) = (self.cside2[off + nx + 2 * k], self.cside2[off + nx + 2 * k + 1]); if self.sl_id[li as usize] != id { bad[li as usize] = true; } }
            let fg = self.fcgroups[al[0] as usize];
            for k in 0..fg[5] as usize { let li = al[6 + k]; if li != NONE32 && self.sl_id[li as usize] != fg[6 + k] { bad[li as usize] = true; } }
        }
        self.n_sl_conflict = bad.iter().filter(|&&x| x).count() as u32;
        let mut intern: HashMap<Vec<u64>, u32> = HashMap::new();
        let mut memo: HashMap<(u32, u32), u32> = HashMap::new();
        let mut cls_of: HashMap<Vec<u64>, u32> = HashMap::new();
        let mut cls: Vec<u32> = (0..nl as u32).collect();
        for li in 0..nl {
            let id = self.sl_id[li];
            if id == NONE32 { continue; }
            self.n_sat_lists += 1;
            if bad[li] { cls[li] = NONE32; continue; }
            let items: Vec<u32> = self.list(li as u32).to_vec();
            let key: Vec<u64> = items.iter().map(|&it| (((it >> 31) as u64) << 32) | self.canon(it & 0x7FFF_FFFF, id, &mut intern, &mut memo) as u64).collect();
            let n0 = cls_of.len();
            let c = *cls_of.entry(key).or_insert(li as u32);
            if cls_of.len() > n0 { self.n_sat_classes += 1; }
            cls[li] = c;
        }
        self.sat_cls = cls;
    }
    pub fn analyze(&mut self) {
        if self.analyzed || self.kind != 0 { self.analyzed = true; return; }
        let nl = self.n_lists();
        self.sl_id = vec![NONE32; nl]; self.cls = vec![255; self.nodes.len()];
        for al in &self.falts {
            let off = al[3] as usize; let nx = al[4] as usize; let nfix = al[5] as usize;
            for k in 0..nfix { let (id, li) = (self.side2[off + nx + 2 * k], self.side2[off + nx + 2 * k + 1]); self.sl_id[li as usize] = id; }
            let fg = self.fgroups[al[0] as usize];
            for k in 0..fg[1] as usize { let li = al[6 + k]; if li != NONE32 { self.sl_id[li as usize] = fg[2 + k]; } }
        }
        // single-index lists of the family call alternatives (a list's items all name the same index, so a list
        // shared with a family site alternative gets the same id)
        for al in &self.fcalts {
            let off = al[3] as usize; let nx = al[4] as usize; let nfix = al[5] as usize;
            for k in 0..nfix { let (id, li) = (self.cside2[off + nx + 2 * k], self.cside2[off + nx + 2 * k + 1]); self.sl_id[li as usize] = id; }
            let fg = self.fcgroups[al[0] as usize];
            for k in 0..fg[5] as usize { let li = al[6 + k]; if li != NONE32 { self.sl_id[li as usize] = fg[6 + k]; } }
        }
        self.sl_off = vec![[0; 3]; nl];
        let (mut sh, mut rest) = (Vec::new(), Vec::new());
        for li in 0..nl {
            let id = self.sl_id[li];
            let s0 = sh.len() as u32; let r0 = rest.len() as u32;
            if id != NONE32 {
                let items: Vec<u32> = self.list(li as u32).to_vec();
                for it in items {
                    let (c, s) = self.classify(it, id);
                    self.cls[(it & 0x7FFF_FFFF) as usize] = c;
                    match s { Some(s) => sh.push(s), None => rest.push(it) }
                }
            }
            self.sl_off[li] = [s0, sh.len() as u32, r0]; // remaining items end at the next list's r0 (rest_range)
        }
        self.sl_shape = sh; self.sl_rest = rest;
        self.analyzed = true;
        if SAT_CLASSES.load(Ordering::Relaxed) { self.classify_lists(); }
    }
    #[inline] fn rest_range(&self, li: usize) -> (usize, usize) {
        let r0 = self.sl_off[li][2] as usize;
        let r1 = if li + 1 < self.sl_off.len() { self.sl_off[li + 1][2] as usize } else { self.sl_rest.len() };
        (r0, r1)
    }
    pub fn list_items(&self, i: u32) -> &[u32] { self.list(i) }
    pub fn n_lists(&self) -> usize { self.list_off.len().saturating_sub(1) }
    #[inline] fn list(&self, i: u32) -> &[u32] { &self.list_data[self.list_off[i as usize] as usize..self.list_off[i as usize + 1] as usize] }
    fn sel_range(v: &[(u32, u32, u32)], sel: u32) -> (usize, usize) {
        match v.binary_search_by_key(&sel, |x| x.0) { Ok(i) => (v[i].1 as usize, v[i].2 as usize), Err(_) => (0, 0) }
    }
}

/// Inputs of one frame. `env` slots follow N_ENV order.
pub struct Frame<'a> {
    pub calldata: &'a [u8],
    pub env: [U256; N_ENV],
    /// storage read callback for `T_SLOAD` nodes (key -> value); `None` makes every such node unknown.
    pub sload: Option<&'a dyn Fn(U256) -> Option<U256>>,
}

/// one call whose target concretised. `payload` is the callee's calldata when every argument
/// word evaluated (bytes no word covers are zero), `None` otherwise.
#[derive(Clone, Debug)]
pub struct CallOut { pub kind: u8, pub target: U256, pub payload: Option<Vec<u8>> }

#[derive(Clone, Copy, PartialEq, Debug)]
pub enum Fail { Unk, Wide }
type R = Result<U256, Fail>;

#[derive(Default, Clone, Copy, Debug)]
pub struct Counters { pub records: u32, pub keccak: u32, pub cons_evals: u32, pub wide: u32, pub family_alts: u32, pub satsets: u32 }

/// Reusable per-thread scratch space (memo of index-free nodes, selector-set cache, output buffer).
#[derive(Default)]
pub struct Scratch {
    stamp: u32,
    memo_stamp: Vec<u32>, memo_val: Vec<U256>, memo_ok: Vec<u8>,
    sat_stamp: Vec<u32>, sat_res: Vec<Vec<u16>>,
    done: Vec<u32>,
    asg: Vec<(u32, u16, u16)>,
    full: Vec<u16>,
    pub out: Vec<U256>,
    pub c: Counters,
    /// output of `instantiate_calls`
    pub calls: Vec<CallOut>,
    cdone: Vec<u32>,
    /// call records whose target evaluated but whose payload did not
    pub c_nopayload: u32,
    /// per entry of `calls`, the family call group and key index values (v0, v1) it came from; None for an
    /// index-free call group. Index-free calls come first, then family calls in (group, v0, v1) order.
    pub call_idx: Vec<Option<(u32, u16, u16)>>,
    /// family calls in `calls` after the last `instantiate_calls`
    pub c_family: u32,
    /// per entry of `calls`, the payload bytes no argument word covers (they read zero; predict.py with
    /// TIER_HOLE_UNKNOWN=1 treats them as unknown); 0 when the payload is unknown
    pub call_holes: Vec<u32>,
    /// family call assignments dropped by MAX_FAMILY_CALLS (per group) or MAX_FAMILY_CALLS_FRAME
    pub c_family_capped: u32,
    /// index-free call payloads of version-3 plans with the version-1/2 rule for argument words whose offset is
    /// an expression (evaluate it without loop indices, any failure makes the payload unknown) instead of predict.py's
    /// `_callargs` rule; family calls always use the latter. Version-1/2 plans always use the former.
    pub legacy_payload: bool,
    fasg: Vec<(u32, u16, u16)>,
    /// false = value-by-value check of single-index conditions, true = interval solving
    pub interval: bool,
    /// single division with 64-bit fast path, one-wrap affine values split into two pieces
    pub improved: bool,
    /// key the frame's satisfying-set cache by the plan's list classes (`Plan::sat_cls`); off: by list
    pub sat_classes: bool,
    /// solver check: compute every satisfying set both ways and log (list, cap, equal)
    pub check: bool,
    pub chk_log: Vec<(u32, u32, bool)>,
    pub chk_first_bad: Option<(u32, u32, Vec<u16>, Vec<u16>)>,
    fb: Vec<u32>,
    pub sc: SolveCounters,
    #[cfg(feature = "prof")]
    pub prof: Prof,
    #[cfg(feature = "prof")]
    pub prof_cond: bool, // time every per-value condition evaluation (rdtsc pair per evaluation)
}

/// interval-solver counters per frame
#[derive(Default, Clone, Copy, Debug)]
pub struct SolveCounters { pub solved: u32, pub wrap_fallback: u32, pub unk_all: u32, pub rest_evals: u32, pub after_empty: u32 }

/// profiling counters (rdtsc cycles, timer overhead included); built only with --features prof
#[cfg(feature = "prof")]
#[derive(Default, Clone, Copy, Debug)]
pub struct Prof {
    pub total: u64, pub sfree: u64, pub sat: u64, pub solve: u64, pub multi: u64, pub keys: u64,
    pub cond_cyc: [u64; N_CLS + 1], pub cond_n: [u64; N_CLS + 1], // per-value condition evaluations by class; [N_CLS] = solvable form fallen back (wrap)
    pub solve_n: u64, pub multi_n: u64, pub keys_n: u64,
    pub sat_full: u64, pub sat_full_n: u64, pub sat_n: u64, // satisfying-set time of lists whose conditions are all of a solvable form
}
#[cfg(feature = "prof")]
#[inline] fn tsc() -> u64 { unsafe { core::arch::x86_64::_rdtsc() } }

#[inline] fn mask_range(lo: u32, hi: u32) -> [u64; 8] {
    let mut m = [0u64; 8];
    if lo >= hi { return m; }
    for w in 0..8u32 {
        let (a, b) = (w * 64, w * 64 + 64);
        let (l, h) = (lo.max(a), hi.min(b));
        if l < h { let n = h - l; let bits = if n == 64 { u64::MAX } else { ((1u64 << n) - 1) << (l - a) }; m[w as usize] = bits; }
    }
    m
}

/// (d / a, d % a) with a 64-bit fast path (a != 0)
#[inline] fn divrem(d: U256, a: U256) -> (U256, U256) {
    let (dl, al) = (d.as_limbs(), a.as_limbs());
    if dl[1] | dl[2] | dl[3] == 0 && al[1] | al[2] | al[3] == 0 { return (U256::from(dl[0] / al[0]), U256::from(dl[0] % al[0])); }
    d.div_rem(a)
}

#[inline] fn shl512(m: [u64; 8], s: u32) -> [u64; 8] {
    let (w, b) = ((s / 64) as usize, s % 64); let mut o = [0u64; 8];
    for i in (w..8).rev() { let src = i - w; o[i] = m[src] << b; if b > 0 && src > 0 { o[i] |= m[src - 1] >> (64 - b); } }
    o
}

/// solve_affine without the signed transform, one division per piece
fn solve_unsigned2(a: U256, b: U256, c: U256, op: u8, want: bool, cap: u32) -> Option<[u64; 8]> {
    let full = mask_range(0, cap);
    if a.is_zero() {
        let base = match op { 0 => b < c, 1 => b > c, _ => b == c };
        return Some(if base == want { full } else { [0; 8] });
    }
    let n = U256::from(cap - 1); let capu = U256::from(cap);
    let clip = |x: U256| -> u32 { if x >= capu { cap } else { x.as_limbs()[0] as u32 } };
    let (lt0, lt1, eq): (u32, u32, Option<u32>);
    if a.checked_mul(n).and_then(|x| x.checked_add(b)).is_some() {
        lt0 = 0;
        if c <= b { lt1 = 0; eq = if c == b { Some(0) } else { None }; }
        else { let (q, r) = divrem(c - b, a); lt1 = clip(q + U256::from(!r.is_zero() as u8)); eq = if r.is_zero() && q < capu { Some(q.as_limbs()[0] as u32) } else { None }; }
    } else {
        let na = a.wrapping_neg();
        match na.checked_mul(n) { Some(x) if x <= b => {} _ => return None }
        lt1 = cap;
        if b < c { lt0 = 0; eq = None; }
        else { let (q, r) = divrem(b - c, na); lt0 = clip(q.saturating_add(U256::from(1u8))); /* q = MAX gives cap, not 0 */ eq = if r.is_zero() && q < capu { Some(q.as_limbs()[0] as u32) } else { None }; }
    }
    let ltm = mask_range(lt0, lt1);
    let mut eqm = [0u64; 8]; if let Some(q) = eq { eqm[(q / 64) as usize] = 1u64 << (q % 64); }
    let mut m = [0u64; 8];
    for w in 0..8 {
        m[w] = match op { 0 => ltm[w], 1 => full[w] & !(ltm[w] | eqm[w]), _ => eqm[w] };
        if !want { m[w] = full[w] & !m[w]; }
    }
    Some(m)
}

/// improvement: same result as solve_affine where that is Some; additionally solves an affine value that wraps
/// around exactly once on [0, cap) (|a| * (cap - 1) < 2^256) as two monotone pieces [0, k0] and [k0 + 1, cap)
pub fn solve_affine2(a: U256, b: U256, c: U256, op: u8, signed: bool, want: bool, cap: u32) -> Option<[u64; 8]> {
    let (b, c) = if signed { let t = U256::from(1u8) << 255; (b ^ t, c ^ t) } else { (b, c) };
    if let Some(m) = solve_unsigned2(a, b, c, op, want, cap) { return Some(m); }
    let n = U256::from(cap - 1);
    let k0 = if a.checked_mul(n).is_some() { (U256::MAX - b) / a }            // increasing: last value without overflow
             else { let na = a.wrapping_neg(); if na.checked_mul(n).is_none() { return None; } b / na };   // decreasing: last value >= 0
    let k0 = k0.as_limbs()[0] as u32; // < cap - 1 because the single piece wrapped
    let m1 = solve_unsigned2(a, b, c, op, want, k0 + 1)?;
    let b2 = b.wrapping_add(a.wrapping_mul(U256::from(k0 + 1)));
    let m2 = solve_unsigned2(a, b2, c, op, want, cap - k0 - 1)?;
    let m2 = shl512(m2, k0 + 1); let mut m = [0u64; 8];
    for w in 0..8 { m[w] = m1[w] | m2[w]; }
    Some(m)
}

/// satisfying set over [0, cap) of (cmp(a*i + b, c) == want), cmp: op 0 f < c, 1 f > c, 2 f == c (256-bit modular f);
/// None when f may wrap around on [0, cap) (the caller falls back to the value-by-value check)
pub fn solve_affine(a: U256, b: U256, c: U256, op: u8, signed: bool, want: bool, cap: u32) -> Option<[u64; 8]> {
    // signed comparison of x, y == unsigned comparison of x + 2^255, y + 2^255; f + 2^255 = a i + (b + 2^255)
    let (b, c) = if signed { let t = U256::from(1u8) << 255; (b ^ t, c ^ t) } else { (b, c) };
    let full = mask_range(0, cap);
    if a.is_zero() {
        let base = match op { 0 => b < c, 1 => b > c, _ => b == c };
        return Some(if base == want { full } else { [0; 8] });
    }
    let n = U256::from(cap - 1); let capu = U256::from(cap);
    let clip = |x: U256| -> u32 { if x >= capu { cap } else { x.as_limbs()[0] as u32 } };
    // [lt0, lt1): values with f < c; eq: the value with f == c, if any
    let (lt0, lt1, eq): (u32, u32, Option<u32>);
    if a.checked_mul(n).and_then(|x| x.checked_add(b)).is_some() {
        // increasing without wrap: f(v) = b + a v, v in [0, cap)
        lt0 = 0;
        lt1 = if c <= b { 0 } else { let d = c - b; clip(d / a + U256::from(!(d % a).is_zero() as u8)) };
        eq = if c >= b && ((c - b) % a).is_zero() { let q = (c - b) / a; if q < capu { Some(q.as_limbs()[0] as u32) } else { None } } else { None };
    } else {
        let na = a.wrapping_neg();
        match na.checked_mul(n) { Some(x) if x <= b => {} _ => return None }
        // decreasing without wrap: f(v) = b - na v
        lt1 = cap;
        lt0 = if b < c { 0 } else { clip(((b - c) / na).saturating_add(U256::from(1u8))) }; // q = MAX gives cap, not 0
        eq = if b >= c && ((b - c) % na).is_zero() { let q = (b - c) / na; if q < capu { Some(q.as_limbs()[0] as u32) } else { None } } else { None };
    }
    let ltm = mask_range(lt0, lt1);
    let mut eqm = [0u64; 8]; if let Some(q) = eq { eqm[(q / 64) as usize] = 1u64 << (q % 64); }
    let mut m = [0u64; 8];
    for w in 0..8 {
        m[w] = match op { 0 => ltm[w], 1 => full[w] & !(ltm[w] | eqm[w]), _ => eqm[w] };
        if !want { m[w] = full[w] & !m[w]; }
    }
    Some(m)
}

#[derive(Clone, Copy)]
struct Bind<'b> { pairs: &'b [(u32, u32)], default_zero: bool }
const NOBIND: Bind<'static> = Bind { pairs: &[], default_zero: false };

#[inline] fn is_neg(x: &U256) -> bool { x.bit(255) }
#[inline] fn abs(x: U256) -> U256 { if is_neg(&x) { x.wrapping_neg() } else { x } }
#[inline] fn b2u(b: bool) -> U256 { if b { U256::from(1u8) } else { U256::ZERO } }
#[inline] fn small(x: &U256, lim: u64) -> Option<u64> { if *x < U256::from(lim) { Some(x.as_limbs()[0]) } else { None } }

fn op(o: u32, a: &[U256]) -> U256 {
    match o {
        ADD => a[0].wrapping_add(a[1]), MUL => a[0].wrapping_mul(a[1]), SUB => a[0].wrapping_sub(a[1]),
        DIV => if a[1].is_zero() { U256::ZERO } else { a[0] / a[1] },
        MOD => if a[1].is_zero() { U256::ZERO } else { a[0] % a[1] },
        SDIV => {
            if a[1].is_zero() { return U256::ZERO; }
            let q = abs(a[0]) / abs(a[1]);
            if is_neg(&a[0]) != is_neg(&a[1]) { q.wrapping_neg() } else { q }
        }
        SMOD => {
            if a[1].is_zero() { return U256::ZERO; }
            let r = abs(a[0]) % abs(a[1]);
            if is_neg(&a[0]) { r.wrapping_neg() } else { r }
        }
        ADDMOD => a[0].add_mod(a[1], a[2]), MULMOD => a[0].mul_mod(a[1], a[2]),
        EXP => a[0].wrapping_pow(a[1]),
        SIGNEXTEND => match small(&a[0], 31) {
            None => a[1],
            Some(b) => {
                let bit = (b * 8 + 7) as usize;
                let mask = (U256::from(1u8) << (bit + 1)).wrapping_sub(U256::from(1u8));
                if a[1].bit(bit) { a[1] | !mask } else { a[1] & mask }
            }
        },
        LT => b2u(a[0] < a[1]), GT => b2u(a[0] > a[1]),
        SLT => { let (na, nb) = (is_neg(&a[0]), is_neg(&a[1])); b2u(if na != nb { na } else { a[0] < a[1] }) }
        SGT => { let (na, nb) = (is_neg(&a[0]), is_neg(&a[1])); b2u(if na != nb { nb } else { a[0] > a[1] }) }
        EQ => b2u(a[0] == a[1]), ISZERO => b2u(a[0].is_zero()),
        AND => a[0] & a[1], OR => a[0] | a[1], XOR => a[0] ^ a[1], NOT => !a[0],
        BYTE => match small(&a[0], 32) { Some(i) => U256::from(a[1].byte(31 - i as usize)), None => U256::ZERO },
        SHL => match small(&a[0], 256) { Some(s) => a[1] << (s as usize), None => U256::ZERO },
        SHR => match small(&a[0], 256) { Some(s) => a[1] >> (s as usize), None => U256::ZERO },
        SAR => {
            let neg = is_neg(&a[1]);
            match small(&a[0], 256) {
                Some(s) => if neg { !((!a[1]) >> (s as usize)) } else { a[1] >> (s as usize) },
                None => if neg { U256::MAX } else { U256::ZERO },
            }
        }
        _ => unreachable!("op {o}"),
    }
}

const TWO32: u64 = 1 << 32;
const TWO20: u64 = 1 << 20;

impl Scratch {
    fn bump(&mut self, p: &Plan) {
        self.stamp = self.stamp.wrapping_add(1);
        if self.stamp == 0 {
            self.memo_stamp.iter_mut().for_each(|x| *x = 0); self.sat_stamp.iter_mut().for_each(|x| *x = 0);
            self.done.iter_mut().for_each(|x| *x = 0); self.cdone.iter_mut().for_each(|x| *x = 0); self.stamp = 1;
        }
        if self.memo_stamp.len() < p.nodes.len() {
            self.memo_stamp.resize(p.nodes.len(), 0); self.memo_val.resize(p.nodes.len(), U256::ZERO); self.memo_ok.resize(p.nodes.len(), 0);
        }
        // with `sat_classes`, class slots [0, n_lists) and per-list slots [n_lists, 2 n_lists)
        let nl = if self.sat_classes { 2 * p.n_lists() } else { p.n_lists() };
        if self.sat_stamp.len() < nl { self.sat_stamp.resize(nl, 0); self.sat_res.resize_with(nl, Vec::new); }
        if self.done.len() < p.sgroups.len() { self.done.resize(p.sgroups.len(), 0); }
        if self.cdone.len() < p.cgroups.len() { self.cdone.resize(p.cgroups.len(), 0); }
    }
    fn prepare(&mut self, p: &Plan) {
        self.bump(p);
        self.out.clear(); self.asg.clear(); self.c = Counters::default(); self.sc = SolveCounters::default();
        self.chk_log.clear();
        #[cfg(feature = "prof")] { self.prof = Prof::default(); }
    }

    /// (a, b) with node j == a * idx + b (mod 2^256) for the single loop index in scope; j must satisfy Plan::is_affine
    fn affine(&mut self, p: &Plan, f: &Frame, j: u32) -> Result<(U256, U256), Fail> {
        let nd = p.nodes[j as usize];
        if !nd.dep() { return Ok((U256::ZERO, self.eval(p, f, j, NOBIND)?)); }
        match nd.tag() {
            T_IDX => Ok((U256::from(1u8), U256::ZERO)),
            T_LIN => {
                let (mut a, mut b) = (U256::ZERO, p.consts[nd.a as usize]);
                for k in 0..nd.n as usize {
                    let o = nd.b as usize + 2 * k; let co = p.consts[p.side[o] as usize];
                    let (ax, bx) = self.affine(p, f, p.side[o + 1])?;
                    a = a.wrapping_add(co.wrapping_mul(ax)); b = b.wrapping_add(co.wrapping_mul(bx));
                }
                Ok((a, b))
            }
            T_OP => {
                let (x, y) = (p.side[nd.b as usize], p.side[nd.b as usize + 1]);
                match nd.sub() {
                    ADD => { let (ax, bx) = self.affine(p, f, x)?; let (ay, by) = self.affine(p, f, y)?; Ok((ax.wrapping_add(ay), bx.wrapping_add(by))) }
                    SUB => { let (ax, bx) = self.affine(p, f, x)?; let (ay, by) = self.affine(p, f, y)?; Ok((ax.wrapping_sub(ay), bx.wrapping_sub(by))) }
                    _ /* MUL */ => {
                        let (k, z) = if !p.nodes[x as usize].dep() { (x, y) } else { (y, x) };
                        let kv = self.eval(p, f, k, NOBIND)?; let (az, bz) = self.affine(p, f, z)?;
                        Ok((kv.wrapping_mul(az), kv.wrapping_mul(bz)))
                    }
                }
            }
            _ => unreachable!("affine tag"),
        }
    }

    /// all items (list_data format) hold or are unevaluable under binding bd
    #[inline]
    fn items_ok(&mut self, p: &Plan, f: &Frame, items: &[u32], bd: Bind) -> bool {
        for &it in items {
            self.c.cons_evals += 1; self.sc.rest_evals += 1;
            #[cfg(feature = "prof")] let t0 = if self.prof_cond { tsc() } else { 0 };
            let r = self.eval(p, f, it & 0x7FFF_FFFF, bd);
            #[cfg(feature = "prof")] { let cl = p.cls[(it & 0x7FFF_FFFF) as usize] as usize; if self.prof_cond { self.prof.cond_cyc[cl.min(N_CLS)] += tsc() - t0; } self.prof.cond_n[cl.min(N_CLS)] += 1; }
            match r { Ok(v) => { if (!v.is_zero()) != (it >> 31 == 1) { return false; } } Err(_) => continue }
        }
        true
    }

    /// interval solving of a single-index condition list; result (ascending) in `res` (stored by `satset` in the
    /// list's cache slot)
    fn satset_interval(&mut self, p: &Plan, f: &Frame, list: u32, id: u32, cap: u32, res: &mut Vec<u16>) {
        let li = list as usize; let [s0, s1, _] = p.sl_off[li]; let (r0, r1) = p.rest_range(li);
        let mut bits = mask_range(0, cap);
        let mut fb = std::mem::take(&mut self.fb); fb.clear();
        #[cfg(feature = "prof")] let t0 = tsc();
        for k in s0 as usize..s1 as usize {
            // diagnostic: conditions solved after the set is already empty
            if self.check && bits.iter().all(|&w| w == 0) { self.sc.after_empty += 1; }
            let sh = p.sl_shape[k];
            let c = if sh.c == NONE32 { Ok(U256::ZERO) } else { self.eval(p, f, sh.c, NOBIND) };
            let r = c.and_then(|c| self.affine(p, f, sh.f).map(|(a, b)| (a, b, c)));
            match r {
                Err(_) => { self.sc.unk_all += 1; } // unevaluable for every index value: skipped by _cons_ok
                Ok((a, b, c)) => match if self.improved { solve_affine2(a, b, c, sh.op, sh.signed, sh.want, cap) } else { solve_affine(a, b, c, sh.op, sh.signed, sh.want, cap) } {
                    Some(m) => { self.sc.solved += 1; for w in 0..8 { bits[w] &= m[w]; } }
                    None => { self.sc.wrap_fallback += 1; fb.push(k as u32 | 0x8000_0000); }
                },
            }
        }
        #[cfg(feature = "prof")] { self.prof.solve += tsc() - t0; self.prof.solve_n += (s1 - s0) as u64; }
        let _ = id;
        res.clear();
        let rest = &p.sl_rest[r0..r1];
        for w in 0..8 {
            let mut x = bits[w];
            while x != 0 {
                let v = (w as u32) * 64 + x.trailing_zeros(); x &= x - 1;
                let pr = [(id, v)]; let bd = Bind { pairs: &pr, default_zero: false };
                if !rest.is_empty() && !self.items_ok(p, f, rest, bd) { continue; }
                if !fb.is_empty() && !self.fallback_ok(p, f, &fb, bd) { continue; }
                res.push(v as u16);
            }
        }
        self.fb = fb;
    }

    /// value-by-value check of solvable-form conditions whose affine value may wrap (fb holds 0x8000_0000 | shape index)
    fn fallback_ok(&mut self, p: &Plan, f: &Frame, fb: &[u32], bd: Bind) -> bool {
        for &k in fb {
            let sh = p.sl_shape[(k & 0x7FFF_FFFF) as usize];
            self.c.cons_evals += 1; self.sc.rest_evals += 1;
            #[cfg(feature = "prof")] let t0 = if self.prof_cond { tsc() } else { 0 };
            // evaluate the original comparison through the generic evaluator (same result as the original node)
            let fv = self.eval(p, f, sh.f, bd);
            let r = fv.and_then(|fv| { let c = if sh.c == NONE32 { U256::ZERO } else { self.eval(p, f, sh.c, NOBIND)? }; Ok((fv, c)) });
            #[cfg(feature = "prof")] { if self.prof_cond { self.prof.cond_cyc[N_CLS] += tsc() - t0; } self.prof.cond_n[N_CLS] += 1; }
            match r {
                Err(_) => continue,
                Ok((fv, c)) => {
                    let (x, y) = if sh.signed { let t = U256::from(1u8) << 255; (fv ^ t, c ^ t) } else { (fv, c) };
                    let v = match sh.op { 0 => x < y, 1 => x > y, _ => x == y };
                    if v != sh.want { return false; }
                }
            }
        }
        true
    }

    fn eval(&mut self, p: &Plan, f: &Frame, j: u32, bd: Bind) -> R {
        let nd = p.nodes[j as usize];
        let memo = !nd.dep();
        if memo && self.memo_stamp[j as usize] == self.stamp {
            return match self.memo_ok[j as usize] { 0 => Ok(self.memo_val[j as usize]), 1 => Err(Fail::Unk), _ => Err(Fail::Wide) };
        }
        let r = self.eval_raw(p, f, nd, bd);
        if memo {
            self.memo_stamp[j as usize] = self.stamp;
            match r { Ok(v) => { self.memo_val[j as usize] = v; self.memo_ok[j as usize] = 0 }
                      Err(Fail::Unk) => self.memo_ok[j as usize] = 1, Err(Fail::Wide) => self.memo_ok[j as usize] = 2 }
        }
        r
    }

    fn region_cd(&mut self, p: &Plan, f: &Frame, nd: Node, bd: Bind, out: &mut Vec<u8>) -> Result<(), Fail> {
        let n = self.eval(p, f, nd.b, bd)?;
        let n = small(&n, TWO20 + 1).ok_or(Fail::Unk)? as usize;
        let s = self.eval(p, f, nd.a, bd)?;
        let st = out.len(); out.resize(st + n, 0);
        if let Some(s) = small(&s, f.calldata.len() as u64) {
            let s = s as usize; let e = (s + n).min(f.calldata.len());
            out[st..st + (e - s)].copy_from_slice(&f.calldata[s..e]);
        }
        Ok(())
    }

    /// evm_static_v2.eval_segments: Python slice semantics (negative bounds count from the end), REGION slices
    /// with an upper bound are right-padded with zeros to hi - lo (bytes.ljust)
    fn segments(&mut self, p: &Plan, f: &Frame, nd: Node, bd: Bind) -> Result<Vec<u8>, Fail> {
        fn pyslice(l: usize, lo: i64, hi: Option<i64>) -> (usize, usize) {
            let l = l as i64;
            let c = |x: i64| if x < 0 { (x + l).max(0) } else { x.min(l) };
            let (a, b) = (c(lo), hi.map(c).unwrap_or(l));
            if b > a { (a as usize, b as usize) } else { (a as usize, a as usize) }
        }
        let mut out = Vec::with_capacity(64);
        for k in 0..nd.n as usize {
            let b = nd.b as usize + 3 * k;
            let (c, lo, hr) = (p.side[b], p.side[b + 1] as i32 as i64, p.side[b + 2]);
            let hi = if hr == HI_NONE { None } else { Some(hr as i32 as i64) };
            let cn = p.nodes[c as usize];
            if cn.tag() == T_REGCD {
                let mut rb = Vec::new();
                self.region_cd(p, f, cn, bd, &mut rb)?;
                let (s0, s1) = pyslice(rb.len(), lo, hi);
                let st = out.len(); out.extend_from_slice(&rb[s0..s1]);
                if let Some(h) = hi { let w = h - lo; if w > (s1 - s0) as i64 { out.resize(st + w as usize, 0); } }
            } else {
                let w: [u8; 32] = self.eval(p, f, c, bd)?.to_be_bytes::<32>();
                let (s0, s1) = pyslice(32, lo, hi);
                out.extend_from_slice(&w[s0..s1]);
            }
        }
        Ok(out)
    }

    fn eval_raw(&mut self, p: &Plan, f: &Frame, nd: Node, bd: Bind) -> R {
        match nd.tag() {
            T_CONST => Ok(p.consts[nd.a as usize]),
            T_CD => {
                let off = self.eval(p, f, nd.a, bd)?;
                if off > U256::from(TWO32) { return Ok(U256::ZERO); }
                let o = off.as_limbs()[0] as usize;
                let mut w = [0u8; 32];
                if o < f.calldata.len() { let e = (o + 32).min(f.calldata.len()); w[..e - o].copy_from_slice(&f.calldata[o..e]); }
                Ok(U256::from_be_bytes(w))
            }
            T_ENV => Ok(f.env[nd.sub() as usize]),
            T_SLOAD => {
                let k = self.eval(p, f, nd.a, bd)?;
                match f.sload { Some(g) => g(k).ok_or(Fail::Unk), None => Err(Fail::Unk) }
            }
            T_IDX => {
                for &(i, v) in bd.pairs { if i == nd.a { return Ok(U256::from(v)); } }
                if bd.default_zero { Ok(U256::ZERO) } else { Err(Fail::Unk) }
            }
            T_LIN => {
                let mut v = p.consts[nd.a as usize];
                for k in 0..nd.n as usize {
                    let b = nd.b as usize + 2 * k;
                    let x = self.eval(p, f, p.side[b + 1], bd)?;
                    v = v.wrapping_add(p.consts[p.side[b] as usize].wrapping_mul(x));
                }
                Ok(v)
            }
            T_OP => {
                let mut a = [U256::ZERO; 3];
                for k in 0..nd.n as usize { a[k] = self.eval(p, f, p.side[nd.b as usize + k], bd)?; }
                Ok(op(nd.sub(), &a[..nd.n as usize]))
            }
            T_KEC => {
                let n = nd.n as usize;
                let mut st = [0u8; 256]; let mut hv: Vec<u8>;
                let buf: &mut [u8] = if n * 32 <= 256 { &mut st[..n * 32] } else { hv = vec![0u8; n * 32]; &mut hv[..] };
                for k in 0..n {
                    let x = self.eval(p, f, p.side[nd.b as usize + k], bd)?;
                    buf[32 * k..32 * k + 32].copy_from_slice(&x.to_be_bytes::<32>());
                }
                self.c.keccak += 1;
                Ok(U256::from_be_bytes(keccak256(&*buf).0))
            }
            T_KECB => { let s = self.segments(p, f, nd, bd)?; self.c.keccak += 1; Ok(U256::from_be_bytes(keccak256(&s).0)) }
            T_BYTES => {
                let s = self.segments(p, f, nd, bd)?;
                if s.len() > 32 { self.c.wide += 1; return Err(Fail::Wide); }
                Ok(U256::from_be_slice(&s))
            }
            T_REGCD => Err(Fail::Unk), // a REGION outside a segment list never occurs in the plans (export asserts)
            T_UNK => Err(Fail::Unk),
            t => unreachable!("tag {t}"),
        }
    }

    /// predict.Predictor._cons_ok: an unevaluable constraint is skipped (over-approximation)
    fn cons_ok(&mut self, p: &Plan, f: &Frame, list: u32, bd: Bind) -> bool {
        let (s, e) = (p.list_off[list as usize] as usize, p.list_off[list as usize + 1] as usize);
        for k in s..e {
            let it = p.list_data[k];
            self.c.cons_evals += 1;
            match self.eval(p, f, it & 0x7FFF_FFFF, bd) {
                Ok(v) => { if (!v.is_zero()) != (it >> 31 == 1) { return false; } }
                Err(_) => continue,
            }
        }
        true
    }

    /// index assignments of one family alternative `al` (falts / fcalts layout; `side2` its extra-selector and
    /// fixed-index array; key indices `kid[..nkey]`), as predict.Predictor._family_assignments: fixed (non-key) indices take
    /// the minimum of their satisfying set (an empty set rejects the alternative); key indices enumerate their satisfying
    /// sets when bounded (one key: all values; two keys: first 96 x 96), any set reaching cap - 1 (unbounded) gives its
    /// smallest value only; the multi-index list is checked last with the fixed and key indices bound (unconstrained
    /// non-key indices read 0, as `fixed` holds 0 for them in Python). Pushes (group, v0, v1) onto `out`. Shared by the
    /// family storage groups (`instantiate`) and the family call groups (`instantiate_calls`); the selector check is the
    /// caller's.
    fn family_assignments(&mut self, p: &Plan, f: &Frame, al: &[u32; 9], side2: &[u32], nkey: usize, kid: [u32; 2], cap: u32,
                          fixed: &mut Vec<(u32, u32)>, out: &mut Vec<(u32, u16, u16)>) {
        let g = al[0];
        let off = al[3] as usize; let nx = al[4] as usize; let nfix = al[5] as usize;
        fixed.clear();
        for k in 0..nfix {
            let (id, li) = (side2[off + nx + 2 * k], side2[off + nx + 2 * k + 1]);
            self.satset(p, f, li, id, cap);
            match self.sat_res[self.sat_slot(p, li, id)].first() { Some(&v) => fixed.push((id, v as u32)), None => return }
        }
        let set = |s: &Self, k: usize| -> Vec<u16> {
            let li = al[6 + k];
            if li == NONE32 { s.full[..cap as usize].to_vec() } else { s.sat_res[s.sat_slot(p, li, kid[k])].clone() }
        };
        for k in 0..nkey { let li = al[6 + k]; if li != NONE32 { self.satset(p, f, li, kid[k], cap); } }
        let sets: Vec<Vec<u16>> = (0..nkey).map(|k| set(self, k)).collect();
        if sets.iter().any(|s| s.is_empty()) { return; }
        let unb = sets.iter().any(|s| s.contains(&((cap - 1) as u16)));
        let mut cand: Vec<(u16, u16)> = Vec::new();
        if nkey == 0 { cand.push((0, 0)); }
        else if unb { cand.push((sets[0][0], if nkey > 1 { sets[1][0] } else { 0 })); }
        else if nkey == 1 { cand.extend(sets[0].iter().map(|&v| (v, 0))); }
        else { for &va in sets[0].iter().take(96) { for &vb in sets[1].iter().take(96) { cand.push((va, vb)); } } }
        let ml = al[8];
        for (v0, v1) in cand {
            if ml != NONE32 {
                let mut pr = fixed.clone();
                if nkey > 0 { pr.push((kid[0], v0 as u32)); }
                if nkey > 1 { pr.push((kid[1], v1 as u32)); }
                #[cfg(feature = "prof")] let tm = tsc();
                let ok = self.cons_ok(p, f, ml, Bind { pairs: &pr, default_zero: true });
                #[cfg(feature = "prof")] { self.prof.multi += tsc() - tm; self.prof.multi_n += 1; }
                if !ok { continue; }
            }
            out.push((g, v0, v1));
        }
    }

    /// cache slot of list `list` solved for loop index `id`: the list itself without `sat_classes`; with
    /// it, the class representative when `id` is the list's own index and the list joined a class, a per-list slot
    /// (n_lists + list) otherwise
    #[inline] fn sat_slot(&self, p: &Plan, list: u32, id: u32) -> usize {
        if !self.sat_classes { return list as usize; }
        match p.sat_cls.get(list as usize) {
            Some(&c) if c != NONE32 && p.sl_id[list as usize] == id => c as usize,
            _ => p.n_lists() + list as usize,
        }
    }

    /// satisfying values in range(cap) of the per-index constraint list `list` for loop index `id` (cached per frame, in `sat_slot`)
    fn satset(&mut self, p: &Plan, f: &Frame, list: u32, id: u32, cap: u32) {
        let slot = self.sat_slot(p, list, id);
        if self.sat_stamp[slot] == self.stamp { return; }
        self.c.satsets += 1;
        #[cfg(feature = "prof")] let t0 = tsc();
        if self.interval {
            let mut res = std::mem::take(&mut self.sat_res[slot]);
            self.satset_interval(p, f, list, id, cap, &mut res);
            if self.check {
                let mut bf = Vec::new();
                for v in 0..cap { let pr = [(id, v)]; if self.cons_ok(p, f, list, Bind { pairs: &pr, default_zero: false }) { bf.push(v as u16); } }
                let eq = bf == res;
                self.chk_log.push((list, cap, eq));
                if !eq && self.chk_first_bad.is_none() { self.chk_first_bad = Some((list, cap, res.clone(), bf)); }
            }
            self.sat_res[slot] = res;
        } else {
            let mut res = std::mem::take(&mut self.sat_res[slot]); res.clear();
            for v in 0..cap {
                let pr = [(id, v)];
                #[cfg(not(feature = "prof"))]
                let ok = self.cons_ok(p, f, list, Bind { pairs: &pr, default_zero: false });
                #[cfg(feature = "prof")]
                let ok = self.items_ok(p, f, p.list(list), Bind { pairs: &pr, default_zero: false });
                if ok { res.push(v as u16); }
            }
            self.sat_res[slot] = res;
        }
        self.sat_stamp[slot] = self.stamp;
        #[cfg(feature = "prof")] {
            let d = tsc() - t0; self.prof.sat += d; self.prof.sat_n += 1;
            let (r0, r1) = p.rest_range(list as usize);
            if r0 == r1 { self.prof.sat_full += d; self.prof.sat_full_n += 1; }
        }
    }

    /// evaluate the plan's call records for one frame. Call after `instantiate` on the same frame
    /// (the memo of index-free nodes is reused) or standalone; the result is left in `self.calls` (and `self.call_idx`).
    /// Mirrors predict.Predictor._frame's call loop for index-free groups: a group is taken when any alternative's
    /// constraints hold (unevaluable conditions count as holding), the target is masked to 160 bits, targets below 256
    /// (precompiles, zero) are dropped; the payload follows Predictor._callargs with every unknown word making the
    /// whole payload unknown (the Python keeps unknown ranges; see README).
    /// then the family call groups of a version-3 plan (`family_calls`).
    pub fn instantiate_calls(&mut self, p: &Plan, f: &Frame, reuse_memo: bool) {
        self.calls.clear(); self.call_idx.clear(); self.call_holes.clear(); self.c_nopayload = 0; self.c_family = 0; self.c_family_capped = 0;
        if p.kind != 0 || (p.cgroups.is_empty() && p.fcgroups.is_empty()) { return; }
        if !reuse_memo { self.bump(p); }
        let cd = f.calldata;
        let mut s4 = [0u8; 4]; let k = cd.len().min(4); s4[..k].copy_from_slice(&cd[..k]);
        let sel = u32::from_be_bytes(s4);
        let pyoff = p.version >= 3 && !self.legacy_payload;
        let (a, b) = Plan::sel_range(&p.c_sel, sel);
        for r in [0..p.c_generic, a..b] {
            for i in r {
                let al = p.calts[i];
                let g = al[0] as usize;
                if self.cdone[g] == self.stamp { continue; }
                if !self.cons_ok(p, f, al[3], NOBIND) { continue; }
                self.cdone[g] = self.stamp;
                let cg = p.cgroups[g];
                let Ok(t) = self.eval(p, f, cg[1], NOBIND) else { continue };
                let t = t & ((U256::from(1u8) << 160) - U256::from(1u8));
                if t < U256::from(256u32) { continue; }
                let (payload, holes) = match if cg[2] == NONE32 { None } else { self.payload(p, f, cg[2], cg[3], cg[4], &[], pyoff) } {
                    Some((b, h)) => (Some(b), h), None => (None, 0) };
                if payload.is_none() { self.c_nopayload += 1; }
                self.calls.push(CallOut { kind: cg[0] as u8, target: t, payload });
                self.call_idx.push(None); self.call_holes.push(holes);
            }
        }
        if !p.fcgroups.is_empty() { self.family_calls(p, f, sel, cd.len()); }
    }

    /// family call groups (predict.Predictor._frame's call loop for groups with loop indices): per alternative
    /// whose extra selectors match, the assignments of `family_assignments` (as for family storage groups, same cap);
    /// assignments deduplicated per group over all alternatives, the first MAX_FAMILY_CALLS per group in (v0, v1) order
    /// and at most MAX_FAMILY_CALLS_FRAME per frame are evaluated with the key indices bound: target (160 bits, >= 256)
    /// and payload (`payload` with predict.py's rule for expression offsets). A group without payload whose target does
    /// not depend on a loop index gives one call (all its assignments give the same call). The storage counters
    /// (`c`, `sc`) are left as `instantiate` set them.
    fn family_calls(&mut self, p: &Plan, f: &Frame, sel: u32, cdlen: usize) {
        let (c0, sc0) = (self.c, self.sc);
        #[cfg(feature = "prof")] let pf0 = self.prof;
        let cap = (cdlen / 32 + 34).min(512) as u32;
        if self.full.len() < cap as usize { self.full = (0..512u16).collect(); }
        let mut fasg = std::mem::take(&mut self.fasg); fasg.clear();
        let mut fixed: Vec<(u32, u32)> = Vec::new();
        let (a, b) = Plan::sel_range(&p.fc_sel, sel);
        for r in [0..p.fc_generic, a..b] {
            'alt: for i in r {
                let al = p.fcalts[i];
                let off = al[3] as usize; let nx = al[4] as usize;
                for k in 0..nx { if p.cside2[off + k] != sel { continue 'alt; } } // 'sel'-class rejection
                let cg = p.fcgroups[al[0] as usize];
                self.family_assignments(p, f, &al, &p.cside2, cg[5] as usize, [cg[6], cg[7]], cap, &mut fixed, &mut fasg);
            }
        }
        fasg.sort_unstable(); fasg.dedup();
        let mask = (U256::from(1u8) << 160) - U256::from(1u8);
        let (mut i, mut done) = (0usize, 0usize);
        while i < fasg.len() {
            let g = fasg[i].0;
            let mut j = i; while j < fasg.len() && fasg[j].0 == g { j += 1; }
            let cg = p.fcgroups[g as usize];
            let single = cg[2] == NONE32 && !p.dep(cg[1]);
            let lim = if single { 1 } else { MAX_FAMILY_CALLS };
            let end = j.min(i + lim).min(i + (MAX_FAMILY_CALLS_FRAME - done));
            self.c_family_capped += if single { (end == i) as u32 } else { (j - end) as u32 };
            let n = cg[5] as usize;
            for &(_, v0, v1) in &fasg[i..end] {
                done += 1;
                let pr = [(cg[6], v0 as u32), (cg[7], v1 as u32)];
                let bd = Bind { pairs: &pr[..n], default_zero: false };
                let Ok(t) = self.eval(p, f, cg[1], bd) else { continue };
                let t = t & mask;
                if t < U256::from(256u32) { continue; }
                let (payload, holes) = match if cg[2] == NONE32 { None } else { self.payload(p, f, cg[2], cg[3], cg[4], &pr[..n], true) } {
                    Some((b, h)) => (Some(b), h), None => (None, 0) };
                if payload.is_none() { self.c_nopayload += 1; }
                self.calls.push(CallOut { kind: cg[0] as u8, target: t, payload });
                self.call_idx.push(Some((g, v0, v1))); self.call_holes.push(holes);
                self.c_family += 1;
            }
            i = j;
        }
        self.fasg = fasg;
        self.c = c0; self.sc = sc0;
        #[cfg(feature = "prof")] { self.prof = pf0; }
    }

    /// Payload of a call group: buffer of `size_node` bytes, argument words `cside[off .. off + 3 nw]` placed in order
    /// with the key indices `keys` bound; returns (buffer, bytes no word covers), `None` when the payload is unknown.
    /// Without `pyoff` (version-1/2 rule): every offset is evaluated (failure: unknown), a word whose value does not
    /// evaluate makes the payload unknown, a T_UNK value too. With `pyoff` (predict.Predictor._callargs): a word whose value
    /// does not evaluate marks its bytes unknown and a later word overwriting them clears the mark (a REGION: from its
    /// offset to the end); the payload is unknown when unknown bytes remain; offsets that are expressions follow
    /// `place_offexpr`. Uncovered bytes read zero in both.
    fn payload(&mut self, p: &Plan, f: &Frame, size_node: u32, off: u32, nw: u32, keys: &[(u32, u32)], pyoff: bool) -> Option<(Vec<u8>, u32)> {
        let bd = Bind { pairs: keys, default_zero: false };
        let size = self.eval(p, f, size_node, bd).ok()?;
        let size = small(&size, (1u64 << 16) + 1)? as usize;
        let mut buf = vec![0u8; size];
        let mut fl = vec![0u8; size]; // bit 0: covered by a word, bit 1: unknown (pyoff)
        let off = off as usize;
        for k in 0..nw as usize {
            let (rn, vn, nb) = (p.cside[off + 3 * k], p.cside[off + 3 * k + 1], p.cside[off + 3 * k + 2]);
            if !pyoff && p.nodes[vn as usize].tag() == T_UNK { return None; }
            if pyoff && p.nodes[rn as usize].tag() != T_CONST { self.place_offexpr(p, f, &mut buf, &mut fl, rn, vn, nb, keys)?; continue; }
            let r = self.eval(p, f, rn, bd).ok()?;
            // Python: r >= 2^62 -> r - 2^256 (negative offset); r < -32 or r >= size -> word lies outside the buffer
            let rel: i64 = if r >= (U256::from(1u8) << 62) {
                let neg = r.wrapping_neg();
                match small(&neg, 1 << 40) { Some(v) => -(v as i64), None => continue } // far negative offset: nothing lands in the buffer
            } else {
                match small(&r, 1 << 40) { Some(v) => v as i64, None => continue }       // far positive offset: likewise
            };
            self.place(p, f, &mut buf, &mut fl, pyoff, rel, vn, nb, bd)?;
        }
        if pyoff && fl.iter().any(|&x| x & 2 != 0) { return None; }
        let holes = fl.iter().filter(|&&x| x & 1 == 0).count() as u32;
        Some((buf, holes))
    }

    /// predict._callargs `place`: one word (or a REGION CD value) at relative offset `rel`. A value that does not
    /// evaluate: `None` without `pyoff`, otherwise its bytes are marked unknown (REGION: up to the end of the buffer)
    fn place(&mut self, p: &Plan, f: &Frame, buf: &mut [u8], fl: &mut [u8], pyoff: bool, rel: i64, vn: u32, nb: u32, bd: Bind) -> Option<()> {
        let size = buf.len() as i64;
        let vnd = p.nodes[vn as usize];
        if vnd.tag() == T_REGCD || (vnd.tag() == T_UNK && vnd.sub() == 1) {
            let mut data = Vec::new();
            let r = if vnd.tag() == T_UNK { Err(Fail::Unk) } else { self.region_cd(p, f, vnd, bd, &mut data) };
            match r {
                Ok(()) => {
                    let lo = rel.max(0); let hi = (rel + data.len() as i64).min(size);
                    if lo < hi {
                        buf[lo as usize..hi as usize].copy_from_slice(&data[(lo - rel) as usize..(hi - rel) as usize]);
                        fl[lo as usize..hi as usize].fill(1);
                    }
                }
                Err(_) => {
                    if !pyoff { return None; }
                    let lo = rel.max(0);
                    if lo < size { fl[lo as usize..].fill(3); }
                }
            }
        } else {
            let n: i64 = if nb == NONE32 { 32 } else { nb as i64 };
            let lo = rel.max(0); let hi = (rel + n).min(size);
            if lo >= hi { return Some(()); }
            match self.eval(p, f, vn, bd) {
                Ok(v) => {
                    let w: [u8; 32] = v.to_be_bytes::<32>();
                    buf[lo as usize..hi as usize].copy_from_slice(&w[(lo - rel) as usize..(hi - rel) as usize]);
                    fl[lo as usize..hi as usize].fill(1);
                }
                Err(_) => {
                    if !pyoff { return None; }
                    fl[lo as usize..hi as usize].fill(3);
                }
            }
        }
        Some(())
    }

    /// predict.Predictor._callargs for a word whose offset is an expression: with the loop indices of offset and
    /// value not bound by `keys` ("free"): none -> the offset is evaluated once and the word placed when it is below 2^62;
    /// exactly one -> placed for i in range(min(MAX_FAMILY, size // 32 + 2)) with the free index = i while the offset
    /// (>= 2^62 read as negative) lies in [-32, size), stopping at the first offset outside; more than one -> payload
    /// unknown. An offset that does not evaluate makes the payload unknown: Python leaves those bytes uncovered, which the
    /// export environment's TIER_HOLE_UNKNOWN=1 marks unknown, and the payload here has no partially known form. Values
    /// are placed by `place` with the `pyoff` rule (an unknown value marks its bytes unknown).
    fn place_offexpr(&mut self, p: &Plan, f: &Frame, buf: &mut [u8], fl: &mut [u8], rn: u32, vn: u32, nb: u32, keys: &[(u32, u32)]) -> Option<()> {
        let mut ids = Vec::new(); p.idx_ids(rn, &mut ids); p.idx_ids(vn, &mut ids); ids.sort_unstable(); ids.dedup();
        let mut pr: Vec<(u32, u32)> = keys.iter().copied().filter(|(i, _)| ids.contains(i)).collect();
        let free: Vec<u32> = ids.iter().copied().filter(|i| !keys.iter().any(|(k, _)| k == i)).collect();
        let size = buf.len();
        match free.len() {
            0 => {
                let bd = Bind { pairs: &pr, default_zero: false };
                let r = self.eval(p, f, rn, bd).ok()?;
                if r < (U256::from(1u8) << 62) {
                    if let Some(rel) = small(&r, 1 << 40) { self.place(p, f, buf, fl, true, rel as i64, vn, nb, bd)?; }
                }
                Some(())
            }
            1 => {
                let n = MAX_FAMILY.min((size / 32 + 2) as u32);
                pr.push((free[0], 0)); let last = pr.len() - 1;
                for i in 0..n {
                    pr[last].1 = i;
                    let bd = Bind { pairs: &pr, default_zero: false };
                    let r = self.eval(p, f, rn, bd).ok()?;
                    let rel: i64 = if r >= (U256::from(1u8) << 62) {
                        match small(&r.wrapping_neg(), 1 << 40) { Some(v) => -(v as i64), None => break }
                    } else {
                        match small(&r, 1 << 40) { Some(v) => v as i64, None => break }
                    };
                    if rel >= size as i64 || rel < -32 { break; }
                    self.place(p, f, buf, fl, true, rel, vn, nb, bd)?;
                }
                Some(())
            }
            _ => None,
        }
    }

    /// Instantiate `p` for one frame; the predicted storage keys are left sorted and deduplicated in `self.out`.
    pub fn instantiate(&mut self, p: &Plan, f: &Frame) {
        #[cfg(feature = "prof")] let t_all = tsc();
        self.instantiate_inner(p, f);
        #[cfg(feature = "prof")] { self.prof.total = tsc() - t_all; }
    }
    fn instantiate_inner(&mut self, p: &Plan, f: &Frame) {
        self.prepare(p);
        if p.kind != 0 { return; }
        #[cfg(feature = "prof")] let t_sf = tsc();
        let cd = f.calldata;
        let mut s4 = [0u8; 4]; let k = cd.len().min(4); s4[..k].copy_from_slice(&cd[..k]);
        let sel = u32::from_be_bytes(s4);
        let cap = (cd.len() / 32 + 34).min(512) as u32;
        // ---- index-free site groups: predicted when any alternative's constraints hold
        let (a, b) = Plan::sel_range(&p.s_sel, sel);
        for r in [0..p.s_generic, a..b] {
            for i in r {
                let al = p.salts[i];
                let g = al[0] as usize;
                if self.done[g] == self.stamp { continue; }
                if !self.cons_ok(p, f, al[3], NOBIND) { continue; }
                self.done[g] = self.stamp; self.c.records += 1;
                match self.eval(p, f, p.sgroups[g], NOBIND) { Ok(k) => self.out.push(k), Err(_) => {} }
            }
        }
        #[cfg(feature = "prof")] { self.prof.sfree = tsc() - t_sf; }
        // ---- loop-index (family) site groups
        if self.full.len() < cap as usize { self.full = (0..512u16).collect(); }
        let (a, b) = Plan::sel_range(&p.f_sel, sel);
        let mut fixed: Vec<(u32, u32)> = Vec::new();
        let mut asg = std::mem::take(&mut self.asg);
        for r in [0..p.f_generic, a..b] {
            'alt: for i in r {
                let al = p.falts[i];
                let off = al[3] as usize; let nx = al[4] as usize;
                for k in 0..nx { if p.side2[off + k] != sel { continue 'alt; } } // 'sel'-class rejection
                self.c.family_alts += 1;
                let fg = p.fgroups[al[0] as usize];
                self.family_assignments(p, f, &al, &p.side2, fg[1] as usize, [fg[2], fg[3]], cap, &mut fixed, &mut asg);
            }
        }
        self.asg = asg;
        #[cfg(feature = "prof")] let tk = tsc();
        if !self.asg.is_empty() {
            let mut asg = std::mem::take(&mut self.asg);
            asg.sort_unstable(); asg.dedup();
            for &(g, v0, v1) in &asg {
                let fg = p.fgroups[g as usize];
                let pr = [(fg[2], v0 as u32), (fg[3], v1 as u32)];
                let n = fg[1] as usize;
                self.c.records += 1;
                if let Ok(k) = self.eval(p, f, fg[0], Bind { pairs: &pr[..n], default_zero: false }) { self.out.push(k); }
            }
            self.asg = asg;
        }
        #[cfg(feature = "prof")] { self.prof.keys += tsc() - tk; self.prof.keys_n += self.asg.len() as u64; }
        self.out.sort_unstable(); self.out.dedup();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    /// solve_affine against direct evaluation on [0, cap) for edge-heavy random (a, b, c)
    #[test]
    fn solve_affine_matches_valuewise() {
        let mut x: u64 = 0x9E3779B97F4A7C15;
        let mut rnd = || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
        let picks = |r: u64, r2: u64| -> U256 {
            let k = U256::from(r2 % 1000);
            match r % 8 { 0 => k, 1 => U256::MAX - k, 2 => (U256::from(1u8) << 255) - k, 3 => (U256::from(1u8) << 255) + k,
                          4 => U256::from(r2), 5 => U256::from(r2) << 128, 6 => U256::ZERO.wrapping_sub(U256::from(r2 % 64)), _ => U256::from(r2 % 40) }
        };
        let (mut n, mut solved) = (0u64, 0u64);
        for _ in 0..400_000 {
            let (a, b, c) = (picks(rnd(), rnd()), picks(rnd(), rnd()), picks(rnd(), rnd()));
            let cap = [34u32, 35, 64, 65, 100, 128, 511, 512][(rnd() % 8) as usize];
            for op in 0..3u8 { for signed in [false, true] { for want in [false, true] {
                n += 1;
                let Some(m) = solve_affine(a, b, c, op, signed, want, cap) else { continue };
                solved += 1;
                for v in 0..cap {
                    let f = a.wrapping_mul(U256::from(v)).wrapping_add(b);
                    let (fx, cx) = if signed { let t = U256::from(1u8) << 255; (f ^ t, c ^ t) } else { (f, c) };
                    let r = match op { 0 => fx < cx, 1 => fx > cx, _ => fx == cx } == want;
                    assert_eq!(r, (m[(v / 64) as usize] >> (v % 64)) & 1 == 1, "a={a:x} b={b:x} c={c:x} op={op} s={signed} w={want} cap={cap} v={v}");
                }
                for v in cap..512 { assert_eq!((m[(v / 64) as usize] >> (v % 64)) & 1, 0); }
            } } }
        }
        eprintln!("cases {n} solved {solved}");
    }
    /// solve_affine2 against direct evaluation; and equal to solve_affine wherever the latter solves
    #[test]
    fn solve_affine2_matches_valuewise() {
        let mut x: u64 = 0x2545F4914F6CDD1D;
        let mut rnd = || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
        let picks = |r: u64, r2: u64| -> U256 {
            let k = U256::from(r2 % 1000);
            match r % 9 { 0 => k, 1 => U256::MAX - k, 2 => (U256::from(1u8) << 255) - k, 3 => (U256::from(1u8) << 255) + k,
                          4 => U256::from(r2), 5 => U256::from(r2) << 128, 6 => U256::ZERO.wrapping_sub(U256::from(r2 % 64)), 7 => U256::ZERO.wrapping_sub(U256::from(32u8 * (r2 % 4) as u8)), _ => U256::from(r2 % 200) }
        };
        let (mut n, mut solved, mut extra) = (0u64, 0u64, 0u64);
        for _ in 0..400_000 {
            let (a, b, c) = (picks(rnd(), rnd()), picks(rnd(), rnd()), picks(rnd(), rnd()));
            let cap = [34u32, 35, 37, 64, 65, 100, 128, 511, 512][(rnd() % 9) as usize];
            for op in 0..3u8 { for signed in [false, true] { for want in [false, true] {
                n += 1;
                let old = solve_affine(a, b, c, op, signed, want, cap);
                let Some(m) = solve_affine2(a, b, c, op, signed, want, cap) else { assert!(old.is_none()); continue };
                solved += 1; if old.is_none() { extra += 1; } else { assert_eq!(old.unwrap(), m); }
                for v in 0..cap {
                    let f = a.wrapping_mul(U256::from(v)).wrapping_add(b);
                    let (fx, cx) = if signed { let t = U256::from(1u8) << 255; (f ^ t, c ^ t) } else { (f, c) };
                    let r = match op { 0 => fx < cx, 1 => fx > cx, _ => fx == cx } == want;
                    assert_eq!(r, (m[(v / 64) as usize] >> (v % 64)) & 1 == 1, "a={a:x} b={b:x} c={c:x} op={op} s={signed} w={want} cap={cap} v={v}");
                }
                for v in cap..512 { assert_eq!((m[(v / 64) as usize] >> (v % 64)) & 1, 0); }
            } } }
        }
        eprintln!("v2 cases {n} solved {solved} of which split {extra}");
    }

    /// the decreasing branch with q = (b - c) / na = MAX (na = 1, b - c = MAX)
    /// must give lt0 = cap (`q + 1` wrapped to 0 before); fixed cases of both solvers
    #[test]
    fn solve_decreasing_qmax_fixed() {
        let t = U256::from(1u8) << 255;
        let full34 = mask_range(0, 34);
        let mut no5 = full34; no5[0] &= !(1u64 << 5);
        // improved path, a = -1 wrapping once: f = 5 - i > 0 holds on [0, 34) except i = 5 (unsigned: c = 0; signed: c = INT_MIN)
        assert_eq!(solve_affine2(U256::MAX, U256::from(5u8), U256::ZERO, 1, false, true, 34), Some(no5));
        assert_eq!(solve_affine2(U256::MAX, t + U256::from(5u8), t, 1, true, true, 34), Some(no5));
        // f < c on the same values: never
        assert_eq!(solve_affine2(U256::MAX, U256::from(5u8), U256::ZERO, 0, false, true, 34), Some([0u64; 8]));
        // default path: b = MAX (signed: INT_MAX), c = 0 (signed: INT_MIN): f < c never, f > c always
        assert_eq!(solve_affine(U256::MAX, U256::MAX, U256::ZERO, 0, false, true, 34), Some([0u64; 8]));
        assert_eq!(solve_affine(U256::MAX, U256::MAX, U256::ZERO, 1, false, true, 34), Some(full34));
        assert_eq!(solve_affine(U256::MAX, t - U256::from(1u8), t, 0, true, true, 34), Some([0u64; 8]));
        assert_eq!(solve_affine(U256::MAX, t - U256::from(1u8), t, 1, true, true, 34), Some(full34));
        assert_eq!(solve_affine2(U256::MAX, U256::MAX, U256::ZERO, 1, false, true, 34), Some(full34));
    }
    /// both solvers against direct evaluation for decreasing steps a = -1, -2 with b near 0, MAX and the signed
    /// boundary, c at the boundaries, every comparison, sign and polarity, several caps
    #[test]
    fn solve_unit_decreasing_exhaustive() {
        let t = U256::from(1u8) << 255;
        let one = U256::from(1u8);
        let mut bs = Vec::new();
        for k in 0..600u32 { let k = U256::from(k); bs.extend([k, U256::MAX - k, t + k, t - one - k]); }
        let cs = [U256::ZERO, one, U256::from(5u8), U256::from(33u8), t, t + one, t - one, U256::MAX, U256::MAX - one];
        let (mut n, mut s1, mut s2) = (0u64, 0u64, 0u64);
        for &a in &[U256::MAX, U256::MAX - one] {
            for &b in &bs { for &c in &cs { for &cap in &[34u32, 65, 512] {
                for op in 0..3u8 { for signed in [false, true] { for want in [false, true] {
                    n += 1;
                    let check = |m: [u64; 8]| {
                        for v in 0..cap {
                            let f = a.wrapping_mul(U256::from(v)).wrapping_add(b);
                            let (fx, cx) = if signed { (f ^ t, c ^ t) } else { (f, c) };
                            let r = match op { 0 => fx < cx, 1 => fx > cx, _ => fx == cx } == want;
                            assert_eq!(r, (m[(v / 64) as usize] >> (v % 64)) & 1 == 1, "a={a:x} b={b:x} c={c:x} op={op} s={signed} w={want} cap={cap} v={v}");
                        }
                        for v in cap..512 { assert_eq!((m[(v / 64) as usize] >> (v % 64)) & 1, 0); }
                    };
                    if let Some(m) = solve_affine(a, b, c, op, signed, want, cap) { s1 += 1; check(m); }
                    if let Some(m) = solve_affine2(a, b, c, op, signed, want, cap) { s2 += 1; check(m); }
                } } }
            } } }
        }
        eprintln!("unit-decreasing cases {n} solved: default {s1} improved {s2}");
    }
}

/// version-3 layout and family call expansion on hand-built plans (serialized independently of `to_bytes`,
/// following the Python exporters' `serialize` / `serialize2` / `serialize3`).
#[cfg(test)]
mod tests_v3 {
    use super::*;
    const LT_: u32 = 11;

    #[derive(Default, Clone)]
    struct PB {
        consts: Vec<U256>, nodes: Vec<[u32; 4]>, side: Vec<u32>, lists: Vec<Vec<u32>>,
        sgroups: Vec<u32>, salts: Vec<[u32; 4]>, fgroups: Vec<[u32; 4]>, falts: Vec<[u32; 9]>, side2: Vec<u32>, n_idx: u32,
        cgroups: Vec<[u32; 6]>, cside: Vec<u32>, calts: Vec<[u32; 4]>, n_family: u32,
        fcgroups: Vec<[u32; 8]>, fcalts: Vec<[u32; 9]>, cside2: Vec<u32>,
    }
    impl PB {
        fn dep(&self, j: u32) -> u32 { (self.nodes[j as usize][0] >> 16) & 1 }
        fn node(&mut self, tag: u32, sub: u32, a: u32, b: u32, n: u32, dep: u32) -> u32 {
            self.nodes.push([tag | (sub << 8) | (dep << 16), a, b, n]); (self.nodes.len() - 1) as u32
        }
        fn c(&mut self, v: U256) -> u32 { self.consts.push(v); let ci = (self.consts.len() - 1) as u32; self.node(T_CONST, 0, ci, 0, 0, 0) }
        fn cu(&mut self, v: u64) -> u32 { self.c(U256::from(v)) }
        fn sel(&mut self, s: u32) -> u32 { self.c(U256::from(s) << 224) }
        fn idx(&mut self, i: u32) -> u32 { self.n_idx = self.n_idx.max(i + 1); self.node(T_IDX, 0, i, 0, 0, 1) }
        fn cd(&mut self, x: u32) -> u32 { let d = self.dep(x); self.node(T_CD, 0, x, 0, 0, d) }
        fn op(&mut self, sub: u32, args: &[u32]) -> u32 {
            let b = self.side.len() as u32; self.side.extend_from_slice(args);
            let d = args.iter().map(|&a| self.dep(a)).max().unwrap_or(0);
            self.node(T_OP, sub, 0, b, args.len() as u32, d)
        }
        fn lin(&mut self, c0: u64, terms: &[(u64, u32)]) -> u32 {
            self.consts.push(U256::from(c0)); let a = (self.consts.len() - 1) as u32;
            let mut sd = Vec::new();
            for &(c, x) in terms { self.consts.push(U256::from(c)); sd.push((self.consts.len() - 1) as u32); sd.push(x); }
            let b = self.side.len() as u32; self.side.extend_from_slice(&sd);
            let d = terms.iter().map(|&(_, x)| self.dep(x)).max().unwrap_or(0);
            self.node(T_LIN, 0, a, b, terms.len() as u32, d)
        }
        fn list(&mut self, items: &[u32]) -> u32 { self.lists.push(items.to_vec()); (self.lists.len() - 1) as u32 }
        /// `i < CD(4)` (the array length word), wanted true
        fn lt_len(&mut self, i: u32) -> u32 { let ix = self.idx(i); let c4 = self.cu(4); let n = self.cd(c4); let lt = self.op(LT_, &[ix, n]); self.list(&[lt | 1 << 31]) }
        /// CD(36 + 32 i): element i of the array
        fn elem(&mut self, i: u32) -> u32 { let ix = self.idx(i); let l = self.lin(36, &[(32, ix)]); self.cd(l) }
        fn bytes(&self, version: u32) -> Vec<u8> {
            fn w(o: &mut Vec<u8>, x: u32) { o.extend_from_slice(&x.to_le_bytes()); }
            fn flat<const K: usize>(o: &mut Vec<u8>, v: &[[u32; K]]) { w(o, v.len() as u32); for r in v { for &x in r { w(o, x); } } }
            fn u32s(o: &mut Vec<u8>, v: &[u32]) { w(o, v.len() as u32); for &x in v { w(o, x); } }
            let mut o = b"EAPF".to_vec(); w(&mut o, version); w(&mut o, 0);
            w(&mut o, self.consts.len() as u32); for c in &self.consts { o.extend_from_slice(&c.to_be_bytes::<32>()); }
            flat(&mut o, &self.nodes);
            u32s(&mut o, &self.side);
            w(&mut o, self.lists.len() as u32); let mut acc = 0u32; w(&mut o, 0);
            for l in &self.lists { acc += l.len() as u32; w(&mut o, acc); }
            let data: Vec<u32> = self.lists.concat(); u32s(&mut o, &data);
            u32s(&mut o, &self.sgroups); flat(&mut o, &self.salts); flat(&mut o, &self.fgroups); flat(&mut o, &self.falts);
            u32s(&mut o, &self.side2); w(&mut o, self.n_idx);
            if version >= 2 { flat(&mut o, &self.cgroups); u32s(&mut o, &self.cside); flat(&mut o, &self.calts); w(&mut o, self.n_family); }
            if version >= 3 { flat(&mut o, &self.fcgroups); flat(&mut o, &self.fcalts); u32s(&mut o, &self.cside2); }
            o
        }
    }
    const S: u32 = 0x1234_5678;
    const TRANSFER: u32 = 0xa905_9cbb;
    fn addr(k: u64) -> U256 { (U256::from(0xA11CEu64) << 100) + U256::from(k) }
    /// calldata S | n | a_0 .. a_{n-1} | pad (pad zero bytes)
    fn batch_cd(sel: u32, n: u64, pad: usize) -> Vec<u8> {
        let mut cd = sel.to_be_bytes().to_vec(); cd.extend_from_slice(&U256::from(n).to_be_bytes::<32>());
        for k in 0..n { cd.extend_from_slice(&addr(k).to_be_bytes::<32>()); }
        cd.resize(cd.len() + pad, 0); cd
    }
    fn frame(cd: &[u8]) -> Frame<'_> {
        let mut env = [U256::ZERO; N_ENV]; env[4] = U256::from(cd.len()); env[7] = U256::from(1u8); env[12] = U256::from(1u8);
        Frame { calldata: cd, env, sload: None }
    }
    fn word(v: U256) -> [u8; 32] { v.to_be_bytes::<32>() }
    /// storage: index-free key CD(4), family key CD(36 + 32 i0) for i0 < CD(4); index-free call: target CD(36), payload
    /// S2 (4 bytes); family call (index 1): CALL CD(36 + 32 i1) with transfer(CD(36 + 32 i1), 1000), selector S
    fn batch_plan() -> PB {
        let mut b = PB::default();
        let c4 = b.cu(4); let k0 = b.cd(c4); let el = b.list(&[]);
        b.sgroups.push(k0); b.salts.push([0, 0, 0, el]);
        let fk = b.elem(0); let l0 = b.lt_len(0);
        b.fgroups.push([fk, 1, 0, 0]); b.falts.push([0, 1, S, 0, 0, 0, l0, NONE32, NONE32]);
        let c36 = b.cu(36); let t = b.cd(c36); let sz = b.cu(4); let r0 = b.cu(0); let v0 = b.sel(0x0bad_cafe);
        b.cgroups.push([3, t, sz, 0, 1, 0]); b.cside.extend_from_slice(&[r0, v0, NONE32]); b.calts.push([0, 0, 0, el]);
        b.n_family = 1;
        let ft = b.elem(1); let l1 = b.lt_len(1); let fsz = b.cu(68); let r4 = b.cu(4); let r36 = b.cu(36);
        let vs = b.sel(TRANSFER); let v1000 = b.cu(1000);
        let off = b.cside.len() as u32;
        b.cside.extend_from_slice(&[r0, vs, NONE32, r4, ft, NONE32, r36, v1000, NONE32]);
        b.fcgroups.push([0, ft, fsz, off, 3, 1, 1, 0]); b.fcalts.push([0, 1, S, 0, 0, 0, l1, NONE32, NONE32]);
        b
    }
    fn run(p: &Plan, cd: &[u8], legacy: bool) -> (Vec<U256>, Vec<CallOut>, Vec<Option<(u32, u16, u16)>>, Scratch) {
        let mut sc = Scratch::default(); sc.interval = true; sc.legacy_payload = legacy;
        let fr = frame(cd);
        sc.instantiate(p, &fr);
        let keys = sc.out.clone();
        sc.instantiate_calls(p, &fr, true);
        (keys, sc.calls.clone(), sc.call_idx.clone(), sc)
    }

    /// lists equal up to the solved index's number share a class; a list given two indices joins none;
    /// keys, calls, their family annotation and the caps are the same with the cache by class on and off
    #[test]
    fn sat_classes_on_off_equal() {
        let mut b = batch_plan();
        // a second family storage group (index 2) and a second family call group (index 3), as the first ones
        let fk2 = b.elem(2); let l2 = b.lt_len(2);
        b.fgroups.push([fk2, 1, 2, 0]); b.falts.push([1, 1, S, 0, 0, 0, l2, NONE32, NONE32]);
        let ft3 = b.elem(3); let l3 = b.lt_len(3); let fsz = b.cu(68); let r0 = b.cu(0); let r4 = b.cu(4); let r36 = b.cu(36);
        let vs = b.sel(TRANSFER); let v1000 = b.cu(1000);
        let off = b.cside.len() as u32;
        b.cside.extend_from_slice(&[r0, vs, NONE32, r4, ft3, NONE32, r36, v1000, NONE32]);
        b.fcgroups.push([0, ft3, fsz, off, 3, 1, 3, 0]); b.fcalts.push([1, 1, S, 0, 0, 0, l3, NONE32, NONE32]);
        // one list (on index 5) given to two family storage groups with key indices 5 and 6
        let lc = b.lt_len(5); let fk5 = b.elem(5); let fk6 = b.elem(6);
        b.fgroups.push([fk5, 1, 5, 0]); b.falts.push([2, 1, S, 0, 0, 0, lc, NONE32, NONE32]);
        b.fgroups.push([fk6, 1, 6, 0]); b.falts.push([3, 1, S, 0, 0, 0, lc, NONE32, NONE32]);
        let mut p = Plan::parse_analyzed(&b.bytes(3));
        assert!(p.sat_cls.is_empty()); // not classed unless asked
        p.classify_lists();
        let (l0, l1) = (b.falts[0][6] as usize, b.fcalts[0][6] as usize);
        let c = p.sat_cls[l0];
        assert_ne!(c, NONE32);
        for l in [l1, l2 as usize, l3 as usize] { assert_eq!(p.sat_cls[l], c, "list {l}"); }
        assert_eq!(p.sat_cls[lc as usize], NONE32);
        assert_eq!((p.n_sat_lists, p.n_sat_classes, p.n_sl_conflict), (5, 1, 1));
        for (n, pad) in [(0u64, 0usize), (1, 0), (3, 0), (7, 5), (40, 64)] {
            let cd = batch_cd(S, n, pad);
            let fr = frame(&cd);
            let mut out = Vec::new();
            for on in [false, true] {
                let mut sc = Scratch::default(); sc.interval = true; sc.sat_classes = on;
                sc.instantiate(&p, &fr);
                let keys = sc.out.clone(); let ss = sc.c.satsets;
                sc.instantiate_calls(&p, &fr, true);
                let calls: Vec<(u8, U256, Option<Vec<u8>>)> = sc.calls.iter().map(|c| (c.kind, c.target, c.payload.clone())).collect();
                out.push((keys, calls, sc.call_idx.clone(), sc.c_family_capped, sc.call_holes.clone(), ss));
            }
            let (a, b2) = (&out[0], &out[1]);
            assert_eq!((&a.0, &a.1, &a.2, a.3, &a.4), (&b2.0, &b2.1, &b2.2, b2.3, &b2.4), "n={n}");
            assert!(b2.5 < a.5, "n={n}: storage satisfying sets {} with classes, {} without", b2.5, a.5);
            if n > 0 { assert_eq!(a.2.iter().filter(|x| x.is_some()).count(), 2 * n as usize); }
        }
    }

    /// lists that differ in a constant, the wanted polarity, the operator or a node kind fall in different
    /// classes; members of each class get their own class's sets; a fixed (non-key) index reads its class slot, and its set
    /// reaches the output through a multi-index list; a list given another index as a fixed call index joins no class. Keys
    /// and calls with the cache by class on equal those with it off, and the keys depend on the classes being kept apart.
    #[test]
    fn sat_classes_discriminate_and_fixed() {
        const GT_: u32 = 12;
        let mut b = batch_plan();
        let lt_w = |b: &mut PB, i: u32, off: u64| { let ix = b.idx(i); let c = b.cu(off); let w = b.cd(c); let x = b.op(LT_, &[ix, w]); b.list(&[x | 1 << 31]) };
        let not_lt4 = |b: &mut PB, i: u32| { let ix = b.idx(i); let c = b.cu(4); let w = b.cd(c); let x = b.op(LT_, &[ix, w]); b.list(&[x]) };
        let gt4 = |b: &mut PB, i: u32| { let ix = b.idx(i); let c = b.cu(4); let w = b.cd(c); let x = b.op(GT_, &[ix, w]); b.list(&[x | 1 << 31]) };
        let lt3 = |b: &mut PB, i: u32| { let ix = b.idx(i); let c = b.cu(3); let x = b.op(LT_, &[ix, c]); b.list(&[x | 1 << 31]) };
        // family storage group with key 1e6 g + i on index i and condition list li
        let fam = |b: &mut PB, g: u64, i: u32, li: u32| {
            let ix = b.idx(i); let k = b.lin(1_000_000 * g, &[(1, ix)]); let fg = b.fgroups.len() as u32;
            b.fgroups.push([k, 1, i, 0]); b.falts.push([fg, 1, S, 0, 0, 0, li, NONE32, NONE32]);
        };
        let mut forms: Vec<Vec<u32>> = vec![vec![]; 4];
        for (f, ids) in [(0usize, [10u32, 11]), (1, [12, 13]), (2, [14, 15]), (3, [16, 17])] {
            for (j, &i) in ids.iter().enumerate() {
                let li = match f { 0 => lt_w(&mut b, i, 36), 1 => not_lt4(&mut b, i), 2 => gt4(&mut b, i), _ => lt3(&mut b, i) };
                fam(&mut b, 1 + 2 * f as u64 + j as u64, i, li); forms[f].push(li);
            }
        }
        let l30 = b.lt_len(30); fam(&mut b, 20, 30, l30);
        // key index 40 on i < 3, fixed index 41 on !(i < CD(4)) (its minimum is n), multi-index list i40 < i41
        let l40 = lt3(&mut b, 40); let l41 = not_lt4(&mut b, 41);
        let (i40, i41) = (b.idx(40), b.idx(41)); let m = b.op(LT_, &[i40, i41]); let lm = b.list(&[m | 1 << 31]);
        let k40 = b.lin(30_000_000, &[(1, i40)]); let fg = b.fgroups.len() as u32;
        let off = b.side2.len() as u32; b.side2.extend_from_slice(&[41, l41]);
        b.fgroups.push([k40, 1, 40, 0]); b.falts.push([fg, 1, S, off, 0, 1, l40, NONE32, lm]);
        // call side: a family call group (index 50) with list lx as its fixed index 51, then a second one keyed by index 53 on
        // lx, so lx is solved for 53 and also requested for 51
        let lx = b.lt_len(53);
        for (i, fix) in [(50u32, true), (53, false)] {
            let ft = b.elem(i); let li = if fix { b.lt_len(i) } else { lx };
            let (fsz, r0, r4, r36, vs, v1000) = (b.cu(68), b.cu(0), b.cu(4), b.cu(36), b.sel(TRANSFER), b.cu(1000));
            let o = b.cside.len() as u32;
            b.cside.extend_from_slice(&[r0, vs, NONE32, r4, ft, NONE32, r36, v1000, NONE32]);
            let o2 = b.cside2.len() as u32; let nfix = if fix { b.cside2.extend_from_slice(&[51, lx]); 1 } else { 0 };
            let g = b.fcgroups.len() as u32;
            b.fcgroups.push([0, ft, fsz, o, 3, 1, i, 0]); b.fcalts.push([g, 1, S, o2, 0, nfix, li, NONE32, NONE32]);
        }
        let mut p = Plan::parse_analyzed(&b.bytes(3));
        p.classify_lists();
        let base = p.sat_cls[b.falts[0][6] as usize];
        for l in [b.fcalts[0][6], l30, b.fcalts[1][6]] { assert_eq!(p.sat_cls[l as usize], base, "list {l}"); }
        let mut seen = vec![base];
        for f in &forms {
            let c = p.sat_cls[f[0] as usize];
            assert_eq!(p.sat_cls[f[1] as usize], c);
            assert!(c != NONE32 && !seen.contains(&c), "form class {c} not distinct"); seen.push(c);
        }
        assert_eq!(p.sat_cls[l41 as usize], p.sat_cls[forms[1][0] as usize]);
        assert_eq!(p.sat_cls[l40 as usize], p.sat_cls[forms[3][0] as usize]);
        assert_eq!(p.sat_cls[lx as usize], NONE32);
        assert_eq!((p.n_sat_lists, p.n_sat_classes, p.n_sl_conflict), (15, 5, 1));
        for (n, pad) in [(0u64, 0usize), (1, 0), (3, 0), (7, 5)] {
            let cd = batch_cd(S, n, pad);
            let fr = frame(&cd);
            let mut out = Vec::new();
            for on in [false, true] {
                let mut sc = Scratch::default(); sc.interval = true; sc.sat_classes = on;
                sc.instantiate(&p, &fr);
                let keys = sc.out.clone();
                sc.instantiate_calls(&p, &fr, true);
                let calls: Vec<(u8, U256, Option<Vec<u8>>)> = sc.calls.iter().map(|c| (c.kind, c.target, c.payload.clone())).collect();
                out.push((keys, calls, sc.call_idx.clone()));
            }
            assert_eq!(out[0], out[1], "n={n}");
            // per group, the values the keys 1e6 g + v carry: each form's own set, which a merge of the classes would change
            let small: Vec<u64> = out[1].0.iter().filter(|k| k.as_limbs()[1..].iter().all(|&x| x == 0)).map(|k| k.as_limbs()[0]).collect();
            let vals = |g: u64| -> Vec<u64> { small.iter().filter(|&&k| k / 1_000_000 == g).map(|&k| k % 1_000_000).collect() };
            let lt = |m: u64| -> Vec<u64> { (0..m).collect() };
            // CD(36) is the first element (0 past the end of the calldata when n = 0): unbounded, smallest value only
            for g in [1u64, 2] { assert_eq!(vals(g), if n == 0 { vec![] } else { vec![0] }, "n={n}: i < CD(36)"); }
            for g in [3u64, 4] { assert_eq!(vals(g), vec![n], "n={n}: !(i < CD(4))"); }
            for g in [5u64, 6] { assert_eq!(vals(g), vec![n + 1], "n={n}: i > CD(4)"); }
            for g in [7u64, 8] { assert_eq!(vals(g), lt(3), "n={n}: i < 3"); }
            assert_eq!(vals(20), lt(n), "n={n}: i < CD(4) on index 30");
            assert_eq!(vals(30), lt(3.min(n)), "n={n}: key index 40 below the fixed index 41 = n");
        }
    }

    #[test]
    fn v3_parse_roundtrip() {
        let b = batch_plan();
        for ver in [1u32, 2, 3] {
            let bytes = b.bytes(ver);
            let p = Plan::parse_analyzed(&bytes);
            assert_eq!(p.version, ver);
            assert_eq!(p.to_bytes(), bytes, "round trip v{ver}");
            assert_eq!(p.fcgroups.len(), if ver >= 3 { 1 } else { 0 });
            assert_eq!(p.cgroups.len(), if ver >= 2 { 1 } else { 0 });
            if ver >= 3 { assert_eq!(p.fcgroups[0], b.fcgroups[0]); assert_eq!(p.fcalts[0], b.fcalts[0]); assert_eq!(p.fc_sel, vec![(S, 0, 1)]); }
        }
        // delegate and no-summary files
        let mut d = b"EAPF".to_vec(); d.extend_from_slice(&1u32.to_le_bytes()); d.extend_from_slice(&1u32.to_le_bytes()); d.extend_from_slice(&[7u8; 20]);
        assert_eq!(Plan::parse(&d).to_bytes(), d);
        let mut e = b"EAPF".to_vec(); e.extend_from_slice(&1u32.to_le_bytes()); e.extend_from_slice(&2u32.to_le_bytes());
        assert_eq!(Plan::parse(&e).to_bytes(), e);
    }

    #[test]
    fn family_calls_batch_transfer() {
        let b = batch_plan();
        let cd = batch_cd(S, 3, 0);
        let p3 = Plan::parse_analyzed(&b.bytes(3));
        let p2 = Plan::parse_analyzed(&b.bytes(2));
        let (k3, c3, i3, sc3) = run(&p3, &cd, false);
        let (k2, c2, i2, _) = run(&p2, &cd, false);
        // storage keys and index-free calls identical to version 2
        let mut want: Vec<U256> = vec![U256::from(3u8), addr(0), addr(1), addr(2)]; want.sort();
        assert_eq!(k3, want); assert_eq!(k2, want);
        assert_eq!(c2.len(), 1); assert_eq!(i2, vec![None]);
        assert_eq!((c3[0].kind, c3[0].target, c3[0].payload.clone()), (c2[0].kind, c2[0].target, c2[0].payload.clone()));
        assert_eq!(c2[0].target, addr(0)); assert_eq!(c2[0].payload.as_deref(), Some(&0x0bad_cafeu32.to_be_bytes()[..]));
        // family calls: one per array element, payload transfer(a_i, 1000)
        assert_eq!(c3.len(), 4); assert_eq!(sc3.c_family, 3); assert_eq!(sc3.c_family_capped, 0); assert_eq!(sc3.c_nopayload, 0);
        for k in 0..3usize {
            let c = &c3[1 + k];
            assert_eq!(i3[1 + k], Some((0, k as u16, 0)));
            assert_eq!((c.kind, c.target), (0, addr(k as u64)));
            let mut pl = TRANSFER.to_be_bytes().to_vec(); pl.extend_from_slice(&word(addr(k as u64))); pl.extend_from_slice(&word(U256::from(1000u32)));
            assert_eq!(c.payload.as_deref(), Some(&pl[..]));
        }
        // storage counters are not touched by the family call expansion
        let mut sc = Scratch::default(); sc.interval = true; let fr = frame(&cd); sc.instantiate(&p3, &fr);
        let before = (sc.c.records, sc.c.cons_evals, sc.c.family_alts, sc.c.satsets);
        sc.instantiate_calls(&p3, &fr, true);
        assert_eq!(before, (sc.c.records, sc.c.cons_evals, sc.c.family_alts, sc.c.satsets));
        // standalone (no prior instantiate) gives the same calls
        let mut sc = Scratch::default(); sc.interval = true; sc.instantiate_calls(&p3, &fr, false);
        assert_eq!(sc.calls.len(), 4); assert_eq!(sc.calls[3].target, addr(2));
        // value-by-value satisfying sets (interval off) agree
        let mut sc = Scratch::default(); sc.instantiate(&p3, &fr); sc.instantiate_calls(&p3, &fr, true);
        assert_eq!(sc.calls.iter().map(|c| c.target).collect::<Vec<_>>(), c3.iter().map(|c| c.target).collect::<Vec<_>>());
        // other selector: the family alternative is rejected, the index-free call stays
        let (_, c, _, _) = run(&p3, &batch_cd(0x1111_1111, 3, 0), false);
        assert_eq!(c.len(), 1);
    }

    #[test]
    fn family_calls_unbounded_takes_smallest() {
        let mut b = batch_plan();
        b.fcalts[0][6] = NONE32; // no loop bound recorded for the key index
        let p = Plan::parse_analyzed(&b.bytes(3));
        let (_, c, i, sc) = run(&p, &batch_cd(S, 3, 0), false);
        assert_eq!(sc.c_family, 1); assert_eq!(i[1], Some((0, 0, 0))); assert_eq!(c[1].target, addr(0));
    }

    #[test]
    fn family_calls_two_keys_capped() {
        let mut b = batch_plan();
        let (x2, x3) = (b.idx(2), b.idx(3)); let c96 = b.cu(96);
        let lt2 = b.op(LT_, &[x2, c96]); let lt3 = b.op(LT_, &[x3, c96]);
        let (l2, l3) = (b.list(&[lt2 | 1 << 31]), b.list(&[lt3 | 1 << 31]));
        let t = b.cu(0xbeef_0000); let sz = b.cu(64); let (r0, r32) = (b.cu(0), b.cu(32));
        let off = b.cside.len() as u32; b.cside.extend_from_slice(&[r0, x2, NONE32, r32, x3, NONE32]);
        b.fcgroups.push([3, t, sz, off, 2, 2, 2, 3]); b.fcalts.insert(0, [1, 0, 0, 0, 0, 0, l2, l3, NONE32]);
        let p = Plan::parse_analyzed(&b.bytes(3));
        let cd = batch_cd(S, 3, 2048); // cap = min(512, len / 32 + 34) = 102: sets 0..95 do not reach cap - 1, bounded
        let (_, c, i, sc) = run(&p, &cd, false);
        assert_eq!(sc.c_family as usize, 3 + MAX_FAMILY_CALLS);
        assert_eq!(sc.c_family_capped as usize, 96 * 96 - MAX_FAMILY_CALLS);
        let g1: Vec<_> = i.iter().flatten().filter(|x| x.0 == 1).collect();
        assert_eq!(g1.len(), MAX_FAMILY_CALLS);
        assert_eq!(*g1[0], (1, 0, 0)); assert_eq!(*g1[MAX_FAMILY_CALLS - 1], (1, 5, 31));
        let last = c.iter().zip(i.iter()).filter(|(_, x)| matches!(x, Some((1, _, _)))).last().unwrap().0;
        let mut pl = word(U256::from(5u8)).to_vec(); pl.extend_from_slice(&word(U256::from(31u8)));
        assert_eq!(last.payload.as_deref(), Some(&pl[..]));
    }

    #[test]
    fn expression_offset_words() {
        // index-free call whose payload is an abi-encoded array built in a loop: S3 | 32 | n | a_0 .. a_{n-1}
        let mut b = batch_plan();
        let x4 = b.idx(4); let lo = b.lin(68, &[(32, x4)]); let lv = b.lin(36, &[(32, x4)]); let v = b.cd(lv);
        let (r0, r4, r36) = (b.cu(0), b.cu(4), b.cu(36)); let s3 = b.sel(0x3333_3333); let c32 = b.cu(32);
        let c4 = b.cu(4); let n = b.cd(c4); let sz = b.cu(4 + 64 + 96); let t = b.cu(0xbeef_0001);
        let off = b.cside.len() as u32;
        b.cside.extend_from_slice(&[r0, s3, NONE32, r4, c32, NONE32, r36, n, NONE32, lo, v, NONE32]);
        b.cgroups.push([0, t, sz, off, 4, 0]); let el = b.list(&[]); b.calts.insert(0, [1, 0, 0, el]);
        let cd = batch_cd(S, 3, 0);
        let mut want = 0x3333_3333u32.to_be_bytes().to_vec(); want.extend_from_slice(&word(U256::from(32u8)));
        want.extend_from_slice(&word(U256::from(3u8))); for k in 0..3 { want.extend_from_slice(&word(addr(k))); }
        let p3 = Plan::parse_analyzed(&b.bytes(3));
        let (_, c, _, _) = run(&p3, &cd, false);
        let x = c.iter().find(|c| c.target == U256::from(0xbeef_0001u64)).unwrap();
        assert_eq!(x.payload.as_deref(), Some(&want[..]));
        // version-1/2 rule: the expression offset does not evaluate without a loop index -> payload unknown
        let (_, c, _, sc) = run(&p3, &cd, true);
        assert!(c.iter().find(|c| c.target == U256::from(0xbeef_0001u64)).unwrap().payload.is_none()); assert_eq!(sc.c_nopayload, 1);
        let p2 = Plan::parse_analyzed(&b.bytes(2));
        let (_, c, _, _) = run(&p2, &cd, false);
        assert!(c.iter().find(|c| c.target == U256::from(0xbeef_0001u64)).unwrap().payload.is_none());
        let mut ids = Vec::new(); p3.idx_ids(v, &mut ids); assert_eq!(ids, vec![4]);
    }

    #[test]
    fn unknown_value_words_and_holes() {
        // index-free call groups (version 3) with T_UNK values (exporter --unkval); target = 0xbeef_1000 + case
        let mut b = batch_plan();
        let el = b.list(&[]);
        let s70 = b.sel(0x70a0_8231); let c36 = b.cu(36); let a0 = b.cd(c36);
        let (r0, r4) = (b.cu(0), b.cu(4)); let rneg = b.c(U256::ZERO.wrapping_sub(U256::from(32u8)));
        let u0 = b.node(T_UNK, 0, 0, 0, 0, 0); let u1 = b.node(T_UNK, 1, 0, 0, 0, 0);
        let (z36, z68) = (b.cu(36), b.cu(68));
        let cases: Vec<(u32, Vec<[u32; 3]>)> = vec![
            (z36, vec![[rneg, u0, NONE32], [r0, s70, NONE32], [r4, a0, NONE32]]), // 0: unknown word outside the buffer
            (z36, vec![[r0, s70, NONE32], [r4, u0, NONE32], [r4, a0, NONE32]]),   // 1: overwritten by a later word
            (z36, vec![[r0, s70, NONE32], [r4, u0, NONE32]]),                     // 2: unknown bytes remain
            (z36, vec![[r0, s70, NONE32], [r4, u1, NONE32], [r4, a0, NONE32]]),   // 3: unknown REGION, then covered to the end
            (z68, vec![[r0, s70, NONE32], [r4, u1, NONE32], [r4, a0, NONE32]]),   // 4: unknown REGION, 36..68 stay unknown
            (z68, vec![[r0, s70, NONE32], [r4, a0, NONE32]]),                     // 5: 36..68 covered by no word (holes)
        ];
        for (k, (sz, ws)) in cases.iter().enumerate() {
            let t = b.cu(0xbeef_1000 + k as u64);
            let off = b.cside.len() as u32;
            for w in ws { b.cside.extend_from_slice(w); }
            let g = b.cgroups.len() as u32; b.cgroups.push([3, t, *sz, off, ws.len() as u32, 0]); b.calts.insert(0, [g, 0, 0, el]);
        }
        let cd = batch_cd(S, 3, 0);
        let mut bal = 0x70a0_8231u32.to_be_bytes().to_vec(); bal.extend_from_slice(&word(addr(0)));
        let p3 = Plan::parse_analyzed(&b.bytes(3));
        let get = |legacy: bool| {
            let (_, c, _, sc) = run(&p3, &cd, legacy);
            (0..6u64).map(|k| { let i = c.iter().position(|x| x.target == U256::from(0xbeef_1000 + k)).unwrap(); (c[i].payload.clone(), sc.call_holes[i]) }).collect::<Vec<_>>()
        };
        let py = get(false);
        assert_eq!(py[0], (Some(bal.clone()), 0));
        assert_eq!(py[1], (Some(bal.clone()), 0));
        assert_eq!(py[2], (None, 0));
        assert_eq!(py[3], (Some(bal.clone()), 0));
        assert_eq!(py[4], (None, 0));
        let mut bal68 = bal.clone(); bal68.resize(68, 0);
        assert_eq!(py[5], (Some(bal68.clone()), 32));
        // version-1/2 rule: any T_UNK value makes the payload unknown (the exporter without --unkval drops it)
        let lg = get(true);
        for k in 0..5 { assert_eq!(lg[k], (None, 0), "legacy case {k}"); }
        assert_eq!(lg[5], (Some(bal68), 32));
    }
}
