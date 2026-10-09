"""QREC TLEN -- a manual recording quantised to the recording track's own loop
point.

QREC quantises a MANUAL recording (TRACK + REC AB/CD, either order) to a
class of master-clock steps; PLEN waits for the MASTER loop. In PER TRACK
scale mode a track shorter than the master (master 256 / track 64) starts a
PLEN take only every 256 steps, and at master INF never. A sequencer
recorder trig is not quantised at all (measured: it never enters the
scheduler). This module adds QREC value 17, drawn TLEN: the take starts on
the recording track's own next loop point, whichever comes first of its own
wrap and the restarts PLEN already marks (master length, pattern change).

One cave, three entries (tlen_cave.s):

  cave  hooked at 0x400a42d0, the master step's mask build (FUN_400a1e10),
        after the ladder bits: bit 17+t in the class mask at the first master
        step whose mask fires at or after the track's loop start. A track
        step processed at tick P sounds its own step (tt ticks) later, the
        mask mt ticks later (measured, README.md), so with e = ticks since
        the loop's step 1 was processed and L = length x tt the bit is set
        when (e - tt + mt) mod L < mt. Same scale: the stock comparator
        (0x4000b2ce) supplies the loop start's own sample and subframe;
        another scale is late by fewer than mt ticks.
  cls   poke at 0x400051cc (the scheduler FUN_40005178's `lea 0x400d8120,a0`
        -> jsr): raw 17 stages class (1 << (17+t)) | 1.
  fmt   the QREC slot's formatter word 0x400d3d9a: 17 -> "TLEN" (the string
        is the cave's), else the stock formatter 0x4003b150.

Plus the descriptor's QREC count (E = 0x400d3c74, +0xd2 + 9 x 4 = 0x400d3d6a)
18 -> 19, which the setup editor clamps by. Raw -1..16 keep their meaning;
saved parts need no restamp. On a stock image a stored 17 survives the bank
load and quantises to the next 2-step boundary (the class read past the
table is a message buffer, 0x11pp0015): measured, docs/firmware/RECORDER.md
section 1b.

Assemble: `m68k-elf-as -mcpu=5475 -o tlen.o tlen_cave.s`; the build
re-assembles, links at the resolved address and compares against the pinned
bytes (position-independent: the two self-references are pc-relative).
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, SymbolRef

MASK_HOOK = 0x400a42d0
MASK_HOOK_STOCK = bytes.fromhex("7b03" "2c3c00285ff0")    # mvs.b d3,d5; move.l #2646000,d6

CLS_SITE = 0x400051cc
CLS_STOCK = bytes.fromhex("41f9400d8120")                 # lea 0x400d8120,a0
CLS_OFF = 0xac                                            # `cls:` in the cave
FMT_OFF = 0xc4                                            # `fmt:`

QREC_FMT = 0x400d3c74 + 0x102 + 9 * 4                     # 0x400d3d9a, descriptor entry 8, slot 9
QREC_COUNT = 0x400d3c74 + 0xd2 + 9 * 4                    # 0x400d3d6a

TLEN_CAVE_BYTES = bytes.fromhex(
    "7b03" "2c3c00285ff0"                    # displaced
    "4fefffe4" "48d7031f"                    # save d0-d4/a0-a1
    "7007" "223c01000000"                    # t = 7; bit 24
    "41f9800064d0"                           # a0 = step[]; tick[] +0x20, running[] +0x30
    "75b00830" "5382" "66000074"             # next: running[t] == 1?
    "43f98000663e" "75310800"                # d2 = scale[t]
    "43f9400aba50" "24312c00"                # d2 = tt = ticks[scale]
    "224c" "d3fc00008e53" "7911"             # d4 = the pattern's length (a4 + 0x8e53)
    "4a290002" "67000014"                    # PER TRACK (+0x8e55)?
    "263c0000091a" "4c003000"                #   d3 = t x 0x91a
    "224c" "d3c3" "79290050"                 #   d4 = the track's length
    "4a84" "6f000036"                        # havelen: none -> skip
    "4c024000"                               # d4 = L = length x tt
    "77b00800" "4c023000" "9682"             # d3 = step x tt - tt
    "75b00820" "d682" "d685"                 # + tick + mt = x
    "b885" "6f000018"                        # L <= mt: set
    "4a83" "6c000004" "d684"                 # x < 0: + L
    "b684" "6d000004" "9684"                 # x >= L: - L
    "b685" "6c000004"                        # x >= mt: skip
    "8392"                                   # set: mask |= bit
    "e289" "5380" "6c00ff7e"                 # skip: next track
    "4cd7031f" "4fef001c" "4e75"             # restore, rts
    "7211" "b081" "6700000a"                 # cls: raw 17?
    "41f9400d8120" "4e75"                    #   displaced lea, rts
    "2003" "41fa0024" "4e75"                 # tlen: d0 = track; a0 = classes
    "7011" "b0af0008" "66000010"             # fmt: value 17?
    "41fa0034" "2f480008" "4ef940013a08"     #   sprintf(buf, "TLEN")
    "4ef94003b150"                           # stock: the stock QREC formatter
    "0000"
    "00020001" "00040001" "00080001" "00100001"
    "00200001" "00400001" "00800001" "01000001"
    "544c454e0000")                          # "TLEN"

assert TLEN_CAVE_BYTES[CLS_OFF:CLS_OFF + 2] == bytes.fromhex("7211")
assert TLEN_CAVE_BYTES[FMT_OFF:FMT_OFF + 2] == bytes.fromhex("7011")


def emit(addr):
    """No cave bytes (the linked source supplies them); the class hook, the
    formatter word and the count."""
    pokes = (
        (CLS_SITE, CLS_STOCK, bytes.fromhex("4eb9") + (addr + CLS_OFF).to_bytes(4, "big")),
        (QREC_FMT, (0x4003b150).to_bytes(4, "big"), (addr + FMT_OFF).to_bytes(4, "big")),
        (QREC_COUNT, (18).to_bytes(4, "big"), (19).to_bytes(4, "big")),
    )
    return b"", pokes


# pf-slice-qrec: the bottleservice-pf clone window has no room for a
# floating 266-byte cave, so the same source links into the DRAM platform
# runtime and the three sites reach it by symbol (the CavePatch above is the
# qrec-tlen branch's ROM form; TLEN_CAVE_BYTES stays the reference).
MODULE = Module(
    name="qrec-tlen",
    key="QREC TLEN",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES, author="dries", author_url="https://github.com/sanderlegit",
    proof=Proof.PORT, proof_note="verify_qrec_tlen, 9 Oct 2026",
    doc="ColdFire cave: QREC value TLEN (past 256) = a manual recording starts on the "
        "recording track's own loop point in PER TRACK mode, not the master's.",
    gates=(Gate("tools/verify/verify_qrec_tlen.py"),),
    linked=(Linked("tlen", "modules/qrec-tlen/tlen_cave.s", dram=True),),
    detours=(
        Detour(MASK_HOOK, MASK_HOOK_STOCK, "tlen", "qrt_cave",
               "master step: class bit 17+t at the track's loop start", kind="jsr",
               pad_to=8),   # the displaced span is 8 bytes (mvs.b + move.l #imm)
        Detour(CLS_SITE, CLS_STOCK, "tlen", "qrt_cls",
               "scheduler class lookup: raw 17 -> the track's bit | PLEN", kind="jsr"),
    ),
    symbol_refs=(SymbolRef(QREC_FMT, 0x4003b150, "tlen", "qrt_fmt",
                           "QREC formatter: 17 draws TLEN"),),
    pokes=(Poke(QREC_COUNT, (18).to_bytes(4, "big"), (19).to_bytes(4, "big"),
                "QREC count 18 -> 19"),),
)
