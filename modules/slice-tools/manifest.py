"""SLICE TOOLS -- slices that follow the track: TLEN SLICES, CREATE LINEAR, AUTO LINEAR.

Three additions to the audio editor's SLICE page, for a sliced sample played
one slice per step:

  TLEN SLICES     a 12th row in CREATE SLICE GRID: N equal slices, N = the
                  active track's length (PER TRACK: the track's own; else the
                  pattern's), clamped 1..64, through the stock setter
                  0x40073984(N), so the stock guards, the ZERO-CROSS ALIGN?
                  question and the stock record writer all run.
  CREATE LINEAR   a SLICE menu row: CLEAR TRACK? SURE?, then the active
                  track in the current pattern is cleared by stock's CLEAR
                  TRACK TRIGS (0x40039df4, mask 1; its undo saved first as
                  stock does), trigs are placed on steps 1..len, stock's
                  CREATE LINEAR LOCKS writer (0x40073544) puts STRT
                  2*((s-1) mod count) on each and turns SLIC on, and AUTO
                  LINEAR is switched on for the track.
  AUTO LINEAR     a SLICE menu row drawn AUTO LINEAR:ON / :OFF for the active
                  track (rewritten each time the menu opens): toggles a
                  per-track flag kept in the Part, so it is saved with it
                  (with Octakit the Part is her Kit: the write goes through
                  her editing functions and SAVE KIT saves it).
                  While on, a trig the step key adds on an EMPTY step gets
                  STRT 2*((s-1) mod count) when the step has no STRT lock.
                  Only that add: not a removal, a trigless or lock trig, live
                  recording, copy/paste or a MIDI track (none of them reach
                  the hooked branch).

Both new SLICE rows are in both SLICE menus (6 rows with no slice selected,
9 with one), before CHANGE VIEW. The flag lives in the track's THRU slot
byte (part + 0x2cc + 5t), which a STATIC or FLEX track does not use; the
README says what was measured about that byte and what was not.

Every stock address and offset: README.md and the unit's header.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, SymbolRef

H = bytes.fromhex
UNIT = "slicetools"

# The SLICE menu opener 0x40072c10: `lea 0x4006d94c,%a0` (the list routine)
# before either branch pushes its tables; the detour rewrites AUTO LINEAR's
# label for the active track, then replays the lea.
OPEN_SITE = 0x40072C30
OPEN_STOCK = H("41f94006d94c")

# The step key's empty-step add (0x40051970..0x40051afa): `move.l #1165,%d4`
# after the trig bit is in the bank's mask and before its SRAM twin.
ADD_SITE = 0x40051AEA
ADD_STOCK = H("283c0000048d")

# SLICE menu tables (0x400ceb3c < 0: no slice selected, 6 rows; else 9).
MENU6_HANDLERS, MENU6_LABELS = 0x400CEB74, 0x400CEB8C
MENU9_HANDLERS, MENU9_LABELS = 0x400CEBA4, 0x400CEBC8
# CREATE SLICE GRID's popup 0x40072cb8: 11 rows, 64 .. 2 SLICES.
GRID_HANDLERS, GRID_LABELS = 0x400CEC08, 0x400CEC34

MODULE = Module(
    name="slice-tools",
    key="SLICE TOOLS",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES, author="dries", author_url="https://github.com/sanderlegit",
    proof=Proof.PORT, proof_note="verify_slicetools under the port, 9 Oct 2026; with Octakit "
               "(bottleservice-pf), 10 Oct 2026",
    doc="Audio editor SLICE page: CREATE SLICE GRID > TLEN SLICES (one slice per track step), "
        "SLICE menu > CREATE LINEAR (clear the track, a trig and a slice lock per step) and "
        "AUTO LINEAR (a trig added on an empty step gets its step's slice).",
    linked=(Linked(UNIT, "modules/slice-tools/slice_tools.s", dram=True),
            Linked("slicetables", "modules/slice-tools/slice_tables.s", dram=True)),
    detours=(
        Detour(OPEN_SITE, OPEN_STOCK, UNIT, "menu_open",
               "SLICE menu opener: AUTO LINEAR's label for the active track"),
        Detour(ADD_SITE, ADD_STOCK, UNIT, "auto_hook",
               "step key, empty-step add: AUTO LINEAR's STRT lock"),
    ),
    # pf-slice-qrec: the grown arrays live in DRAM (slice_tables.s); the six
    # stock pointer operands are repointed at them.
    symbol_refs=tuple(SymbolRef(ref, old, "slicetables", "st_" + name, f"{name} -> DRAM")
        for ref, old, name in (
            (0x40072C5E, MENU6_HANDLERS, "menu6_handlers"),
            (0x40072C64, MENU6_LABELS, "menu6_labels"),
            (0x40072C40, MENU9_HANDLERS, "menu9_handlers"),
            (0x40072C46, MENU9_LABELS, "menu9_labels"),
            (0x40072CD4, GRID_HANDLERS, "grid_handlers"),
            (0x40072CDA, GRID_LABELS, "grid_labels"))),
    pokes=(
        Poke(0x40072C74, expect=H("48780006"), write=H("48780008"),
             note="SLICE menu (no slice): 6 -> 8 rows"),
        Poke(0x40072C56, expect=H("48780009"), write=H("4878000b"),
             note="SLICE menu (slice): 9 -> 11 rows"),
        Poke(0x40072CEA, expect=H("4878000b"), write=H("4878000c"),
             note="CREATE SLICE GRID: 11 -> 12 rows"),
    ),
    gates=(Gate("tools/verify/verify_slicetools.py"),),
)
