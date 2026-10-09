# `role-paste` — ROLE PASTE

A ColdFire patch for the rig: an FX2 page paste (a page key + PASTE) or a
track paste (GRID REC, FUNC + PASTE) keeps the destination track's bus
role. T1 stays BusDelay, T5 BusVerb, T8 RETURNS (when the remix carries
RETURNS), and every other track SEND. Only the sends cross: DEL and REV,
page-1 slots 0 and 1, which are the same two knobs on SEND, BusDelay and
BusVerb (their manifests). The destination keeps the rest of its own FX2
page.

## The bug it fixes

Seen on an MKII, RIGPF11B (`bottleservice-pf`), 9 Oct 2026. T1's FX2 page
was copied and pasted on another track. The knobs pasted and the page read
like SEND's, but the sends did nothing. Pasting T3's FX2 page (a real SEND)
fixed it.

A page paste copies the effect id with the knobs. Stock's page restore
(`0x40027e4c`, case page 4) writes clipboard + 18 into three places: the
FX2 id of the working part (part + 8 + t), the SRAM mirror, and the live id
`0x80000ecc[t]` that the DSP is handed. So T2 got T1's id `0x06`, the
hidden BusDelay, and BusDelay off its host slot is a dry pass (HOSTGUARD).
HOST LOCK guards the FX2 chooser, not a paste. A track paste (`0x4002b654`,
called from `0x4002b988`) carries the FX2 id in the same way, from
clipboard + `0x91b`.

## How

There are four detours, two per paste. None is at a site Octakit's recipe
claims (checked against her `firmware.json`; the ledger checks again on
every build):

| site | stock bytes | stock instruction | stub |
|---|---|---|---|
| `0x4005df40` | `2f39 8000 0012` | `move.l 0x80000012,-(sp)`: head of the page PASTE handler (key `0x27` of the page-key layer, record word `0x400baaee`, which holds Octakit's wrapper; her wrapper calls this routine whole) | `rp_page` |
| `0x4005dfe8` | `70ff 2f40 0004` | `moveq #-1,d0` / `move.l d0,4(sp)`: the point every exit of that handler joins (paste, undo, nothing to paste) before `jmp 0x4004d948` | `rp_page_done` |
| `0x4002b996` | `2f2f 0008 2f2f 0008` | `move.l 8(sp),-(sp)` ×2: the track paste, after its tag check, before `pea 0x460c8122` / `jsr 0x4002b654` | `rp_track` |
| `0x4002b9a8` | `7001 4fef 000c` | `moveq #1,d0` / `lea 12(sp),sp`: the return of that `jsr`. Octakit's track-store wrapper checks this return ADDRESS (`GK_STOCK_AUDIO_TRACK_PASTE_RETURN`), and the address does not change | `rp_track_done` |

The first stub of each pair rewrites the clipboard's FX2 for the
destination track. The paste that follows is stock's own, with stock's
writes (part, mirror, live id, engine lanes), stock's undo and stock's
dirty marks. Octakit's checks see a stock paste: working part == mirror,
the paste tag, the marker counts, her caller checks. The second stub puts
the clipboard back as it was copied, so the next paste on another track
starts from the source again. No Octakit word, wrapper or return address
changes.

The rewrite. S is the clipboard's id, R is the destination's role, and D is
its FX2 before the paste.

- **S == R:** nothing changes, and the paste is stock's. Examples: T3 → T2
  (SEND → SEND), or T1 → T1 in another part.
- **Otherwise:**
  - The id becomes R.
  - The page is D's own bytes when D already holds R. When it does not, the
    page is R's descriptor defaults (`FX2_IDS[R]` + `0x5e` / + `0x64`, the
    bytes RIG HOSTS and the chooser write).
  - When S and R both carry sends (BusDelay, BusVerb, SEND), slots 0 and 1
    are the source's.
- **T8 without RETURNS** has no role. R is the id T8 already holds.

Why the destination keeps its other slots: those slots mean different
things on each effect. BusDelay has FDBK/TONE/PING/WET (and MODE … TIME on
page 2), BusVerb has SIZE/SHMR/SHFT/WET, SEND has blanks, and RETURNS'
slots 0/1 are return levels (DLY/VRB), not sends. That is also why nothing
crosses to or from T8: T1 → T8 leaves T8's return levels alone, and T8 →
T2 does not turn RETURNS' 108/108 into T2's sends.

How the DSP gets the right effect: the same way the bug reached it, through
the live id `0x80000ecc[t]` that stock's paste writes. The stub only
changes which id that is.

## Measured (under the port, 9–10 Oct 2026)

All of the following come from `tools/verify/verify_role_paste.py
bottleservice-pf` with the RIGTEST project. The copy's stored RETURNS
`0x1e` was migrated to `0x1b`, and the copy's Kit is staged by Octakit.

- **Control** (the same remix without ROLE PASTE):
  - A T1 → T2 FX2 page paste gives T2 id `0x06` in the part and in the
    live ids. This is the bug.
  - A T1 → T2 track paste does the same.
  - With the DSP emulated (`--dsp`), core 1 enters BusDelay's code at
    `P:0x66f` once at load, and once more after the page paste.
- **Fixed**, FX2 page paste, each pair checked in the part, the mirror, the
  live id and the engine page lanes:

  | paste | result |
  |---|---|
  | T1 → T2, T2 → T1, T1 → T5, T5 → T1 | the destination keeps its id; DEL/REV are the source's; the other 10 bytes are its own |
  | T1 → T8, T8 → T2 | the destination unchanged |
  | T3 → T2 | the source's whole page (stock) |
  | T2's FX1 page → T2's FX2 (FX1 and FX2 share the clipboard tag `0x1d`) | T2 unchanged |
  | T2 given RETURNS through its chooser, then T8 → T2 | T2 SEND at SEND's descriptor defaults |
  | T2 given RETURNS through its chooser, then T1 → T2 | the same, with T1's DEL/REV |

  For every page paste:
  - the whole part equals its mirror (Octakit's own invariant);
  - every other track is unchanged;
  - the clipboard is back as copied;
  - COPY PAGE / PASTE PAGE shown, and no halt.
- **Fixed, PASTE twice:** the second press is stock's undo, and T2's own
  id and page come back.
- **Fixed, the DSP:** core 1 does not enter BusDelay's code again after
  T1 → T2.
- **Fixed, track paste:** T1 → T2, T2 → T1, T1 → T5 and T3 → T2 follow
  the same rule.
  - The part/mirror gap equals the control's byte for byte. Two causes,
    both stock: Octakit's Kit staging, and part + `0x2ce` + 5t, which
    stock's track paste writes to the part only.
- **Fixed, AMP page:** CLEAR, COPY and PASTE complete with no halt and the
  FX2 untouched.
- **Octakit's and HOST LOCK's gates still pass** on `bottleservice-pf`:
  `verify_octakit`, `verify_octakit_mirror`, `verify_machine_select` and
  `verify_hostlock`.

## Inferred

- **The DSP runs what the live id names.** On the unit, the bug's dry T2
  and the repair by a SEND paste both point to this. Under the port, the
  extra entry at `P:0x66f` (the start of BusDelay's record; one entry per
  load, so not the per-frame proc) is read as the DSP setting BusDelay up
  on T2's slot. The DSP's dispatch per slot is not watched directly.
- **FX1 carries no role in the rig.** Its chooser lists stations and stock
  effects. A FX2 page pasted on an FX1 (same tag) puts that id on FX1:
  measured, T1 → T2's FX1 gives FX1 `0x06`. That FX1 is a dry pass
  (HOSTGUARD; SEND on an FX1 slot does not send, `modules/send/README.md`),
  and FX1's chooser repairs it on the unit. Left stock.

## Other routes that can put an FX2 id on a track

- **FX2 page paste:** covered (above).
- **Track paste** (GRID REC, FUNC + PASTE; "PASTE TRACK"): covered
  (above). Its undo (`0x4002b910`) restores from the undo buffer and is
  stock.
- **MIDI track paste:** not applicable. A MIDI track has no FX.
- **Part copy/paste, pattern + kit paste, Kit load/paste (Octakit):** not
  covered. These copy a whole part, so every id stays on its own track
  position. A part or Kit saved in the rig carries the roles where they
  belong. One saved elsewhere (another project, or one from before the rig)
  carries whatever it had, as loading such a project does.
  `tools/hw/ot_project.py host` puts the roles back on the card. Not
  measured under the port.
- **FX2 chooser:** HOST LOCK (T1/T5 refused, T8 RETURNS only). SEND or
  RETURNS on T2–T4/T6/T7 stays possible, and RETURNS there is a no-op.

## Open

- Not yet on a unit.
- A track paste into a pattern whose part is not the current one. The
  stub reads the part the way stock does (pattern + `0x8e57`), but the gate
  only pastes within one pattern.
