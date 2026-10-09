#!/usr/bin/env python3
"""verify_slicetools -- SLICE TOOLS under the ColdFire port, driven from the panel.

    python3 tools/verify/verify_slicetools.py REMIX [--project DIR] [--only TAG,...]

An "image" gate: out/mainos_bus.bin (the remix) boots under the port with a
fixture made from a copy of a real project (OT_PROJECT, --project or
~/.octabam_project): T1 FLEX on slot 1 (a 2 s sine, FIVE slices in the
markers), pattern A01 LEN 12 in NORMAL mode, T1 trigs on steps 1 and 3, a
STRT lock 0x20 on the empty step 7, a trigless trig with a STRT lock on
step 20, T1's AUTO LINEAR byte 0 in every part. The project loads once and
each scenario forks from the loaded machine (`ot_emu --scenario`); the
keys are the panel's (AED, the SLICE page, YES for the SLICE menu, DOWN,
YES), the results are RAM dumps (the bank's records and their SRAM twins).

  base      nothing pressed: the fixture is in RAM where the unit expects it
            (and the AUTO LINEAR label reads OFF)
  tlen      CREATE SLICE GRID > TLEN SLICES (row 12), NO on ZERO-CROSS ALIGN?
  grid12    the same with stock's 12 SLICES (the control): the slice record
            must be TLEN's byte for byte, and 12 slices of the trim range
  tlenpt    PER TRACK, T1 LEN 6 (poked after the load): TLEN SLICES ...
  grid6     ... equals stock's 6 SLICES
  linear    SLICE menu > CREATE LINEAR > YES: trigs exactly on 1..12, STRT
            2*((s-1) mod 5) on each, every other lock byte of the track 0xff
            (step 7's and step 20's gone), the trigless mask clear, SLIC on,
            AUTO LINEAR on; bank and SRAM twin alike
  auto      AUTO LINEAR on from the menu, then in grid recording: trig 9 and
            11 (empty) get STRT 6 and 0 (wrap at 5), step 18 (page 2, the
            pattern's LEN poked to 32) gets 4, trig 7 (empty, locked
            0x20) keeps 0x20, trig 1 (a trig: the removal) gets nothing,
            FUNC+trig 10 (a trigless trig) gets nothing, MIDI mode + trig 4
            leaves the audio track alone
  autooff   the same keys with AUTO LINEAR off: no lock anywhere (the control)
  label     AUTO LINEAR on, the menu opened again: the row reads
            AUTO LINEAR:ON (the menu draws the label it is handed)
  menu8     the same from the 8-row menu (no slice selected: the slot's
            slice count poked to 0, since opening the editor selects slice 0
            of a sliced sample): AUTO LINEAR is its row 7
  linear0   CREATE LINEAR with no slices: refused (NO SLICES), the track and
            the flag untouched
  thru      AUTO LINEAR on, then T1 to THRU and back to FLEX through SELECT
            MACHINE TYPE, the audio editor opened while THRU: every write to
            the flag byte (bank and SRAM) is logged; the flag must still be 1
  saveproj  CREATE LINEAR, then (with OCTAKIT) SAVE KIT, then PROJ > SAVE
            PROJECT; the card is written out
  reboot    a second boot from that card: the flag, the trigs and the locks
            are as saved, and the bank files on the card carry the flag

With OCTAKIT in the remix the part is her workspace Kit (her saved Kits and
workspace state are dumped by her runtime's own symbols):
  saveproj0 / reboot0  the same without SAVE KIT: a reboot stages the saved
            Kit over the part, so the flag reverts together with stock's SLIC
  kitdirty  AUTO LINEAR alone marks her workspace dirty (as her wrapper of
            stock's linear-lock writer does); her saved Kit not yet changed
  kitsave   AUTO LINEAR alone, SAVE KIT (FUNC+PART, YES, YES): the saved Kit has it
  kitquick  a named Kit, AUTO LINEAR, the quick save (FUNC+PART held, YES)
  kitreload saved as 1, toggled to 0, FUNC+CUE: 1 again
  kitload   saved as 1, LOAD KIT 2 (0), LOAD KIT 1: 1
  kitundo   set and not saved, LOAD KIT 2, LOAD KIT > UNDO KIT: 1, still dirty

What it cannot see: the screen beyond the label buffer (an LCD plane is
written per scenario for a person to look at: tools/emu/lcd_view.py), a
voice playing the slices (no DSP is run), hardware timing. SKIPs without a
project or the port, or for a remix without SLICE TOOLS.
"""
import argparse, math, os, pathlib, re, shutil, struct, subprocess, sys, wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import ot_project as otp  # noqa: E402
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/slicetools"
BASE = 0x40000400
SR, FRAMES, NSLICES, PLEN = 44100, 88200, 5, 12
SAMPLE_REL = "AUDIO/SLICETOOLS.wav"
NAME = "SLT"

# RAM (docs/firmware/PARAM_PAGES.md section 5g; modules/slice-tools/README.md)
BANKP = 0x46c82456
BANK0 = 0x400e21e0                     # bank 1's record (the pointer is checked in every scenario)
SRAM_BANK, SRAM_PART = 0x1001614e, 0x100a4ece
PART_OFF, PART_LEN, NPARTS = 0x8ed80, 0x18b2, 4
TRAC_LEN = 0x91a
FLEX_REC = 0x100b14f0
CUR = 0x100b14cc                       # track, ?, ?, part, pattern
FLAG_OFF, SLIC_OFF = 0x2cc, 0x1e0 + 1  # T1: THRU slot byte; FLEX setup slot 1 (SLIC)
K = dict(no=0x32, yes=0x31, up=0x33, down=0x20, left=0x34, right=0x21, aed=0x1e, func=0x2d,
         amp=0x23, page=0x1b, rec=0x29, midi=0x35, proj=0x1c, part=0x1d, cue=0x2a, t1=0x10, t2=0x11)


class Script:
    def __init__(self):
        self.t, self.lines = 1500, []

    def send(self, x, gap):
        self.lines.append(f"{self.t:.0f} {x}"); self.t += gap

    def tap(self, k, gap=400):
        c = K[k] if isinstance(k, str) else k
        self.send(f"key {c:#x} down", 40); self.send(f"key {c:#x} up", gap)
        return self

    def down(self, k, gap=80):
        self.send(f"key {(K[k] if isinstance(k, str) else k):#x} down", gap)

    def up(self, k, gap=300):
        self.send(f"key {(K[k] if isinstance(k, str) else k):#x} up", gap)

    def taps(self, k, n, gap=300):
        for _ in range(n):
            self.tap(k, gap)
        return self

    def wait(self, ms):
        self.send("enc 6 0", ms)

    def text(self):
        return "\n".join(self.lines + [f"{self.t + 200:.0f} quit"]) + "\n"


def start(s):
    """the date prompt; T2 then T1 points the audio editor at T1's sample"""
    s.tap("no", 600); s.tap("t2", 500); s.tap("t1", 500)


def slice_menu(s):
    s.tap("aed", 1500); s.tap("amp", 800); s.tap("yes", 1200)   # AED, SLICE page, the SLICE menu


def grid(s, row):
    """CREATE SLICE GRID (SLICE menu row 5 of 11), the popup's cursor from 4 to `row`, NO on ZERO-CROSS ALIGN?"""
    slice_menu(s); s.taps("down", 5); s.tap("yes", 1200)
    if row >= 4:
        s.taps("down", row - 4)
    else:
        s.taps("up", 4 - row)
    s.tap("yes", 1200); s.tap("no", 6000)


def make_wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        fr = bytearray()
        for n in range(FRAMES):
            v = int(round(12000 * math.sin(2 * math.pi * 220 * n / SR)))
            fr += struct.pack("<hh", v, v)
        w.writeframes(bytes(fr))


def build_fixture(src, dest):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() in (".work", ".strd"):
            shutil.copy2(f, dest / f.name)
    for suffix in ("work", "strd"):
        pw = dest / f"project.{suffix}"
        if not pw.is_file():
            continue
        raw = pw.read_bytes()
        raw = re.sub(rb"\[SAMPLE\]\r\nTYPE=FLEX\r\nSLOT=001\r\n.*?\[/SAMPLE\]\r\n\r\n", b"", raw, flags=re.S)
        block = ("[SAMPLE]\r\nTYPE=FLEX\r\nSLOT=001\r\nPATH=../" + SAMPLE_REL + "\r\n"
                 "TRIM_BARSx100=100\r\nLOOP_BARSx100=100\r\nBPMx24=2880\r\n"
                 "TSMODE=0\r\nLOOPMODE=0\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n").encode()
        at = raw.find(b"[SAMPLE]")
        if at < 0:
            sys.exit(f"verify_slicetools: {pw} has no [SAMPLE] section")
        raw = raw[:at] + block + raw[at:]
        for key in (rb"BANK", rb"PATTERN", rb"TRACK", rb"MIDI_MODE"):   # audio tracks, A01, T1
            raw = re.sub(rb"\r\n" + key + rb"=\d+\r\n", b"\r\n" + key + b"=0\r\n", raw, count=1)
        pw.write_bytes(raw.replace(b"MASTER_TRACK=1", b"MASTER_TRACK=0"))
    for suffix in ("work", "strd"):
        pm = dest / f"markers.{suffix}"
        if not pm.is_file():
            continue
        data = bytearray(pm.read_bytes())
        at = 0x16                                            # FLEX slot 1's record
        sl = b"".join(struct.pack(">III", FRAMES * k // NSLICES, FRAMES * (k + 1) // NSLICES, 0xffffffff)
                      for k in range(NSLICES))
        data[at:at + 784] = struct.pack(">III", 0, FRAMES, 0) + sl + bytes(768 - len(sl)) + struct.pack(">I", NSLICES)
        data[-2:] = (sum(data[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        pm.write_bytes(bytes(data))

    def mut(data):
        for p in range(otp.NPARTS_ALL):
            base = otp.PART_BASE + p * otp.PART_STRIDE
            data[base + otp.MTYPE_OFF] = 1                   # T1 FLEX
            data[base + 9 + 0x2ca + 1] = 0                   # T1's FLEX slot: 1
            data[base + 9 + FLAG_OFF] = 0                    # T1's THRU slot byte: AUTO LINEAR off
            data[base + 9 + SLIC_OFF] = 0                    # T1's SLIC off: CREATE LINEAR turns it on
        t = otp.trac_off(0, 0)
        data[t:t + 0x40] = bytes(0x40)                       # T1, A01: no trigs of any kind
        for s in range(64):
            data[t + 0x59 + 32 * s:t + 0x59 + 32 * s + 32] = b"\xff" * 32
        data[t + 7] |= 0x05                                  # trigs on 1 and 3
        data[t + 0x10 + 5] |= 1 << ((20 - 1) % 8)            # trigless on 20
        data[t + 0x5a + 32 * 6] = 0x20                       # STRT on empty step 7
        data[t + 0x5a + 32 * 19] = 0x08                      # STRT on step 20
        data[t + 0x50] = PLEN                                # T1's own LEN (PER TRACK)
        tail = otp.PTRN0 + otp.PTRN_FSTRIDE - 11             # A01's tail = RAM pattern + 0x8e51:
        data[tail] = data[tail + 2] = PLEN                   # LEN 12 (+0x8e53)
        data[tail + 4] = 0                                   # NORMAL, not PER TRACK (+0x8e55)
    otp._bank_write(dest, 1, mut, guard=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    remix = registry.remix(a.remix)
    if "SLICE TOOLS" not in remix.modules:
        print(f"  [ -- ] verify_slicetools: {a.remix} carries no SLICE TOOLS"); return 0
    octakit = "OCTAKIT" in remix.modules
    project = a.project
    if not project and pathlib.Path("~/.octabam_project").expanduser().is_file():
        project = pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
    if not project:
        print("  [SKIP] verify_slicetools: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)"); return 0
    if not EMU.is_file() or not PY.is_file():
        print("  [SKIP] verify_slicetools: no port binary or .venv (make emu-cf, make emu-setup)"); return 0
    pdir = pathlib.Path(project).expanduser()
    if not (pdir / "project.work").is_file():
        sys.exit(f"verify_slicetools: {pdir} is not a project")
    only = set(a.only.split(",")) - {""}
    image = ROOT / "out/mainos_bus.bin"
    img = image.read_bytes()

    def L(addr):
        return struct.unpack(">I", img[addr - BASE:addr - BASE + 4])[0]

    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}", flush=True)
        fails += not ok

    # the tables the build grew, read from the image: the 9-row menu (a slice
    # is selected after the load) is the one these scenarios open
    labels9 = L(0x40072c46)
    auto_label = L(labels9 + 9 * 4)
    grid_labels = L(0x40072cda)
    check(f"image: the SLICE menu's rows 9/10 are the module's (labels at {labels9:#x}), "
          f"the grid has 12 rows, AUTO LINEAR's label at {auto_label:#x}",
          img[0x40072c56 - BASE:0x40072c5a - BASE].hex() == "4878000b"
          and img[0x40072cea - BASE:0x40072cee - BASE].hex() == "4878000c"
          and L(grid_labels + 11 * 4) >= 0x40a955e0 and auto_label >= 0x40a955e0)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    wav = OUT / "slices.wav"
    make_wav(wav)
    build_fixture(pdir, OUT / "project")
    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(OUT / "project"), "OCTABAM", NAME,
                        "--tree", str(OUT / "tree"), "--out", str(card), "--audio", f"{wav}:{SAMPLE_REL}"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_slicetools: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")

    flag_bank = BANK0 + PART_OFF + FLAG_OFF        # + part * PART_LEN, T1
    dumps_of = {
        "bankp": (BANKP, 4), "cur": (CUR, 8), "trac": (BANK0, TRAC_LEN), "strac": (SRAM_BANK, TRAC_LEN),
        "ptail": (BANK0 + 0x8e50, 8), "parts": (BANK0 + PART_OFF, NPARTS * PART_LEN),
        "sparts": (SRAM_PART, NPARTS * PART_LEN), "rec": (FLEX_REC, 0x448), "label": (auto_label, 16),
    }

    # Octakit: her saved Kits and her workspace's dirty byte (her runtime's
    # own symbols), dumped by the scenarios that save or edit a Kit
    kit_tags = {"kitdirty", "kitsave", "kitquick", "kitreload", "kitload", "kitundo",
                "saveproj", "reboot", "saveproj0", "reboot0"}
    if octakit:
        _gk = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(
            ["m68k-elf-nm", str(ROOT / "out/runtime/octakit/runtime.elf")], capture_output=True,
            text=True).stdout.splitlines() if len(l.split()) == 3}
        kit_dumps = {"kits": (_gk["__gk_canonical_payloads"], 256 * PART_LEN),
                     "okdirty": (_gk["__gk_workspace_dirty"], 1), "okkit": (_gk["__gk_current_kit"], 1)}
    else:
        kit_dumps = {}

    def dumpspec(tag):
        dumps = dict(dumps_of, **(kit_dumps if tag in kit_tags else {}))
        return ";".join(f"{ad:#x},{n}={OUT / f'{tag}_{k}.bin'}" for k, (ad, n) in dumps.items())

    scen = []

    def add(tag, s, pokes=(), extra=()):
        if only and tag not in only:
            return
        sp = OUT / f"{tag}.script"
        sp.write_text(s.text())
        args = []
        if pokes:
            args += ["--poke", ";".join(f"{x:#x}={v:#x}" for x, v in pokes)]
        args += ["--live-script", sp, "--lcd", OUT / f"{tag}.lcd", *extra, "--mem-dump", dumpspec(tag)]
        scen.append(f"{OUT / (tag + '.txt')} " + " ".join(map(str, args)))

    s = Script(); start(s); add("base", s)
    s = Script(); start(s); grid(s, 11); add("tlen", s)
    s = Script(); start(s); grid(s, 5); add("grid12", s)
    per_track = [(BANK0 + 0x8e55, 1), (BANK0 + 0x50, 6)]
    s = Script(); start(s); grid(s, 11); add("tlenpt", s, per_track)
    s = Script(); start(s); grid(s, 7); add("grid6", s, per_track)
    s = Script(); start(s); slice_menu(s); s.taps("down", 8); s.tap("yes", 1200); s.tap("yes", 3000)
    add("linear", s)

    def adds(s):
        s.tap("rec", 600)                                     # grid recording
        for k in (8, 10, 6, 0):                               # trigs 9, 11, 7 (locked), 1 (a trig: removed)
            s.tap(k, 500)
        s.down("func", 150); s.tap(9, 300); s.up("func", 500)   # FUNC + trig 10
        s.tap("midi", 800); s.tap(3, 500); s.tap("midi", 800)   # a MIDI track's trig 4
        s.tap("page", 600); s.tap(1, 500)                     # page 2 (LEN 32, poked): trig 2 = step 18
        s.tap("rec", 800)

    def auto_on(s):
        slice_menu(s); s.taps("down", 9); s.tap("yes", 1500)

    len32 = [(BANK0 + 0x8e53, 32)]
    s = Script(); start(s); auto_on(s); s.tap("no", 800); adds(s); add("auto", s, len32)
    s = Script(); start(s); adds(s); add("autooff", s, len32)
    s = Script(); start(s); auto_on(s); s.tap("yes", 1500); add("label", s)
    noslice = [(FLEX_REC + 0x444 + i, 0) for i in range(4)]  # no slices: the editor selects none, the 8-row menu
    s = Script(); start(s); slice_menu(s); s.taps("down", 6); s.tap("yes", 1500); s.tap("yes", 1500)
    add("menu8", s, noslice)
    s = Script(); start(s); slice_menu(s); s.taps("down", 5); s.tap("yes", 1200); s.tap("yes", 3000)
    add("linear0", s, noslice)                                # CREATE LINEAR is row 6 of 8 there

    def machine(s, steps):
        """T1 twice (the slot list), LEFT (SELECT MACHINE TYPE), DOWN/UP, YES"""
        s.tap("t1", 120); s.tap("t1", 800); s.tap("left", 800)
        s.taps("down" if steps > 0 else "up", abs(steps), 300); s.tap("yes", 1000); s.tap("no", 800)

    # a write watch is not armed in a forked scenario (measured: the module's
    # own flag write went unlogged there), so this one runs on its own boot
    mach_bank = BANK0 + PART_OFF + 0x22
    watch = f"{flag_bank:#x},1;{SRAM_PART + FLAG_OFF:#x},1;{mach_bank:#x},1;0x46c8d1a0,4"
    s = Script(); start(s); auto_on(s); s.tap("no", 800)
    machine(s, 1)                                             # FLEX -> THRU
    s.tap("aed", 1500); s.tap("no", 800)                      # the audio editor key on a THRU track
    s.tap("t1", 120); s.tap("t1", 800); s.tap("yes", 1000); s.tap("no", 800)   # its slot list, YES
    machine(s, -1)                                            # THRU -> FLEX
    solo = []
    if not only or "thru" in only:
        sp = OUT / "thru.script"; sp.write_text(s.text())
        solo.append(("thru", card, ["--live-script", sp, "--lcd", OUT / "thru.lcd", "--watch-mem", watch]))
    def savekit(s):
        """Octakit's SAVE KIT: FUNC+PART, YES on the current slot, YES (an unnamed Kit's name editor)"""
        s.down("func", 100); s.tap("part", 200); s.up("func", 1500); s.tap("yes", 1500); s.tap("yes", 3000)

    def quicksave(s):
        """Octakit's quick save of a named Kit: FUNC+PART held, YES"""
        s.down("func", 100); s.down("part", 300); s.tap("yes", 400); s.up("part", 100); s.up("func", 2500)

    def saveproj(s):
        s.tap("proj", 1000); s.tap("right", 700); s.tap("down", 500); s.tap("yes", 1100); s.tap("yes", 30000)

    def linear(s):
        slice_menu(s); s.taps("down", 8); s.tap("yes", 1200); s.tap("yes", 3000); s.tap("no", 800); s.tap("no", 800)

    # with Octakit the part is her workspace Kit: a reboot stages the SAVED
    # Kit over it, so an edit lasts a reboot once SAVE KIT has saved it
    # (stock's SLIC, measured, exactly as the flag); saveproj0 / reboot0 are
    # that rule without SAVE KIT
    s = Script(); start(s); linear(s)
    if octakit:
        savekit(s)
    saveproj(s)
    add("saveproj", s, extra=["--card-out", OUT / "saved.img"])
    if octakit:
        s = Script(); start(s); linear(s); saveproj(s)
        add("saveproj0", s, extra=["--card-out", OUT / "saved0.img"])
        s = Script(); start(s); auto_on(s); s.tap("no", 800); add("kitdirty", s)
        s = Script(); start(s); auto_on(s); s.tap("no", 800); savekit(s); add("kitsave", s)
        s = Script(); start(s); savekit(s); auto_on(s); s.tap("no", 800); quicksave(s); add("kitquick", s)

        def loadkit(s, moves):
            """PART (LOAD KIT; the cursor on the current Kit's row, row 0 is UNDO KIT), UP/DOWN, YES"""
            s.tap("part", 1500)
            s.taps("down" if moves > 0 else "up", abs(moves), 500)
            s.tap("yes", 2500)
        # the flag saved as 1, toggled to 0, FUNC+CUE: the saved 1 back
        s = Script(); start(s); auto_on(s); s.tap("no", 800); savekit(s); auto_on(s); s.tap("no", 800)
        s.down("func", 100); s.tap("cue", 200); s.up("func", 2500); add("kitreload", s)
        # saved as 1; Kit 2 loaded (its own 0), then Kit 1 again: 1
        s = Script(); start(s); auto_on(s); s.tap("no", 800); savekit(s); loadkit(s, 1); loadkit(s, -1)
        add("kitload", s)
        # set, NOT saved; Kit 2 loaded, then LOAD KIT > UNDO KIT: Kit 1 with the unsaved 1, still dirty
        s = Script(); start(s); auto_on(s); s.tap("no", 800); loadkit(s, 1); loadkit(s, -2); add("kitundo", s)

    if scen:
        cmd = [EMU, "--image", image, "--card", card, "--set", "OCTABAM", "--project", NAME,
               "--load-ms", "90000", "--mkii", "--scenario-jobs", "3"]
        for sc in scen:
            cmd += ["--scenario", sc]
        log = OUT / "load.txt"
        with open(log, "w") as f:
            f.write(" ".join(map(str, cmd)) + "\n"); f.flush()
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode:
            sys.exit(f"verify_slicetools: ot_emu exit {r.returncode} -- {log}")
    for tag, img_ in (("reboot", "saved.img"), ("reboot0", "saved0.img")):
        if (not only or tag in only) and (OUT / img_).is_file():
            s = Script(); s.tap("no", 600); sp = OUT / f"{tag}.script"; sp.write_text(s.text())
            solo.append((tag, OUT / img_, ["--live-script", sp]))

    def solo_run(job):
        tag, card_, args = job
        cmd = [EMU, "--image", image, "--card", card_, "--set", "OCTABAM", "--project", NAME,
               "--load-ms", "90000", "--mkii", *args, "--mem-dump", dumpspec(tag)]
        with open(OUT / f"{tag}.txt", "w") as f:
            f.write(" ".join(map(str, cmd)) + "\n"); f.flush()
            subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        list(ex.map(solo_run, solo))

    def have(tag):
        return (OUT / f"{tag}_rec.bin").is_file()

    def d(tag, k):
        return (OUT / f"{tag}_{k}.bin").read_bytes()

    def ran(tag):
        text = (OUT / f"{tag}.txt").read_text() if (OUT / f"{tag}.txt").is_file() else ""
        ok = "ended on quit" in text and have(tag) and d(tag, "bankp") == BANK0.to_bytes(4, "big")
        check(f"{tag}: the live script ran to its quit, bank record at {BANK0:#x}", ok)
        return ok

    def part_of(tag):
        return d(tag, "cur")[3]

    def part(tag, sram=False):
        p = part_of(tag)
        return d(tag, "sparts" if sram else "parts")[p * PART_LEN:(p + 1) * PART_LEN]

    def strt(trac, s):
        return trac[0x5a + 32 * (s - 1)]

    def mask(trac, off):
        return int.from_bytes(trac[off:off + 8], "big")

    def slices(tag):
        r = d(tag, "rec")
        n = struct.unpack(">I", r[0x444:0x448])[0]
        return n, [struct.unpack(">III", r[0x138 + 12 * k:0x144 + 12 * k]) for k in range(min(n, 64))]

    if have("base") and ran("base"):
        t = d("base", "trac")
        n, sl = slices("base")
        check(f"base: the fixture in RAM: trigs {mask(t, 0):#x} (1, 3), trigless {mask(t, 0x10):#x} (20), "
              f"STRT 7 = {strt(t, 7):#x}, 20 = {strt(t, 20):#x}, LEN {d('base', 'ptail')[3]}, "
              f"{n} slices, track {d('base', 'cur')[0]}",
              mask(t, 0) == 0b101 and mask(t, 0x10) == 1 << 19 and strt(t, 7) == 0x20 and strt(t, 20) == 0x08
              and d("base", "ptail")[3] == PLEN and d("base", "ptail")[5] == 0 and n == NSLICES
              and d("base", "cur")[0] == 0 and part("base")[0x22] == 1 and part("base")[FLAG_OFF] == 0
              and part("base")[SLIC_OFF] == 0)
        check(f"base: AUTO LINEAR's label as drawn at the first open: {d('base', 'label')[:15]!r}",
              d("base", "label").startswith(b"AUTO LINEAR:OFF\0"))

    def even(n, tag):
        cnt, sl = slices(tag)
        return cnt == n and sl[0][0] == 0 and sl[-1][1] == FRAMES and all(
            sl[k][1] == sl[k + 1][0] for k in range(n - 1))

    for tl, ctl, n in (("tlen", "grid12", PLEN), ("tlenpt", "grid6", 6)):
        if have(tl) and have(ctl) and ran(tl) and ran(ctl):
            cnt, sl = slices(tl)
            check(f"{tl}: TLEN SLICES wrote {cnt} slices ({sl[:2]} ...), contiguous over the trim range",
                  even(n, tl))
            check(f"{tl}: the slice record equals stock's {n} SLICES ({ctl}) byte for byte",
                  d(tl, "rec") == d(ctl, "rec"))

    if have("linear") and ran("linear"):
        for side in ("trac", "strac"):
            t = d("linear", side)
            want = [2 * ((s - 1) % NSLICES) for s in range(1, PLEN + 1)]
            got = [strt(t, s) for s in range(1, PLEN + 1)]
            other = all(b == 0xff for s in range(1, 65) for i, b in enumerate(t[0x59 + 32 * (s - 1):0x59 + 32 * s])
                        if not (i == 1 and s <= PLEN))
            check(f"linear ({side}): trigs {mask(t, 0):#018x} = steps 1..{PLEN}, every other mask 0",
                  mask(t, 0) == (1 << PLEN) - 1 and all(mask(t, o) == 0 for o in range(8, 0x40, 8)))
            check(f"linear ({side}): STRT {got} = 2*((s-1) mod {NSLICES}); every other lock byte 0xff", got == want and other)
        for sram in (False, True):
            pt = part("linear", sram)
            check(f"linear ({'SRAM' if sram else 'bank'} part): SLIC on ({pt[SLIC_OFF]}), AUTO LINEAR on ({pt[FLAG_OFF]})",
                  pt[SLIC_OFF] == 1 and pt[FLAG_OFF] == 1)

    if have("auto") and have("autooff") and ran("auto") and ran("autooff"):
        t, t0 = d("auto", "trac"), d("autooff", "trac")
        check(f"auto: the keys did the same to the masks with the flag on and off "
              f"(trigs {mask(t, 0):#x}, trigless {mask(t, 0x10):#x})",
              mask(t, 0) == mask(t0, 0) and mask(t, 0x10) == mask(t0, 0x10))
        check(f"auto: trigs on 3, 7, 9, 11, 18 (1 removed); trigless on 10 and 20  {mask(t, 0):#x} {mask(t, 0x10):#x}",
              mask(t, 0) == sum(1 << (s - 1) for s in (3, 7, 9, 11, 18)) and mask(t, 0x10) == (1 << 9) | (1 << 19))
        check(f"auto: empty step 9 -> STRT {strt(t, 9)} (6), step 11 -> {strt(t, 11)} (0, wrapped at 5), "
              f"step 18 on page 2 -> {strt(t, 18)} (4)", strt(t, 9) == 6 and strt(t, 11) == 0 and strt(t, 18) == 4)
        check(f"auto: step 7's lock kept ({strt(t, 7):#x}), removal (1: {strt(t, 1):#x}), trigless (10: "
              f"{strt(t, 10):#x}) and MIDI (4: {strt(t, 4):#x}) got none",
              strt(t, 7) == 0x20 and strt(t, 1) == 0xff and strt(t, 10) == 0xff and strt(t, 4) == 0xff
              and mask(t, 0) & (1 << 3) == 0)
        check("auto: the SRAM twin is the bank's", d("auto", "strac")[:0x89a] == t[:0x89a])
        check(f"autooff: no lock written (9: {strt(t0, 9):#x}, 11: {strt(t0, 11):#x})",
              strt(t0, 9) == 0xff and strt(t0, 11) == 0xff and strt(t0, 18) == 0xff and strt(t0, 7) == 0x20)

    if have("label") and ran("label"):
        check(f"label: reopened with AUTO LINEAR on, the row reads {d('label', 'label')[:15]!r}",
              d("label", "label").startswith(b"AUTO LINEAR:ON\0"))

    if have("menu8") and ran("menu8"):
        check(f"menu8: no slice selected, row 7 of 8 toggled AUTO LINEAR on ({part('menu8')[FLAG_OFF]}), "
              f"the reopened menu reads {d('menu8', 'label')[:15]!r}",
              part("menu8")[FLAG_OFF] == 1 and d("menu8", "label").startswith(b"AUTO LINEAR:ON\0"))

    if have("linear0") and ran("linear0"):
        t, pt = d("linear0", "trac"), part("linear0")
        check(f"linear0: no slices, CREATE LINEAR refused: the track as loaded (trigs {mask(t, 0):#x}, "
              f"STRT 7 {strt(t, 7):#x}), flag {pt[FLAG_OFF]}",
              mask(t, 0) == 0b101 and mask(t, 0x10) == 1 << 19 and strt(t, 7) == 0x20 and pt[FLAG_OFF] == 0)

    if have("thru") and ran("thru"):
        text = (OUT / "thru.txt").read_text()
        w = [(int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)) for m in
             re.finditer(r"\] \[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|0) \(\d\) at pc (0x[0-9a-f]+)", text)]
        mod = [i for i, (ad, v, pc) in enumerate(w) if ad == flag_bank and pc >= 0x40a955e0]
        after = w[mod[0]:] if mod else []
        mach = [v for ad, v, pc in after if ad == mach_bank]
        kinds = [v for ad, v, pc in after if ad == 0x46c8d1a0]
        stock_flag = [(hex(ad), v, hex(pc)) for ad, v, pc in after
                      if ad in (flag_bank, SRAM_PART + FLAG_OFF) and pc < 0x40a955e0]
        print(f"    thru: after the module's flag write: machine {mach}, editor kind {kinds}, "
              f"stock writes to the flag byte {stock_flag}")
        pt = part("thru")
        check(f"thru: the module set the flag, then T1 went THRU and back (machine writes {mach})",
              bool(mod) and mach[:1] == [2] and mach[-1:] == [1])
        check(f"thru: no stock write reached the flag byte across THRU, the editor key and the slot list "
              f"on THRU, and back; the flag is 1 (bank {pt[FLAG_OFF]}, SRAM {part('thru', True)[FLAG_OFF]})",
              not stock_flag and pt[0x22] == 1 and pt[FLAG_OFF] == 1 and part("thru", True)[FLAG_OFF] == 1)

    if have("reboot") and have("saveproj") and ran("saveproj") and ran("reboot"):
        import emu_card
        files = emu_card.extract_image((OUT / "saved.img").read_bytes())
        p = part_of("saveproj")
        for ext in ("work", "strd"):
            data = next((v for k, v in files.items() if k.upper().endswith(f"/{NAME}/BANK01.{ext.upper()}")), b"")
            off = otp.PART_BASE + p * otp.PART_STRIDE + 9 + FLAG_OFF
            check(f"saveproj: bank01.{ext} on the card holds T1's flag (part {p + 1}: "
                  f"{data[off] if len(data) > off else None})", len(data) > off and data[off] == 1)
        t, pt = d("reboot", "trac"), part("reboot")
        check(f"reboot: flag {pt[FLAG_OFF]}, SLIC {pt[SLIC_OFF]}, trigs {mask(t, 0):#x}, "
              f"STRT 1..{PLEN} {[strt(t, s) for s in range(1, PLEN + 1)]}"
              + (" (SAVE KIT before SAVE PROJECT)" if octakit else ""),
              pt[FLAG_OFF] == 1 and pt[SLIC_OFF] == 1 and mask(t, 0) == (1 << PLEN) - 1
              and [strt(t, s) for s in range(1, PLEN + 1)] == [2 * ((s - 1) % NSLICES) for s in range(1, PLEN + 1)])
        if octakit:
            k = d("saveproj", "okkit")[0]
            kt = d("saveproj", "kits")[k * PART_LEN:(k + 1) * PART_LEN]
            check(f"saveproj: SAVE KIT put the flag and SLIC in Kit {k + 1}'s saved data "
                  f"(flag {kt[FLAG_OFF]}, SLIC {kt[SLIC_OFF]})", kt[FLAG_OFF] == 1 and kt[SLIC_OFF] == 1)

    if octakit and have("reboot0") and have("saveproj0") and ran("saveproj0") and ran("reboot0"):
        pt0, pt1 = part("saveproj0"), part("reboot0")
        check(f"reboot0: no SAVE KIT: the flag reverts with stock's SLIC, as every Kit edit does "
              f"(before the reboot flag {pt0[FLAG_OFF]} SLIC {pt0[SLIC_OFF]}, after flag {pt1[FLAG_OFF]} "
              f"SLIC {pt1[SLIC_OFF]})",
              (pt0[FLAG_OFF], pt0[SLIC_OFF]) == (1, 1) and (pt1[FLAG_OFF], pt1[SLIC_OFF]) == (0, 0))

    if octakit:
        def kitflag(tag):
            k = d(tag, "okkit")[0]
            return k, d(tag, "kits")[k * PART_LEN + FLAG_OFF]
        if have("kitdirty") and ran("kitdirty"):
            k, kf = kitflag("kitdirty")
            check(f"kitdirty: AUTO LINEAR alone marks Octakit's workspace dirty as a stock edit does "
                  f"(dirty {d('kitdirty', 'okdirty')[0]}); her saved Kit {k + 1} still reads {kf}; "
                  f"part and SRAM twin {part('kitdirty')[FLAG_OFF]}/{part('kitdirty', True)[FLAG_OFF]}",
                  d("kitdirty", "okdirty")[0] == 1 and kf == 0
                  and part("kitdirty")[FLAG_OFF] == 1 and part("kitdirty", True)[FLAG_OFF] == 1)
        for tag, k_, f_, dirty, how in (
                ("kitreload", 0, 1, 0, "saved as 1, toggled to 0, FUNC+CUE (reload)"),
                ("kitload", 0, 1, 0, "saved as 1, LOAD KIT 2, LOAD KIT 1"),
                ("kitundo", 0, 1, 1, "set and not saved, LOAD KIT 2, LOAD KIT > UNDO KIT")):
            if have(tag) and ran(tag):
                kk, wf = d(tag, "okkit")[0], part(tag)[FLAG_OFF]
                check(f"{tag}: {how}: Kit {kk + 1}, the part's flag {wf}, SRAM twin {part(tag, True)[FLAG_OFF]}, "
                      f"workspace dirty {d(tag, 'okdirty')[0]}",
                      kk == k_ and wf == f_ and part(tag, True)[FLAG_OFF] == f_ and d(tag, "okdirty")[0] == dirty)
        for tag, how in (("kitsave", "SAVE KIT"), ("kitquick", "the quick save of a named Kit")):
            if have(tag) and ran(tag):
                k, kf = kitflag(tag)
                check(f"{tag}: AUTO LINEAR alone, then {how}: Kit {k + 1}'s saved flag {kf}, "
                      f"workspace dirty {d(tag, 'okdirty')[0]}", kf == 1 and d(tag, "okdirty")[0] == 0)

    print(f"verify_slicetools: {'ok' if not fails else 'FAILED'} ({fails} failure(s)) -- {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
