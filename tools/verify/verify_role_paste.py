#!/usr/bin/env python3
"""ROLE PASTE under the port: an FX2 page paste or a track paste keeps the
destination track's bus role, and only the sends (DEL, REV) cross.

    python3 tools/verify/verify_role_paste.py REMIX --project DIR [--keep]

Builds the remix twice -- as selected and a CONTROL without ROLE PASTE
(OCTABAM_NO_ROLE_PASTE=1) -- stages the project once and forks one panel
script per case from one load each (`--scenario`): NO (the load dialog),
the source track, FX2 (the page), two knob turns (enc 0 +17, enc 1 +29, so
the copied sends differ from every destination's), FX2 + COPY, the
destination track, FX2 + PASTE. A track paste case does the same with REC
(GRID REC), FUNC + COPY and FUNC + PASTE. A dump at the end reads, for
every track: the working part's FX2 id and both FX2 pages, the SRAM
mirror's copy, the live ids the DSP is handed (0x80000ec4/ecc), the
engine's page lanes (0x80000828/0x80000848 + 72 t), and the clipboard.

  control  T1 -> T2 (page paste, and track paste) gives T2 BusDelay's id:
           the bug (the page reads like SEND's, the server is a dry pass)
  fixed    for each pair: the destination's id is its role (T1 BusDelay,
           T5 BusVerb, T8 RETURNS, else SEND) in the part, the mirror and the
           live id; its page is the expected one (below) in the part, the
           mirror and the engine lane; the whole part == its mirror after a
           page paste (Octakit's own check; after a track paste the gap is
           the control's, stock's); every other track is as the baseline
           left it; the clipboard is back as copied; the paste's popup was
           shown; no `illegal` halt (Octakit's checks)
  expected page   source id == role: the source's whole page (stock's
           paste); else the destination's own page (its role's descriptor
           defaults if it held another id: T2 given RETURNS through its
           chooser first) with slots 0/1 the source's when both ends carry
           sends (BusDelay, BusVerb, SEND)
  also     FX2 + PASTE twice (the second press is stock's undo: T2 back to
           its own page and id); T2's FX1 page pasted on its FX2 (FX1 and
           FX2 share the clipboard tag; T2 stays SEND); AMP page CLEAR,
           COPY, PASTE T1 -> T2 (no halt, the paste untouched); and T1's
           FX2 page pasted on T2's FX1, REPORTED (FX1 is left stock)
  DSP      both images with the DSP emulated (--dsp): core 1 enters
           BusDelay's code start once at load; the control's T1 -> T2 paste
           enters it once more, the fixed image's never

What this cannot see: the DSP's per-frame dispatch of each slot (the entry
counted is BusDelay's record start, one entry per load -- read as its
init), the panel's redraw, and the whole-part routes (part, Kit, pattern +
kit paste: modules/role-paste/README.md). SKIPs without a project, the
port, or ROLE PASTE in the remix.
"""
import argparse, os, pathlib, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "hw"))
from remix import registry  # noqa: E402
import ot_project  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
MESSAGE = 0x4005A2B8
TEXTS = {0x400B48C2: "CLEAR PAGE", 0x400B48CD: "PASTE PAGE", 0x400B48D8: "COPY PAGE", 0x400B48B8: "UNDO",
         0x400B49AB: "PASTE TRACK", 0x400B49A0: "UNDO TRACK", 0x400B4BA6: "COPY TRACK"}
KEY = {"NO": 0x32, "AMP": 0x23, "FX1": 0x25, "FX2": 0x26, "COPY": 0x29, "CLEAR": 0x28, "PASTE": 0x27, "REC": 0x29,
       "FUNC": 0x2D, "DOWN": 0x20, "YES": 0x31}
BANKPTR, BANK = 0x46C82456, 0x400E21E0             # the bank blob (its pointer is dumped and checked)
WORK, MIRROR, PARTSZ = BANK + 0x8ED80, 0x100A4ECE, 0x18B2
LIVE, LANES, CLIP, TAG = 0x80000EC4, 0x80000810, 0x460C8122, 0x460D0FFA
FX2_IDS = 0x400D5FDC                                # id -> descriptor P (build_bus.py FX2_IDS)
DEL, REV = 17, 29                                   # the source's knob turns


def keys(t, *steps):
    """Panel lines from t: a 1-tuple presses a key, a 2-tuple holds the first
    and presses the second, ("enc", n, d) turns an encoder."""
    lines = []
    for step in steps:
        if step[0] == "enc":
            lines.append(f"{t} enc {step[1]} {step[2]}")
        elif len(step) == 1:
            k = KEY[step[0]] if isinstance(step[0], str) else step[0]
            lines += [f"{t} key {k:#x} down", f"{t + 20} key {k:#x} up"]
        else:
            h, p = (KEY[x] if isinstance(x, str) else x for x in step)
            lines += [f"{t} key {h:#x} down", f"{t + 100} key {p:#x} down",
                      f"{t + 150} key {p:#x} up", f"{t + 250} key {h:#x} up"]
        t += 400
    return lines, t


def trk(n):
    return (0x10 + n - 1,)


def case_script(src, dst, page_src="FX2", page_dst="FX2", twice=False, pre=()):
    steps = [("NO",), *pre, trk(src), (page_src,), ("enc", 0, DEL), ("enc", 1, REV), (page_src, "COPY"),
             trk(dst), (page_dst,), (page_dst, "PASTE")]
    if twice:
        steps.append((page_dst, "PASTE"))
    lines, t = keys(300, *steps)
    return "\n".join(lines + [f"{t + 1000} quit"]) + "\n"


def track_script(src, dst):
    """GRID REC (REC), the source, its FX2 knobs turned, FUNC + REC (copy
    track), the destination, FUNC + STOP (paste track: stock 0x4002b988)."""
    lines, t = keys(300, ("NO",), trk(src), ("FX2",), ("enc", 0, DEL), ("enc", 1, REV), ("REC",),
                    ("FUNC", "COPY"), trk(dst), ("FUNC", "PASTE"))
    return "\n".join(lines + [f"{t + 1000} quit"]) + "\n"


def amp_script():
    lines, t = keys(300, ("NO",), trk(1), ("AMP",), ("AMP", "CLEAR"), ("AMP", "COPY"), trk(2), ("AMP", "PASTE"))
    return "\n".join(lines + [f"{t + 1000} quit"]) + "\n"


def base_script():
    lines, t = keys(300, ("NO",))
    return "\n".join(lines + [f"{t + 1000} quit"]) + "\n"


class Dump:
    """Every track's FX state from one run's dumps."""

    def __init__(self, d):
        self.bankptr = int.from_bytes(d["bankptr"][:4], "big") if len(d["bankptr"]) >= 4 else None
        self.part = d["ctx"][3] if len(d["ctx"]) >= 4 else None
        p = (self.part or 0) * PARTSZ
        w, m, lanes = d["work"], d["mirror"], d["lanes"]
        self.ok = len(w) == 4 * PARTSZ and len(m) == 4 * PARTSZ and len(lanes) == 576 and self.part is not None
        if not self.ok:
            return
        self.fx1 = list(w[p:p + 8])
        self.fx2 = list(w[p + 8:p + 16])
        self.m_fx2 = list(m[p + 8:p + 16])
        self.page = [bytes(w[p + 0x12C + 24 * t:p + 0x12C + 24 * t + 6] + w[p + 0x304 + 30 * t:p + 0x304 + 30 * t + 6])
                     for t in range(8)]
        self.m_page = [bytes(m[p + 0x12C + 24 * t:p + 0x12C + 24 * t + 6] + m[p + 0x304 + 30 * t:p + 0x304 + 30 * t + 6])
                       for t in range(8)]
        self.fx1page = [bytes(w[p + 0x126 + 24 * t:p + 0x126 + 24 * t + 6] + w[p + 0x2FE + 30 * t:p + 0x2FE + 30 * t + 6])
                        for t in range(8)]
        self.lane = [bytes(lanes[72 * t + 0x18:72 * t + 0x1E] + lanes[72 * t + 0x38:72 * t + 0x3E]) for t in range(8)]
        self.live1, self.live2 = list(d["live"][:8]), list(d["live"][8:16])
        self.clip = bytes(d["clip"][:12]) + bytes(d["clip"][18:19])
        self.tag = int.from_bytes(d["tag"][:4], "big") if len(d["tag"]) >= 4 else None
        tc = d["tclip"]                          # the track clipboard from + 0x91a
        self.tclip = (bytes(tc[0x58:0x5E] + tc[0x70:0x76]) + bytes(tc[1:2])) if len(tc) == 0x80 else b""
        self.whole_part = bytes(w[p:p + PARTSZ])
        self.whole_mirror = bytes(m[p:p + PARTSZ])


def dumps_arg(d, name):
    spec = {"bankptr": (BANKPTR, 4), "ctx": (0x100B14CC, 4), "work": (WORK, 4 * PARTSZ),
            "mirror": (MIRROR, 4 * PARTSZ), "live": (LIVE, 16), "lanes": (LANES, 576),
            "clip": (CLIP, 19), "tag": (TAG, 4), "tclip": (CLIP + 0x91A, 0x80)}
    return ";".join(f"{a:#x},{n}={d / f'{name}.{k}'}" for k, (a, n) in spec.items()), list(spec)


def run_image(image, card, work, tag, cases, norver, extra=()):
    """One load, one forked child per case: {name: (Dump, halted, shown, quit, log)}."""
    d = work / tag
    d.mkdir()
    args, kinds = [], None
    for name, text in cases.items():
        sp = d / f"{name}.script"
        sp.write_text(text)
        spec, kinds = dumps_arg(d, name)
        args += ["--scenario", f"{d / name}.log --live-script {sp} --mem-dump {spec}"]
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", "/OCTABAM", "--project", "RPS",
           "--mkii", "--rtc", "host", "--preload", f"0x3ffc={norver}", "--load-ms", "90000",
           "--watch-pc", f"{MESSAGE:#x}", *extra] + args
    with open(d / "load.log", "w") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_role_paste: ot_emu exit {r.returncode} -- {d / 'load.log'}")
    res = {}
    for name in cases:
        log = (d / f"{name}.log").read_text(errors="replace") if (d / f"{name}.log").exists() else ""
        raw = {k: (d / f"{name}.{k}").read_bytes() if (d / f"{name}.{k}").exists() else b"" for k in kinds}
        halted = bool(re.search(r"unimplemented opcode 4afc", log))
        shown = [TEXTS.get(int(m.group(1), 16), m.group(1)) for m in
                 re.finditer(r"at 0x4005a2b8 .*?\[sp 0x[0-9a-f]+: 0x[0-9a-f]+ (0x[0-9a-f]+)", log)]
        res[name] = (Dump(raw), halted, shown, "ended on quit" in log, log)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    mods = registry.remix(a.remix).modules
    if "ROLE PASTE" not in mods:
        print(f"  [SKIP] verify_role_paste: {a.remix} does not carry ROLE PASTE"); return 0
    if not a.project:
        print("  [SKIP] verify_role_paste: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.exists():
        print("  [SKIP] verify_role_paste: the ColdFire port is not built (make emu-cf)"); return 0
    every = dict(registry.modules())
    ID_DELAY, ID_VERB, ID_SEND = (every[k].menu.fx2_id for k in ("DELAY SERVER", "REVERB SERVER", "SEND"))
    ID_T8 = every["RETURNS"].menu.fx2_id if "RETURNS" in mods else None
    SENDS = {ID_DELAY, ID_VERB, ID_SEND}
    by_id = {m.menu.fx2_id: m for m in every.values() if getattr(m, "menu", None)}

    work = pathlib.Path(tempfile.mkdtemp(prefix="rolepaste."))
    images = {}
    for tag, extra in (("fixed", {}), ("control", {"OCTABAM_NO_ROLE_PASTE": "1"})):
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1", BUILD=os.environ.get("BUILD", "0"), **extra)
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_role_paste: building {a.remix} ({tag}) failed:\n{(r.stdout + r.stderr)[-1200:]}")
        images[tag] = work / f"{tag}.bin"
        shutil.copy(ROOT / "out/mainos_bus.bin", images[tag])
        if tag == "fixed":
            report = r.stdout
    card = work / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(a.project), "OCTABAM", "RPS",
                        "--out", str(card), "--tree", str(work / "tree")], capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_role_paste: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    norver = work / "norver.bin"
    norver.write_bytes(STOCK.read_bytes()[0xDE648:0xDE64A])

    pairs = [(1, 2), (2, 1), (1, 5), (5, 1), (1, 8), (8, 2), (3, 2)]
    cases = {"base": base_script()}
    cases.update({f"t{s}t{d}": case_script(s, d) for s, d in pairs})
    cases["undo"] = case_script(1, 2, twice=True)
    cases["fx1on2"] = case_script(2, 2, page_src="FX1")
    cases["amp"] = amp_script()
    tpairs = [(1, 2), (2, 1), (1, 5), (3, 2)]
    cases.update({f"trk{s}{d}": track_script(s, d) for s, d in tpairs})
    # T2 given RETURNS through its chooser (FUNC + FX2, DOWN = RETURNS' row,
    # YES; HOST LOCK allows it off T8): a destination NOT on its role, so the
    # paste gives it SEND's defaults, never RETURNS' page as sends
    chooser = (trk(2), ("FUNC", "FX2"), ("DOWN",), ("YES",))
    if ID_T8 is not None:
        cases["ret_t8t2"] = case_script(8, 2, pre=chooser)
        cases["ret_t1t2"] = case_script(1, 2, pre=chooser)
    cases["fx2tofx1"] = case_script(1, 2, page_dst="FX1")
    fixed = run_image(images["fixed"], card, work, "fixed", cases, norver)
    control = run_image(images["control"], card, work, "control",
                        {"base": base_script(), "t1t2": case_script(1, 2), "trk12": track_script(1, 2)}, norver)

    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_role_paste: {label}" + (f"  ({detail})" if detail else ""))

    def role(t):
        if t == 1:
            return ID_DELAY
        if t == 5:
            return ID_VERB
        if t == 8:
            return ID_T8
        return ID_SEND

    img = images["fixed"].read_bytes()

    def rd(addr, n):
        o = addr - 0x40000400                  # the OS section's load base
        return img[o:o + n] if 0 <= o and o + n <= len(img) else None

    def defaults(i):
        """What the image stamps for id i: its descriptor's page defaults
        (FX2_IDS[i] + 0x5e / + 0x64, the bytes RIG HOSTS and the chooser
        write), the manifest's when the descriptor is not in the image."""
        ptr = rd(FX2_IDS + 4 * i, 4)
        desc = int.from_bytes(ptr, "big") if ptr else 0
        p1, p2 = (rd(desc + 0x5E, 6), rd(desc + 0x64, 6)) if desc else (None, None)
        if p1 is not None and p2 is not None:
            return bytes(p1 + p2)
        return bytes(ot_project.module_defaults(by_id[i]))

    base = fixed["base"][0]
    if not (base.ok and base.bankptr == BANK):
        print(f"  [FAIL] verify_role_paste: the baseline run gave no part dump (bank pointer "
              f"{base.bankptr if base.bankptr is None else hex(base.bankptr)}, want {BANK:#x}) -- logs in {work}")
        return 1
    check("baseline: the rig's roles are loaded (FX2 T1..T8)",
          base.fx2 == [ID_DELAY, ID_SEND, ID_SEND, ID_SEND, ID_VERB, ID_SEND, ID_SEND, ID_T8 or base.fx2[7]],
          " ".join(f"{x:02x}" for x in base.fx2))
    # the mirror is NOT checked here: Octakit's Kit staging leaves it as the
    # bank file had it until OCTAKIT MIRROR syncs it before a CLEAR/PASTE
    check("baseline: the engine lanes == the part's FX2 pages, the live ids == its FX2 ids",
          base.page == base.lane and base.fx2 == base.live2,
          f"mirror == part: {base.whole_part == base.whole_mirror} (Kit staging; synced at the paste)")

    def mismatch(x):
        return {i for i in range(PARTSZ) if x.whole_part[i] != x.whole_mirror[i]}

    cb = control["base"][0]
    c, chalt, cshown, cquit, _ = control["t1t2"]
    check("control (no ROLE PASTE): T1 -> T2 FX2 page paste gives T2 BusDelay's id (the bug)",
          c.ok and cquit and not chalt and c.fx2[1] == ID_DELAY and c.live2[1] == ID_DELAY,
          f"T2 FX2 {c.fx2[1]:#04x} live {c.live2[1]:#04x}" if c.ok else "no dump")
    c, chalt, cshown, cquit, _ = control["trk12"]
    f = fixed["trk12"][0]
    check("T1 -> T2 track paste: the part/mirror gap is the control's own (stock's), byte for byte",
          c.ok and f.ok and mismatch(c) == mismatch(f),
          f"control {sorted(hex(i) for i in mismatch(c) - mismatch(base))} new vs the baseline" if c.ok else "")
    check("control (no ROLE PASTE): T1 -> T2 track paste gives T2 BusDelay's id too",
          c.ok and cquit and not chalt and c.fx2[1] == ID_DELAY and "PASTE TRACK" in cshown,
          f"T2 FX2 {c.fx2[1]:#04x} live {c.live2[1]:#04x}, shown {cshown}" if c.ok else "no dump")
    del cb

    def expect(src_id, src_page, dst, d_id, d_page):
        r = role(dst)
        if r is None:                     # T8 without RETURNS keeps what it holds
            r = d_id
        if src_id == r:
            return r, bytes(src_page)
        page = bytearray(d_page if d_id == r else defaults(r))
        if src_id in SENDS and r in SENDS:
            page[0:2] = src_page[0:2]
        return r, bytes(page)

    def verify_pair(name, s, dst, src_fx1=False, d_id=None, track=False):
        dmp, halt, shown, quit_, _ = fixed[name]
        if not (dmp.ok and quit_):
            check(f"{name}: the run completed with a dump", False, "HALTED" if halt else "no quit/dump")
            return
        si, di = s - 1, dst - 1
        src_id = dmp.fx1[si] if src_fx1 else dmp.fx2[si]
        src_page = dmp.fx1page[si] if src_fx1 else dmp.page[si]
        want_id, want_page = expect(src_id, src_page, dst, base.fx2[di] if d_id is None else d_id, base.page[di])
        got = (dmp.fx2[di], dmp.page[di])
        # a page paste: the whole part == its mirror (Octakit's own check,
        # OCTAKIT MIRROR syncs before it); a track paste: no byte the
        # baseline had equal now differs (the Kit staging's gap stays) but
        # part + 0x2ce + 5 t, which stock's track paste writes to the part
        # alone (0x4002b7c6: 0x80 + t; the control does the same)
        mirrored = (dmp.whole_part == dmp.whole_mirror if not track else
                    mismatch(dmp) - mismatch(base) <= {0x2CE + 5 * di})
        same_everywhere = (dmp.m_fx2[di] == dmp.fx2[di] == dmp.live2[di]
                           and dmp.m_page[di] == dmp.page[di] == dmp.lane[di] and mirrored)
        others = all(dmp.fx2[t] == base.fx2[t] and (dmp.page[t] == base.page[t] or (t == si and not src_fx1))
                     for t in range(8) if t != di)
        clip = dmp.tclip if track else dmp.clip
        src_turned = src_fx1 or src_page[:2] != base.page[si][:2]   # FX1 NONE has no knobs to turn
        clip_back = clip[12:13] == bytes([src_id]) and clip[:12] == src_page
        ok = (not halt and got == (want_id, want_page) and same_everywhere and others and clip_back
              and (("PASTE TRACK" in shown) if track else shown[-2:] == ["COPY PAGE", "PASTE PAGE"]) and src_turned)
        detail = (f"T{dst} FX2 {got[0]:#04x} page {got[1].hex()} want {want_id:#04x} {want_page.hex()}"
                  + ("" if same_everywhere else "; part/mirror/live/lane DIFFER")
                  + ("" if others else "; another track changed")
                  + ("" if clip_back else f"; clipboard not back ({dmp.clip.hex()})")
                  + ("" if src_turned else "; the source's knobs did not turn")
                  + (f"; shown {shown}" if track or shown[-2:] != ["COPY PAGE", "PASTE PAGE"] else "")
                  + ("; HALTED" if halt else ""))
        label = (f"T{s} -> T{dst} TRACK paste: FX2 role, " if track else
                 f"T{s} {'FX1' if src_fx1 else 'FX2'} -> T{dst}{' (RETURNS)' if d_id else ''} FX2: role, ") + (
            "the source's whole page (same role)" if src_id == want_id else
            ("DEL/REV crossed, the rest " + ("its role's defaults" if d_id else "its own")) if src_id in SENDS and want_id in SENDS
            else ("its role's defaults" if d_id else "its own page kept"))
        check(label, ok, detail)

    for s, dd in pairs:
        verify_pair(f"t{s}t{dd}", s, dd)
    verify_pair("fx1on2", 2, 2, src_fx1=True)
    for s_, d_ in tpairs:
        verify_pair(f"trk{s_}{d_}", s_, d_, track=True)
    if ID_T8 is not None:
        verify_pair("ret_t8t2", 8, 2, d_id=ID_T8)
        verify_pair("ret_t1t2", 1, 2, d_id=ID_T8)

    dmp, halt, shown, quit_, _ = fixed["undo"]
    check("T1 -> T2 FX2 + PASTE twice: the second press is stock's undo (T2's own id and page back)",
          dmp.ok and quit_ and not halt and dmp.fx2[1] == base.fx2[1] and dmp.page[1] == base.page[1]
          and dmp.m_page[1] == dmp.page[1] and dmp.live2[1] == base.fx2[1],
          (f"T2 {dmp.fx2[1]:#04x} {dmp.page[1].hex()} shown {shown}" if dmp.ok else "no dump")
          + ("; HALTED" if halt else ""))

    dmp, halt, shown, quit_, _ = fixed["amp"]
    check("AMP page: CLEAR, COPY, PASTE T1 -> T2 complete without a halt; FX2 untouched",
          dmp.ok and quit_ and not halt and shown == ["CLEAR PAGE", "COPY PAGE", "PASTE PAGE"]
          and dmp.fx2 == base.fx2 and dmp.page == base.page,
          f"shown {shown}" + ("; HALTED" if halt else ""))

    dmp, halt, shown, quit_, _ = fixed["fx2tofx1"]
    print(f"  [INFO] verify_role_paste: T1 FX2 page pasted on T2's FX1 (FX1 left stock): "
          + (f"T2 FX1 {dmp.fx1[1]:#04x} live {dmp.live1[1]:#04x}, FX2 {dmp.fx2[1]:#04x}"
             f"{'; HALTED' if halt else ''}" if dmp.ok else "no dump"))
    # The DSP side, once: both images with the DSP cores emulated (--dsp),
    # a PC watch on core 1 (payload B: tracks 1-4) at the first word of
    # BusDelay's code. It is entered once over a whole load (T1's slot, at
    # the load), so it is not the per-frame proc; a second entry after a
    # paste is the DSP setting BusDelay up on another slot (inferred: init).
    m = re.search(r"-- payload B --.*?\n  DELAY SERVER  P:(0x[0-9a-f]+)", report, re.S)
    if m:
        watch = f"1:{int(m.group(1), 16):x}"

        def arrivals(log):
            body = log.split("dsp pcwatch:")[-1] if "dsp pcwatch:" in log else ""
            return sum(1 for ln in body.splitlines()[1:] if re.match(r"\s+\d+ [0-9a-f]{6}:", ln))
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(2) as ex:
            dsp = {tag: ex.submit(run_image, images[tag], card, work, f"dsp_{tag}",
                                  {"base": base_script(), "t1t2": case_script(1, 2)}, norver,
                                  ("--dsp", "--dsp-pcwatch", watch)) for tag in ("fixed", "control")}
            dsp = {k: f.result() for k, f in dsp.items()}
        n = {(tag, c): arrivals(dsp[tag][c][4]) for tag in dsp for c in ("base", "t1t2")}
        check(f"DSP (core 1, BusDelay's code at P:{watch[2:]}): T1 -> T2 FX2 paste enters it again "
              f"in the control, never with ROLE PASTE",
              n["control", "base"] >= 1 and n["control", "t1t2"] == n["control", "base"] + 1
              and n["fixed", "t1t2"] == n["fixed", "base"] == n["control", "base"],
              f"entries: control {n['control', 'base']} at load, {n['control', 't1t2']} after the paste; "
              f"fixed {n['fixed', 'base']}, {n['fixed', 't1t2']}")
    else:
        check("DSP: BusDelay's placement on payload B found in the build report", False)
    if fails or a.keep:
        print(f"  verify_role_paste: logs in {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
