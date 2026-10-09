# `qrec-tlen` — QREC TLEN

A ColdFire code cave, no DSP code: a new QREC value past 256, drawn `TLEN`,
that starts a manual recording on the recording track's **own** next loop
point. In PER TRACK scale mode, stock `QREC PLEN` waits for the master loop.
A 64-step track under a 256-step master records only every 256 steps, and at
master length INF it never records. With `TLEN` the take starts on the
track's next step 1. With RLEN PLEN (`modules/rlen-plen`) and TRIG `ONE`,
one press records exactly one loop of the track, starting on it.

QPL (manual playback) is untouched. RLEN is RLEN PLEN's.

## How stock quantises a manual take (measured, port, stock 1.40C, 9 Oct 2026)

Fixture: a copy of a project with bank 1 rewritten (every pattern and part).
T1 records. T2 has T1's length and scale and a REC1 trig on step 1, so its
arm sample (`0x46c7fa84[1]`) marks each of T1's loop points in the same clock
as T1's arm (`0x46c7fa84[0]`, written at `0x40006b4a` as `[0x46104cf8]` + the
in-frame offset). T1's recorder sources (INAB, INCD, SRC3, AB, CD) are set to
T2's in every part: with a different source, T1's arm sat 0x50 samples before
T2's reference arm on stock as well ("PROJECT 2025": T1 INAB 0 / SRC3 0, T2
INAB 1 / SRC3 9). Keys are the panel's, through `ot_emu --live-script`. The
scripts are `tools/verify/verify_qrec_tlen.py`'s.

- **The gesture.** TRACK + REC AB (`0x10`, `0x2b`), in either order,
  reaches `FUN_400836d8`, which calls the scheduler `FUN_40005178(t, 0x9010,
  1)` through `jsr (a4)` at `0x4008385c` (`a4 = 0x40005178`, loaded at
  `0x40083908`; the brief's caller list missed this one, because it is a
  register call). REC AB alone on a FLEX or STATIC track does nothing. The
  REC key handler `0x40030e6c` reaches `0x40097924` only for a PICKUP
  machine or under grid recording. The UI loop's own TRACK+REC path,
  `0x400628ec` → `0x40097924(…, 0)`, passes quant 0.
- **A sequencer recorder trig is never quantised.** A REC1 trig on step 9
  under QREC PLEN arms on step 9 of every pass. `FUN_40005178` is not entered.
- **Staging.** `FUN_40005178` reads the part's QREC byte (`blob + part ×
  6322 + t × 12 + 0x8f38b`). For raw ≥ 0 it stages `0x800018be[t] =
  class[raw]` (`0x400d8120`) and `0x800018de[t] = cmd`. For −1 (OFF) it
  writes `0x46c7e9fa[t] = cmd` at once (`0x400051f4`).
- **The mask is built in the same tick as the wrap.** In one sequencer tick
  (`FUN_400a1e10`) the per-track loop (`0x400a3cd0..`) advances every track,
  and a track at its length clears its step counter and calls `0x400a536c`.
  Then the master step (`0x400a421a..`) increments `0x800065b2`, ORs the
  class bits into one of two mask buffers (`0x46c7fe94/98`, alternating via
  `0x461077c4`), and stamps that buffer's timestamp (`0x80001904[59 + buf]`)
  one master step ahead. PLEN's bit 0 is set at `0x400a43a0` when the count
  reaches the master length. In the PER TRACK 64/64 run, T1's wrap and the
  master step that set bit 0 were in the same tick. The comparator
  (`0x4000b2ce`) fired that mask 3,210 port samples later, and the take armed
  at `0x307b0`, the same sample as T2's step-1 trig. So the class is not
  evaluated a step ahead of the step it fires on. The whole sequencer runs
  one step ahead of the audio.
- **Subframe.** The frame code (`0x4000aee0..`) turns each timestamp into a
  due flag (`0x80001798 + i`) and an in-frame offset (`0x800017d6 + i`). For
  buffer 0 those are `0x800017d3` and `0x80001811`; for buffer 1,
  `0x800017d4` and `0x80001812`. The comparator writes `0x46c7e9fa[t] = cmd |
  offset`. At 240 BPM the 64-step loop points are frame-aligned (offset 0).
  At 128 BPM, PLEN and QREC 64 both armed at `0x5629e`, T2's step 1, with
  `0x901e` (offset 14). QREC 16 armed at `0x1999f` = ⌊22,176 + 82,687.5⌋
  with offset 15, and OFF went immediately.
- **Master 256 / track 64** (PER TRACK, 1X, 240 BPM): stock PLEN armed at
  `0xb1ae0`, 256 steps in, not at T1's next loop `0x307b0`. **Master INF**:
  stock PLEN never armed while T2 looped three times.
- **When a track step sounds.** A track step processed at tick P sounds one
  of *its own* steps later; a master-step mask fires one *master* step later.
  Both carry the same constant of about one tick. Measured at master 1X
  (6 ticks), T2's step 1 against the tick its step counter went to 0:

  | track scale | ticks a step | own wrap sounds at | master restart sounds at |
  |---|---|---|---|
  | 2X | 3 | P + 3 (+1) | P + 3 (+1) |
  | 1X | 6 | P + 6 (+1) | — |
  | 3/4X | 8 | P + 8 (+1) | P + 6 (+1) |
  | 1/8X | 48 | P + 48 (+1) | P + 6 (+1) |

  A master-length restart is applied per track by a countdown
  (`0x400a4bbc..0x400a4be6`; it also calls `0x400a536c`), so that the
  track's step 1 sounds on the master's beat. PLEN's bit 0 already fires
  there. (`0x400a539c`, which clears the per-track wrap counters
  `0x46107918`, runs only on a pattern change.)
- **QREC raw 17 on a stock image.** Nothing clamps it: the bank blob, the
  SRAM mirror (`0x100a54d0`) and the published page (`0x80000cf4`) all hold
  `0x11` after the load. The scheduler stages `class[17]`, which is the word
  past the table: a message buffer `{0x11, pattern, 0x00, 0x15}` that
  `0x400a40fc` posts at transport start, `0x11000015` in the run. Bits 0, 2
  and 4 are always set, so a press fires on the next 2-step boundary (armed
  `0x1713f`, offset 15). That is wrong quantisation, not a stall. The only
  QREC reader is the scheduler (`0x400051bc`). The stock formatter draws
  nothing above 16.

## The cave

Raw 17 is stored in QREC's own byte. A stock image mis-quantises it, which is
harmless, so no spare part byte is needed. One cave
(`tlen_cave.s`, 266 bytes, position-independent) has three entries:

- **cave**, hooked at `0x400a42d0` (`mvs.b d3,d5; move.l #2646000,d6`,
  replayed). This is the master step, after the ladder bits and before PLEN's
  bit 0, with `a2` = the mask and `a4` = the playing pattern's record. For
  each running audio track (`0x80006500[t] == 1`):
  - `tt = ticks[scale[t]]` (`0x8000663e`, `0x400aba50`);
  - `L = length × tt`, where length is the pattern's (`+0x8e53`), or the
    track record's `+0x50` when PER TRACK (`+0x8e55`);
  - `e = step × tt + tick` (`0x800064d0`, `0x800064f0`): the ticks since the
    loop's step 1 was processed.

  It sets bit 17+t when `(e − tt + mt) mod L < mt`, where `mt` is the master
  step's ticks (`d5`). That is the first master step whose mask fires at or
  after the loop start sounds.
- **cls**, a `jsr` over `lea 0x400d8120,a0` at `0x400051cc`, the scheduler's
  class lookup. Raw 17 points the stock indexed read at an 8-entry table, so
  `class = (1 << (17+t)) | 1`: the track's own bit, or PLEN's bit 0 for the
  master-length and pattern-change restarts. Stock never sets mask bits above
  16.
- **fmt**, the QREC slot's formatter word (`0x400d3d9a`, the only reference
  to `0x4003b150`). 17 draws `TLEN`; anything else goes to the stock
  formatter.

Plus the descriptor's QREC count (`0x400d3d6a`) 18 → 19, which the setup
editor clamps by. Raw −1..16 keep their meaning, and saved parts need no
restamp.

The comparator stays stock, so a TLEN take arms through the same path, with
the same subframe, as a PLEN take. The cost is that the timing is the master
step's. On the master's scale that is exact. On another scale the take
starts at the first master step at or after the loop point: late by up to
`mt − 1` ticks, never early. A per-track timestamp would need a comparator of
its own.

## Measured (port, `verify_qrec_tlen`, image `qrec-tlen`, 9 Oct 2026)

240 BPM unless noted. "Next loop point" means T2's arm at the loop start
after the press.

| case | result |
|---|---|
| PER TRACK master 256 / T1 64, 1X | armed `0x307b0`, the next 64-step loop point (stock PLEN: `0xb1ae0`, 256 steps) |
| master INF / T1 64 | the next loop point (stock PLEN: never) |
| NORMAL 64, 128 BPM | `0x5629e`, command `0x901e`: identical to stock PLEN, subframe included |
| master 16 at 1X / T1 32 at 1/8X | the master's restart, every 44,100 samples, pressed before a restart and 200 ms after one (no fire in between) |
| T1 16 at 3/4X over master INF at 1X | loop starts 1, 2, 3 (ticks 128, 256, 384): 1,837, 918 and 0 samples late = 4, 2, 0 ticks, the first master step at or after each |
| T1 16 at 2X (48 ticks) | 0 late; the bit is set at the master step before the wrap is processed |
| T1 15 at 2X (45 ticks) | 3 ticks (1,378–1,379 samples) late on odd loops |
| pattern change queued while waiting (CHG 16) | armed at the change (step 64), ahead of T1's own wrap (96); without the change, at 96 |
| TRIG ONE2, HOLD | the next loop point; HOLD's release stop goes the immediate way (`0x40083826`), as on stock |
| QREC TLEN + RLEN PLEN + TRIG ONE, T1 48 at 1/2X | one arm on the loop point, LIMIT (the end post) 264,600 = one loop, no second arm |
| formatter | 17 → `TLEN`, 12 → `64`, −1 → `OFF` |

Stacked with RLEN PLEN and RECORDER LOOP FIX in one image: no shared site
(ledger), and every case above ran on that image.

The first version of the mask entry set the bit when the loop began within
the last master step. That passed every same-scale case, and fired 2 ticks
early on the 3/4X track. `docs/contributing/FAILURE_MODES.md` has the entry.

## On the unit

Not flashed. One flash would settle it. A click track:

1. A project in PER TRACK mode, master 256 at 1X, about 120 BPM. T2 is a
   STATIC track playing a short click on step 1 of a 64-step loop at 1X. T1
   is 64 steps at 1X, SRC3 = T2, QREC `TLEN`, RLEN `PLEN`, TRIG `ONE`.
2. Control: on stock, a REC3 trig on T1 step 1 records one pass. Save the
   recording to the card. The click's onset in it is the routing latency.
3. On the image: delete the trig. Mid-loop, press TRACK 1 + REC3 (MKII) or
   REC AB with T2 on input AB. Save the recording. The click's onset must
   sit at the control's offset to the sample, and the take must be exactly
   one loop (64 steps' samples).
4. Repeat with T1 and T2 at 3/4X over the 1X master. The onset moves later
   by the table's lateness: 0, 2 or 4 ticks, `2,646,000 / tempo24` samples
   each.

## Not measured

- Hardware timing, including whether the unit's sequencer-to-audio lookahead
  is the port's (a same-scale take shares stock PLEN's path, so it is
  inherited).
- The drawn `TLEN` on the setup screen, and turning the encoder past 256 (the
  count poke is asserted on the image).
- REC CD and REC3 presses. Only REC AB was driven; the three share
  `FUN_400836d8`, which is inferred from the shared handler shape.
- A pattern change without CHG (direct jump, the arranger), slides between
  scales mid-take, and MIDI tracks (QREC is for the eight audio recorders).
- The class bit for track 7 is bit 24, which stock's raw-17 junk class
  (`0x11000015`) also has. A stock QPL raw 17 can't be reached from the
  panel (QPL's count is 18).
