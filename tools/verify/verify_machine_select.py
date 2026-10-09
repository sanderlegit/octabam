#!/usr/bin/env python3
"""A track's machine chooser under the port: FUNC + SRC, DOWN, YES on T2 and
T3 reaches stock's machine select and nothing halts.

    python3 tools/verify/verify_machine_select.py REMIX --project DIR

Octakit's wrapper behind the chooser's YES (gk_stock_machine_ui_callback_a)
requires the key dispatch's own return, 0x40031922; any detour on the
dispatch at 0x4003191c that calls the handler from elsewhere halts every
machine change (`illegal` at gk_machine_transition_entry_validate_report_
fatal; OCTAKIT MIRROR did, 9 Oct 2026). A PC watch counts the stock select
(0x4005a5a8) her wrapper calls once it has checked.

What this cannot see: which machine the track ends on, and the other
chooser kinds her wrapper validates (the commit and setup paths). SKIPs
without a project or the port.
"""
import argparse, os, pathlib, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
SELECT = 0x4005A5A8
KEY = {"NO": 0x32, "FUNC": 0x2D, "SRC": 0x22, "DOWN": 0x20, "YES": 0x31}
TRACKS = (2, 3)


def script(track):
    t, lines = 300, []
    for k in ("NO", 0x10 + track - 1):
        code = KEY.get(k, k)
        lines += [f"{t} key {code:#x} down", f"{t + 20} key {code:#x} up"]; t += 300
    lines += [f"{t} key {KEY['FUNC']:#x} down", f"{t + 100} key {KEY['SRC']:#x} down",
              f"{t + 150} key {KEY['SRC']:#x} up", f"{t + 250} key {KEY['FUNC']:#x} up"]
    t += 500
    for k in ("DOWN", "YES"):
        lines += [f"{t} key {KEY[k]:#x} down", f"{t + 20} key {KEY[k]:#x} up"]; t += 300
    return "\n".join(lines + [f"{t + 1000} quit"]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    if "OCTAKIT" not in registry.remix(a.remix).modules:
        print(f"  [SKIP] verify_machine_select: {a.remix} does not carry OCTAKIT"); return 0
    if not a.project:
        print("  [SKIP] verify_machine_select: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.exists():
        print("  [SKIP] verify_machine_select: the ColdFire port is not built (make emu-cf)"); return 0
    work = pathlib.Path(tempfile.mkdtemp(prefix="machsel."))
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1", BUILD=os.environ.get("BUILD", "0"))
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_machine_select: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1200:]}")
    image = work / "image.bin"
    shutil.copy(ROOT / "out/mainos_bus.bin", image)
    card = work / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(a.project), "OCTABAM", "MSL",
                        "--out", str(card), "--tree", str(work / "tree")], capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_machine_select: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    norver = work / "norver.bin"
    norver.write_bytes(STOCK.read_bytes()[0xDE648:0xDE64A])

    def run(track):
        scr = work / f"t{track}.txt"
        scr.write_text(script(track))
        out = subprocess.run([str(EMU), "--image", str(image), "--card", str(card), "--set", "/OCTABAM",
                              "--project", "MSL", "--mkii", "--rtc", "host", "--preload", f"0x3ffc={norver}",
                              "--load-ms", "90000", "--live-script", str(scr),
                              "--watch-pc", f"{SELECT:#x}"],
                             capture_output=True, text=True, cwd=ROOT).stdout
        (work / f"t{track}.log").write_text(out)
        return (len(re.findall(rf"at {SELECT:#x}\b", out)),
                bool(re.search(r"unimplemented opcode 4afc", out)))

    with ThreadPoolExecutor(len(TRACKS)) as ex:
        res = dict(zip(TRACKS, ex.map(run, TRACKS)))
    fails = 0
    for track in TRACKS:
        sel, halt = res[track]
        ok = sel >= 1 and not halt
        fails += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_machine_select: T{track} YES reaches the machine select  "
              f"(select {sel}{', HALTED' if halt else ''})")
    if fails:
        print(f"  verify_machine_select: logs in {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
