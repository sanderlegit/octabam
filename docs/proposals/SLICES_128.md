# 128 slices per sample

Parked proposal, 9 Oct 2026. Not scheduled; the slice tools module (TLEN
SLICES, CREATE LINEAR, AUTO LINEAR) ships within the stock 64 first. This
page keeps what was read so the work can restart without re-reading the
image.

Wanted: up to 128 slices on one sample, every point stored and saved, a
slice knob that moves one slice per detent, and extended snapping in the
slice editor.

All addresses are OS 1.40C at load base `0x40000400`. ✅ read from the
image bytes; 🟡 inferred. Nothing here has run under the port or on a unit.

## Verdict

128 is feasible and large. 256 is not practical:

- ✅ A step lock is one byte, 0..127, with `0xff` as "none". There is no
  spare bit for a 256th value.
- ✅ The SLIC-off start path reads the STRT byte `<< 8` as a fraction
  (`0x400099b4`), so a byte above `0x7f` would turn negative there.
- ✅ The voice's slice field (voice `+0x20`) is read **signed**, with −1 as
  "none" (`blts` at `0x40007ad2`). 0..127 fit; 128 does not.

256 would need a second lock store and a wider voice field.

## Where 64 is baked in

### Storage (medium)

- ✅ The slot settings record has a fixed `0x448` stride: FLEX `0x100b14f0`,
  STATIC `0x100d5b30`, recorders `0x100d38f0 + 0x448·t`.
  - The trim is at `+0x12c/+0x130/+0x134`.
  - Slice k is the 12-byte `{start, end, loop}` at `+0x138 + 12k`.
  - The 12 bytes at `+0x438` are a 65th scratch entry (`0x400741a8`; swapped
    into slice 0 at `0x40093716`, `0x40096cdc`).
  - The count is a long at `+0x444`.
  - The record is full; it cannot grow in place.
- ✅ The `markers.work` reader sits in `0x40084870`.
  - Its version gate is at `0x40085dd0`: above 4 returns −52, **so a v5 file
    would be refused by stock firmware**.
  - It loops `moveq #64` for FLEX at `0x40086424` and for STATIC at
    `0x40086622`.
  - It checks a u16 byte sum of `0x10..end−2` at `0x40086694`.
- ✅ The `markers.work` writer is `0x40089d84`, called from `0x400902ba`.
  Its slice loops are at `0x40089f5c` and `0x4008a0b0`; the sum is written
  at `0x4008a100`.
- ✅ The sanitiser `0x40099374` clamps the count to 0..64
  (`0x40099524/2a`).
- ✅ `.ot` files (SMPA v2):
  - writer `0x40089940`, with its 64 at `0x40089d10`;
  - reader `0x4008b8d0`, with its 64 at `0x4008bd96`;
  - loader `0x40095cd8`.

**Design.** Keep the record, `markers.work` and `.ot` at v4, holding slices
0..63 and `min(count, 64)`. Put slices 64..127 and the true count in a DRAM
table: 264 slots × 64 × 12 = 202,752 B, in the platform reserve. Store them
in a sidecar file that stock firmware ignores. The obvious home for that
file is the OTX store or a module-owned file (`OTX_PROJECT_PROPOSAL.md`).

- Hooks go after the reader at its caller and after the writer at
  `0x400902ba`.
- 🟡 Card file I/O from a runtime is not checked.
- With this design a project still loads on stock firmware, which sees the
  first 64 slices.

### Playback (medium)

Every site below multiplies the slice index by 12; one accessor,
`entry(rec, i)`, replaces them.

- ✅ Voice start `0x4000f63e..f6da`:
  - the slice is STRT `>> 1` (`asrl #1` at `0x4000f650`), but only with SLIC
    on (`a3@(25)`);
  - it is clamped to count−1;
  - then come the start-slice and end-slice lookups (end slice = slice + the
    LEN byte).
- ✅ Per-frame voice update `0x40007aa0..7b32`: three lookups, plus the end
  slice's loop point (`a1@(8)`, −1 off).
- ✅ STATIC preload range `0x40094334`: a second `asrl #1` at `0x400943ae`,
  and three lookups.
- 🟡 No other reader of the slice array was found. A reader that goes
  through a stored record pointer can't be ruled out.
- Risk: the accessor's cost per voice per frame at `0x40007aa8` is
  unmeasured.

### Selection (small to medium)

**Dropping the ×2/÷2** makes lock value = slice number, one slice per knob
detent with no new UI. The pairs:

| Site | What it does |
|---|---|
| ✅ `0x4000f650` | voice start: slice = STRT `>> 1` |
| ✅ `0x400943ae` | STATIC preload: a second `>> 1` |
| ✅ `0x4004f8dc` | trig-key slice mode (mode 3, `0x460d16f0`) press handler: refuses slice > 63 at `0x4004f8f0`, writes STRT = 2·slice at `0x4004f938`, halves again at `0x4004f9a4` |
| ✅ `0x4007331e` | editor "slices → trigs", random (`0x40073218`): writes 2·slice |
| ✅ `0x40073612` | editor "slices → trigs", sequential (`0x40073544`): writes 2·slice |

- The trig-key slice mode pages 4 × 16 (`andl #3` at `0x4004ff08`). Its LEDs
  are at `0x400440de`, and count/16 is at `0x40044920`.
- ✅ The display at `0x4003b514` prints `"SL%d"` of `(v>>1)+1` without
  checking the count.
- 🟡 "SL128" is five characters; whether that fits the field is unmeasured.

**Migration risk:** parts saved with today's 2× locks would play the wrong
slice. That needs either a one-off halving of every STRT lock or an opt-in
per sample.

### Editor (large)

- ✅ Add slice `0x400730f0`: `moveq #62; cmpl count` at `0x40073130`, with
  "TOO MANY SLICES!" at `0x400731e8`.
- ✅ The grid menu has 11 entries {2..64}: handlers at `0x400cec08`, labels at
  `0x400cec34`.
  - The writer `0x40073a68` fills N+1 longs at `0x460e6a9e`.
  - Past N = 64 those longs overwrite `0x460e6ba2..6bae`: record pointer,
    trim start, length, zero-cross flag.
- ✅ Four 64 × 14 B UI arrays at `0x460e5fe4`, `0x460e6372`, `0x460e6700` and
  `0x460e670a`, looped at `0x40070d7c`, `0x400710a2`, `0x400719ea`. Every
  literal that points at them has to move to DRAM.
- ✅ Zero-cross snap runs per boundary (`0x40022978`; prompt at
  `0x400739d0`, mode at `0x400ceb38`, loop `0x40072e74..f58`). Extended
  snapping is new code.
- ✅ Other 64-bound code:

  | Address | Routine |
  |---|---|
  | `0x40072f7c` | delete |
  | `0x40071eb0` | delete all |
  | `0x40071668` | jump to slice |
  | `0x400760b0`, `0x40076200`, `0x400762b4` | list drawing (`"Slice%02d"`) |

- 🟡 128 markers is one per pixel across the waveform.

### Patterns (optional)

✅ A track holds at most 64 steps, also in PER TRACK mode. Locks reach every
slice, but a 1:1 layout of 128 slices spans two patterns. The stock
"slices → trigs" writers fill only the current one.

## Cost

| Area | Work |
|---|---|
| Storage | medium |
| Playback | medium |
| Selection | small–medium |
| Editor | large |
| Patterns | optional |

All of it needs a DRAM runtime. Gates before any flash, under the port:

- a 128-slice project round-trips through save and reload;
- a stock image loads the same project and plays slices 0..63;
- the per-frame cost of the accessor;
- the lock migration on an old part.
