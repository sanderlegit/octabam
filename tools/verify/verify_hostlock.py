#!/usr/bin/env python3
"""HOST LOCK under the port: on T1 and T5 the FX2 chooser's YES does what NO
does; on T8 (with RETURNS) it selects RETURNS' row only; elsewhere it selects.

    python3 tools/verify/verify_hostlock.py REMIX --project DIR

Builds the remix, stages the project's card and runs one panel script per
case: NO (the load dialog), the track key, FUNC + FX2 (the chooser), UP or
DOWN, YES. The rig's FX2 chooser has two rows, SEND then RETURNS, so UP
lands on SEND and DOWN on RETURNS. PC watches count the chooser's two
handlers: the select (0x40052474, stock's FX2 machine select; Octakit's
wrapper sits behind it) and NO (0x4003d440); a dump of the working part's
FX2 row says what each track ends on.

  T1, T5 DOWN   NO ran, the select never did, the server's id stays
  T8 UP         (RETURNS) NO ran: SEND's row is refused, T8 stays RETURNS
  T8 DOWN       (RETURNS) the select ran: T8 is RETURNS
  T2 DOWN       the select ran, NO did not
  every         no `illegal` halt (Octakit's fatal checks)

What this cannot see: the panel's redraw, and a project whose T1/T5 FX2 is
already something else (the lock keeps whatever is there; `ot_project.py
host` puts the servers back). SKIPs without a project or the port.
"""
import argparse, os, pathlib, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
SELECT, NO = 0x40052474, 0x4003D440
KEY = {"NO": 0x32, "FUNC": 0x2D, "FX2": 0x26, "UP": 0x33, "DOWN": 0x20, "YES": 0x31}
FX2_ROW = 0x40170F68                                 # the working part's FX2 ids, T1..T8


def script(track, nav="DOWN"):
    t, lines = 300, []
    for k in ("NO", 0x10 + track - 1):
        code = KEY.get(k, k)
        lines += [f"{t} key {code:#x} down", f"{t + 20} key {code:#x} up"]; t += 300
    lines += [f"{t} key {KEY['FUNC']:#x} down", f"{t + 100} key {KEY['FX2']:#x} down",
              f"{t + 150} key {KEY['FX2']:#x} up", f"{t + 250} key {KEY['FUNC']:#x} up"]
    t += 500
    for k in (nav, "YES"):
        lines += [f"{t} key {KEY[k]:#x} down", f"{t + 20} key {KEY[k]:#x} up"]; t += 300
    return "\n".join(lines + [f"{t + 1000} quit"]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    if "HOST LOCK" not in registry.remix(a.remix).modules:
        print(f"  [SKIP] verify_hostlock: {a.remix} does not carry HOST LOCK"); return 0
    if not a.project:
        print("  [SKIP] verify_hostlock: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.exists():
        print("  [SKIP] verify_hostlock: the ColdFire port is not built (make emu-cf)"); return 0
    work = pathlib.Path(tempfile.mkdtemp(prefix="hostlock."))
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1", BUILD=os.environ.get("BUILD", "0"))
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_hostlock: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1200:]}")
    image = work / "image.bin"
    shutil.copy(ROOT / "out/mainos_bus.bin", image)
    card = work / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(a.project), "OCTABAM", "HLK",
                        "--out", str(card), "--tree", str(work / "tree")], capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_hostlock: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    norver = work / "norver.bin"
    norver.write_bytes(STOCK.read_bytes()[0xDE648:0xDE64A])

    t8 = registry.remix(a.remix).modules
    rid = registry.by_key("RETURNS").menu.fx2_id if "RETURNS" in t8 else None
    # (track, key before YES, the rule): "no" -> NO ran and the id is the
    # baseline's; "sel" -> the select ran (and, on T8, the id is RETURNS')
    cases = [(1, "DOWN", "no"), (5, "DOWN", "no"), (2, "DOWN", "sel")]
    cases += [(8, "UP", "no"), (8, "DOWN", "sel")] if rid is not None else [(8, "DOWN", "sel")]

    def run(case):
        track, nav, _ = case
        tag = f"t{track}{nav.lower()}" if track else "base"
        scr = work / f"{tag}.txt"
        scr.write_text(script(track, nav) if track else "300 key 0x32 down\n320 key 0x32 up\n1300 quit\n")
        dump = work / f"{tag}.fx2"
        out = subprocess.run([str(EMU), "--image", str(image), "--card", str(card), "--set", "/OCTABAM",
                              "--project", "HLK", "--mkii", "--rtc", "host", "--preload", f"0x3ffc={norver}",
                              "--load-ms", "90000", "--live-script", str(scr),
                              "--watch-pc", f"{SELECT:#x},{NO:#x}", "--mem-dump", f"{FX2_ROW:#x},8={dump}"],
                             capture_output=True, text=True, cwd=ROOT).stdout
        (work / f"{tag}.log").write_text(out)
        ids = dump.read_bytes() if dump.exists() else b""
        return (len(re.findall(rf"at {SELECT:#x}\b", out)), len(re.findall(rf"at {NO:#x}\b", out)),
                bool(re.search(r"unimplemented opcode 4afc", out)), ids)

    runs = [(0, "", "")] + cases
    with ThreadPoolExecutor(len(runs)) as ex:
        res = dict(zip(runs, ex.map(run, runs)))
    base = res[runs[0]][3]
    fails = 0
    if len(base) != 8:
        print("  [FAIL] verify_hostlock: no FX2 row from the baseline run"); fails += 1
    for case in cases:
        track, nav, rule = case
        sel, no, halt, ids = res[case]
        got = ids[track - 1] if len(ids) == 8 else None
        if rule == "no":
            want_id = base[track - 1] if len(base) == 8 else None
            ok = not halt and no >= 1 and sel == 0 and got == want_id
            want = "YES answered as NO, FX2 unchanged"
        else:
            want_id = rid if track == 8 and rid is not None else None
            ok = not halt and sel >= 1 and no == 0 and (want_id is None or got == want_id)
            want = "YES selects" + (" RETURNS" if want_id is not None else "")
        fails += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_hostlock: T{track} {nav}+YES {want}  "
              f"(select {sel}, NO {no}, FX2 {got if got is None else hex(got)}"
              f"{f' want {want_id:#x}' if want_id is not None and got != want_id else ''}{', HALTED' if halt else ''})")
    if fails:
        print(f"  verify_hostlock: logs in {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
