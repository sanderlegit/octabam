#!/usr/bin/env python3
"""QREC TLEN gates: a manual recording under QREC TLEN starts on the
recording track's own loop point, to the sample, under the ColdFire port.

    python3 tools/verify/verify_qrec_tlen.py REMIX [--project DIR] [--only a,b]
    make check REMIX=qrec-tlen          # OT_PROJECT=<dir> gives it a project

Every fixture is a copy of the project: bank 1, every pattern and part
rewritten (tools/hw/ot_project.py's offsets). T1 records: QREC, TRIG, RLEN
as the case says. T2 is the REFERENCE: the same length and scale as T1, a
REC1 trig on step 1, QREC OFF, so its arm sample (0x46c7fa84[1]) marks every
sample at which T1's loop restarts, in the same clock as T1's arm
(0x46c7fa84[0] = [0x46104cf8] + the in-frame offset, 0x40006b4a). The press
is the panel's own: TRACK 1 down, REC AB down/up, TRACK 1 up (a live script,
transport started with PLAY), which reaches FUN_40005178 through
FUN_400836d8. EXPECTED = the first reference arm written after the press
staged its class (0x800018be[0]); the take must arm on exactly that sample,
through the comparator (0x4000b2ce..), never the immediate path.

Cases (240 BPM unless noted; a step is 2,756.25 samples):
  pt256      PER TRACK, master 256 / T1 64 at 1X. TLEN: the next 64-step
             loop. Control (stock image, QREC PLEN): the 256-step loop.
  inf        PER TRACK, master INF / T1 64. TLEN: the next loop. Control
             (stock PLEN): never.
  normal     NORMAL, pattern 64 at 1X, 128 BPM (loop points mid-frame).
             TLEN arms where stock PLEN arms, with the same subframe.
  slow       PER TRACK, master 16 at 1X / T1 32 at 1/8X: the master restarts
             the track every 16 master steps; TLEN on that restart.
  slow/after the same, pressed 200 ms after a restart: the next restart,
             nothing in between.
  mixed      PER TRACK, master INF at 1X / T1 16 at 3/4X: a loop of 128
             ticks over master steps of 6. Loop start k (tick 128k) fires at
             the first master step at or after it, (-128k) mod 6 ticks late
             (459.375 samples a tick): 4, 2, 0, asserted to the sample.
  fast       T1 16 at 2X (48 ticks, on the master grid): exact; the bit is
             set at the master step BEFORE the wrap is processed. fast15:
             15 at 2X (45 ticks): 3 ticks late on odd loops.
  chg        PER TRACK, master 256, CHG 16 / T1 48: a pattern change queued
             while waiting moves the take to the change (step 64), ahead of
             T1's own wrap (96); the control without the change arms at 96.
  one2/hold  TRIG ONE2 and HOLD: the take starts on the loop point.
  e2e        QREC TLEN + RLEN PLEN + TRIG ONE, T1 48 at 1/2X over master
             256: one arm on the loop point, LIMIT (0x46c7fe24[0], the end
             post) = one loop, 264,600 samples, and no second arm.
  fmt        the QREC formatter (descriptor word 0x400d3d9a) draws 17 as
             TLEN and 12 as 64 (called under the port).

SKIPs without a project (OT_PROJECT, --project or ~/.octabam_project) or the
port. What it cannot see: hardware timing, the drawn screen, the setup
editor's encoder (the count poke is asserted on the image, not turned).
"""
import argparse, os, pathlib, re, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import ot_project as otp  # noqa: E402
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/qrec_tlen"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
BASE = 0x40000400

BLOB = 0x400e21e0                      # [0x46c82456]: bank 1 in RAM
QREC_LIVE = BLOB + 0x8f382 + 9         # T1's QREC, part 1 (FUN_40005178 reads it here)
ARM, REC, CLS, LIMIT, PATTERN = 0x46c7fa84, 0x46c7e9fa, 0x800018be, 0x46c7fe24, 0x800065be
COMPARATOR = (0x4000b384, 0x4000b456)
TICK_SAMPLES_240 = 2646000 / 5760
X1, X34, X12, X18 = 2, 3, 4, 6         # scale indexes: 1X, 3/4X, 1/2X, 1/8X
TICKS = [3, 4, 6, 8, 12, 24, 48]
REC_AB, PTN = 0x2b, 0x2e


def pat_file(p, ram):
    """File offset of RAM pattern-record byte `ram` (+0x8e50..0x8e56): the
    PTRN chunk's tail, `ot_project.set_pattern_scale`'s pair at +0x8e53."""
    return otp.PTRN0 + p * otp.PTRN_FSTRIDE + otp.PTRN_FSTRIDE - 11 + ram - 0x8e51


def make(src, dest, *, pertrack, mlen, mscale, tlen, tscale, qrec, trig=0, rlen=63, tempo=5760, chg=None):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in pathlib.Path(src).iterdir():
        if f.is_file() and f.suffix.lower() in (".work", ".strd"):
            shutil.copy2(f, dest / f.name)

    def mut(d):
        for p in range(16):
            if pertrack:
                d[pat_file(p, 0x8e50)], d[pat_file(p, 0x8e51)] = (mlen >> 8) & 0xff, mlen & 0xff
                d[pat_file(p, 0x8e52)], d[pat_file(p, 0x8e55)] = mscale, 1
            else:
                d[pat_file(p, 0x8e53)], d[pat_file(p, 0x8e54)], d[pat_file(p, 0x8e55)] = mlen, mscale, 0
            if chg is not None:
                d[pat_file(p, 0x8e56)] = chg
            for t in range(8):
                ln, sc = (tlen, tscale) if t < 2 else (16, mscale)
                d[otp.trac_off(p, t) + 0x50], d[otp.trac_off(p, t) + 0x51] = ln, sc
                for m in (0x20, 0x28, 0x30):                 # no recorder trigs but the reference
                    for i in range(8):
                        d[otp.trac_off(p, t) + m + i] = 0
            d[otp.trac_off(p, 1) + 0x20 + 7] |= 1            # T2: REC1 on step 1
        for pi in range(otp.NPARTS_ALL):
            for t, vals in ((0, (("QREC", qrec), ("TRIG", trig), ("RLEN", rlen))),
                            (1, (("QREC", -1), ("TRIG", 0), ("RLEN", 0)))):
                b = otp.PART_BASE + pi * otp.PART_STRIDE + otp.REC_SETUP_OFF + t * 12
                for f, v in vals:
                    d[b + otp.REC_FIELDS.index(f)] = v & 0xff
            # T1 records from T2's sources: T2's arm is the reference clock,
            # and a different source moved T1's arm 0x50 samples on stock too
            b = otp.PART_BASE + pi * otp.PART_STRIDE + otp.REC_SETUP_OFF
            for f in ("INAB", "INCD", "SRC3", "AB", "CD"):
                d[b + otp.REC_FIELDS.index(f)] = d[b + 12 + otp.REC_FIELDS.index(f)]
    otp._bank_write(dest, 1, mut, guard=False)
    for suffix in ("work", "strd"):
        path = dest / f"project.{suffix}"
        if not path.is_file():
            continue
        raw = path.read_bytes().decode("latin1")
        for pat, val in ((r"(\[STATES\]\r?\nBANK=)\d+", "0"), (r"(\r?\nPATTERN=)\d+", "0"),
                         (r"(\r?\nTRACK=)\d+", "0"), (r"(TRACK_MUTE_MASK=)\d+", "0"),
                         (r"(TRACK_SOLO_MASK=)\d+", "0"), (r"(TEMPOx24=)\d+", str(tempo))):
            raw = re.sub(pat, r"\g<1>" + val, raw, count=1)
        path.write_bytes(raw.encode("latin1"))
    return dest


MEMRE = re.compile(r"\[\s*([\d.]+)\] \[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|0) \((\d)\) at pc (0x[0-9a-f]+) in (\S+)\s+i=(\d+)")


def parse(text):
    return [dict(sample=float(m[1]), addr=int(m[2], 16), val=int(m[3], 16), pc=int(m[5], 16), i=int(m[7]))
            for m in MEMRE.finditer(text)]


def press(at, hold=80, track=0):
    k = 0x10 + track
    return [(at, f"key {k:#x} down"), (at + 40, f"key {REC_AB:#x} down"),
            (at + 40 + hold, f"key {REC_AB:#x} up"), (at + 80 + hold, f"key {k:#x} up")]


def ptn(at, slot):
    return [(at, f"key {PTN:#x} down"), (at + 40, f"key {slot:#x} down"),
            (at + 80, f"key {slot:#x} up"), (at + 120, f"key {PTN:#x} up")]


class Run:
    """One fixture, one load, one forked scenario per (name: events, end ms, extra args)."""

    def __init__(self, image, pdir, tag, scen):
        d = OUT / tag
        d.mkdir(parents=True, exist_ok=True)
        card = d / "card.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(pdir), "OCTABAM", "FIX",
                            "--tree", str(d / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_qrec_tlen: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        args = []
        for name, (ev, end, more) in scen.items():
            sp = d / f"{name}.script"
            lines = [(500, "key 0x28 down"), (540, "key 0x28 up")] + sorted(ev) + [(end, "quit")]
            sp.write_text("".join(f"{ms} {l}\n" for ms, l in lines))
            args += ["--scenario", f"{d / name}.log --live-script {sp} " + " ".join(more)]
        cmd = [EMU, "--image", image, "--card", card, "--set", "OCTABAM", "--project", "FIX", "--load-ms", "90000",
               "--watch-mem", f"{ARM:#x},32;{REC:#x},32;{CLS:#x},32;{LIMIT:#x},32;{PATTERN:#x},1"] + args
        with open(d / "load.log", "w") as f:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode:
            sys.exit(f"verify_qrec_tlen: ot_emu exit {r.returncode} -- {d / 'load.log'}")
        self.res = {}
        for name in scen:
            text = (d / f"{name}.log").read_text(errors="replace")
            if "ended on quit" not in text:
                sys.exit(f"verify_qrec_tlen: {tag}/{name}: the live script did not run to its quit -- {d / name}.log")
            self.res[name] = (text, parse(text))

    def take(self, name):
        """(staged, arms of T1, the expected arm, REC writes of T1, LIMIT writes of T1, pattern writes)."""
        text, mem = self.res[name]
        staged = [w for w in mem if w["addr"] == CLS and w["val"]]
        a1 = [w for w in mem if w["addr"] == ARM]
        ref = [w for w in mem if w["addr"] == ARM + 4]
        exp = next((w["val"] for w in ref if staged and w["i"] > staged[0]["i"]), None)
        # Ambiguous: staged from 600 samples before a loop point's arm (the comparator fires ~114
        # before it) to one master step after it (a late fire of that loop start is still to come).
        if staged and any(-2757 < w["sample"] - staged[0]["sample"] < 600 for w in ref):
            sys.exit(f"verify_qrec_tlen: {name}: the press staged beside a loop point "
                     f"({staged[0]['sample']:.0f}): the fixture cannot tell which loop is expected -- move the press")
        recs = [w for w in mem if w["addr"] == REC and w["val"]]
        lim = [w["val"] for w in mem if w["addr"] == LIMIT]
        pats = [w["val"] for w in mem if w["addr"] == PATTERN]
        return staged, [w["val"] for w in a1], exp, recs, lim, [w["val"] for w in ref], pats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX", "qrec-tlen"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    if "QREC TLEN" not in registry.remix(a.remix).modules:
        print(f"  [ -- ] verify_qrec_tlen: {a.remix} carries no QREC TLEN"); return 0
    project = a.project
    if not project and pathlib.Path("~/.octabam_project").expanduser().is_file():
        project = pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
    if not project:
        print("  [SKIP] verify_qrec_tlen: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)"); return 0
    if not EMU.is_file() or not STOCK.is_file():
        print("  [SKIP] verify_qrec_tlen: no port binary (make emu-cf) or no stock image (make os && make recon)"); return 0
    pdir = pathlib.Path(project).expanduser()
    if not (pdir / "project.work").is_file():
        sys.exit(f"verify_qrec_tlen: {pdir} is not a project")
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.only.split(",")))

    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_qrec_tlen: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    img = image.read_bytes()
    word = lambda addr: int.from_bytes(img[addr - BASE:addr - BASE + 4], "big")

    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    clean = OUT / "clean"
    if not clean.is_dir():
        subprocess.run([str(PY), str(ROOT / "tools/hw/ot_project.py"), "clean", str(pdir), str(clean)],
                       cwd=ROOT, check=True, capture_output=True)
    want = lambda c: not only or c in only
    poke = lambda q: ["--poke", f"{QREC_LIVE:#x}={q & 0xff:#x}"]
    fmt = word(0x400d3d9a)
    check(f"image: QREC count 19 (0x400d3d6a = {word(0x400d3d6a)}), formatter word -> the cave ({fmt:#x})",
          word(0x400d3d6a) == 19 and fmt != 0x4003b150)

    def on_loop(tag, name, run, *, comparator=True):
        staged, a1, exp, recs, _, ref, _ = run.take(name)
        ok = bool(staged) and exp is not None and a1[:1] == [exp] and len(a1) == 1
        check(f"{tag}: T1 armed at {[hex(v) for v in a1]}, the next loop point {exp and hex(exp)} "
              f"(class {staged[0]['val']:#x} staged)" if staged else f"{tag}: nothing staged", ok)
        if comparator:
            check(f"{tag}: the start came through the comparator (REC writes "
                  f"{[(hex(w['val']), hex(w['pc'])) for w in recs]})", bool(recs) and recs[0]["pc"] in COMPARATOR)
        return staged, a1, exp, recs, ref

    # ---- pt256 / inf: the track loop, not the master's ---------------------------------------------
    for tag, mlen in (("pt256", 256), ("inf", 0xffff)):
        if not want(tag):
            continue
        p = make(clean, OUT / f"p_{tag}", pertrack=True, mlen=mlen, mscale=X1, tlen=64, tscale=X1, qrec=17)
        end = 18500 if mlen == 256 else 9500
        run = Run(image, p, tag, {"tlen": (press(2000), 9500, [])})
        on_loop(tag, "tlen", run)
        ctl = Run(STOCK, p, f"{tag}_stock", {"plen": (press(2000), end, poke(0))})
        staged, a1, exp, _, _, ref, _ = ctl.take("plen")
        if mlen == 256:
            loop = round(256 * 6 * TICK_SAMPLES_240)
            check(f"{tag} control, stock QREC PLEN: armed at {[hex(v) for v in a1]}, the master's 256-step loop "
                  f"(T2 {[hex(v) for v in ref]}), not the next track loop {exp and hex(exp)}",
                  len(a1) == 1 and a1[0] != exp and a1[0] in ref and (a1[0] - ref[0]) % loop == 0)
        else:
            check(f"{tag} control, stock QREC PLEN at master INF: never armed ({[hex(v) for v in a1]}) "
                  f"while T2 looped {len(ref)} times", not a1 and len(ref) >= 2)

    # ---- normal: identical to stock PLEN, subframe included -----------------------------------------
    if want("normal"):
        p = make(clean, OUT / "p_normal", pertrack=False, mlen=64, mscale=X1, tlen=64, tscale=X1, qrec=17, tempo=3072)
        run = Run(image, p, "normal", {"tlen": (press(2000), 9500, [])})
        _, a1, _, recs, _ = on_loop("normal", "tlen", run)
        ctl = Run(STOCK, p, "normal_stock", {"plen": (press(2000), 9500, poke(0))})
        _, s1, _, srecs, _, _, _ = ctl.take("plen")
        check(f"normal: TLEN == stock PLEN, arm {[hex(v) for v in a1]} vs {[hex(v) for v in s1]}, "
              f"command {[hex(w['val']) for w in recs]} vs {[hex(w['val']) for w in srecs]} (low nibble: the subframe)",
              a1 == s1 and [w["val"] for w in recs] == [w["val"] for w in srecs] and recs and recs[0]["val"] & 0xf)

    # ---- slow: the master's restart of a slower track -----------------------------------------------
    if want("slow"):
        p = make(clean, OUT / "p_slow", pertrack=True, mlen=16, mscale=X1, tlen=32, tscale=X18, qrec=17)
        run = Run(image, p, "slow", {"tlen": (press(1200), 4500, []), "after": (press(1740), 4500, [])})
        _, a1, exp, _, ref = on_loop("slow", "tlen", run)
        on_loop("slow/after a restart", "after", run)
        period = round(16 * 6 * TICK_SAMPLES_240)
        check(f"slow: T2's loop points are the master's restarts, {period} apart ({[hex(v) for v in ref]})",
              len(ref) >= 3 and all(abs(b - a - period) <= 1 for a, b in zip(ref, ref[1:])))

    # ---- mixed / fast: a loop start between master steps fires at the next one -------------------
    def late_case(tag, tlen, tscale, presses):
        tt, mt = TICKS[tscale], TICKS[X1]
        loop = tlen * tt
        p = make(clean, OUT / f"p_{tag}", pertrack=True, mlen=0xffff, mscale=X1, tlen=tlen, tscale=tscale, qrec=17)
        scen = {f"k{k}": (press(at), at + 2 * loop * TICK_SAMPLES_240 / 44.1 + 500, []) for k, at in presses}
        run = Run(image, p, tag, scen)
        for k, _ in presses:
            staged, a1, exp, recs, _, ref, _ = run.take(f"k{k}")
            n = next((j for j, v in enumerate(ref) if v == exp), None)
            late = (-(loop * n)) % mt if n is not None else None
            want_at = exp + late * TICK_SAMPLES_240 if late is not None else None
            got = a1[0] - exp if a1 and exp is not None else None
            check(f"{tag} k{k}: T1 armed {got} samples after loop start {n} (tick {loop * (n or 0)}); the first master "
                  f"step at or after it is {late} ticks = {late is not None and late * TICK_SAMPLES_240:.1f} samples later",
                  got is not None and want_at is not None and abs(a1[0] - want_at) <= 1 and len(a1) == 1
                  and recs and recs[0]["pc"] in COMPARATOR)

    if want("mixed"):                        # 3/4X, 16 steps = 128 ticks over 1X: 4, 2, 0 ticks late
        late_case("mixed", 16, X34, [(1, 900), (2, 2233), (3, 3566)])
    if want("fast"):                         # 2X: 16 steps = 48 ticks (on the grid), 15 = 45 (3 ticks late on odd loops)
        late_case("fast", 16, 0, [(1, 900)])
        late_case("fast15", 15, 0, [(1, 900), (2, 1720)])

    # ---- chg: a pattern change queued while waiting -------------------------------------------------
    if want("chg"):
        p = make(clean, OUT / "p_chg", pertrack=True, mlen=256, mscale=X1, tlen=48, tscale=X1, qrec=17, chg=8)
        step = 62.5
        scen = {"change": (press(540 + 50 * step) + ptn(540 + 54 * step, 0x01), 540 + 110 * step, []),
                "stay": (press(540 + 50 * step), 540 + 110 * step, [])}
        run = Run(image, p, "chg", scen)
        _, a1, exp, _, ref = on_loop("chg/change", "change", run)
        pats = run.take("change")[6]
        _, b1, bexp, _, bref = on_loop("chg/stay", "stay", run)
        loop48 = round(48 * 6 * TICK_SAMPLES_240)
        check(f"chg: the change (pattern writes {pats}) moved the take ahead of T1's own wrap: "
              f"{a1 and hex(a1[0])} < {b1 and hex(b1[0])}, the stay take on a 48-step loop point",
              1 in pats and a1 and b1 and a1[0] < b1[0] and (b1[0] - bref[0]) % loop48 == 0)

    # ---- one2 / hold ---------------------------------------------------------------------------------
    for tag, trig, hold in (("one2", 1, 80), ("hold", 2, 4000)):
        if not want(tag):
            continue
        p = make(clean, OUT / f"p_{tag}", pertrack=True, mlen=256, mscale=X1, tlen=64, tscale=X1, qrec=17, trig=trig)
        run = Run(image, p, tag, {"tlen": (press(2000, hold=hold), 9500, [])})
        on_loop(tag, "tlen", run)

    # ---- e2e: TLEN + RLEN PLEN + TRIG ONE = one loop, once -------------------------------------------
    if want("e2e") and "RLEN PLEN" not in registry.remix(a.remix).modules:
        print(f"  [ -- ] e2e: {a.remix} carries no RLEN PLEN")
    elif want("e2e"):
        p = make(clean, OUT / "p_e2e", pertrack=True, mlen=256, mscale=X1, tlen=48, tscale=X12, qrec=17, rlen=65)
        run = Run(image, p, "e2e", {"tlen": (press(2000), 14500, [])})
        _, a1, exp, _, ref = on_loop("e2e", "tlen", run)
        lim = run.take("tlen")[4]
        loop = round(48 * 12 * TICK_SAMPLES_240)
        check(f"e2e: RLEN PLEN ended the take after one loop (LIMIT {lim}, a loop is {loop}), armed once "
              f"while T2 looped {len(ref)} times", loop in lim and len(a1) == 1 and len(ref) >= 3)

    # ---- fmt: the formatter under the port -----------------------------------------------------------
    if want("fmt"):
        buf = 0x400d7b00
        p = make(clean, OUT / "p_fmt", pertrack=True, mlen=64, mscale=X1, tlen=64, tscale=X1, qrec=17)
        d = OUT / "fmt"; d.mkdir(exist_ok=True)
        card = d / "card.img"
        subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(p), "OCTABAM", "FIX",
                        "--tree", str(d / "tree"), "--out", str(card)], cwd=ROOT, check=True, capture_output=True)
        got = {}
        for v in (17, 12, -1):
            cmd = [EMU, "--image", image, "--card", card, "--set", "OCTABAM", "--project", "FIX", "--load-ms", "90000",
                   "--sequencer", "--frames", "1", "--step", f"-:call:{fmt:#x},{buf:#x},{v & 0xffffffff:#x}",
                   "--mem-dump", f"{buf:#x},16={d / f'{v}.bin'}"]
            subprocess.run(list(map(str, cmd)), cwd=ROOT, capture_output=True)
            got[v] = (d / f"{v}.bin").read_bytes().split(b"\0")[0].decode("latin1") if (d / f"{v}.bin").is_file() else None
        check(f"fmt: 17 -> {got[17]!r}, 12 -> {got[12]!r}, -1 -> {got[-1]!r}",
              got[17] == "TLEN" and got[12] == "64" and got[-1] == "OFF")

    print(f"verify_qrec_tlen: {'ok' if not fails else 'FAILED'} ({fails} failure(s)) -- {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
