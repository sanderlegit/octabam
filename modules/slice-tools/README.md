# `slice-tools` — SLICE TOOLS

A ColdFire module: one DRAM unit, two detours, six grown tables and three
pokes. It adds three things to the audio editor's SLICE page, for a sliced
sample played one slice per step.

| where | what it does |
|---|---|
| CREATE SLICE GRID > **TLEN SLICES** (row 12, after 2 SLICES) | N equal slices, N = the active track's length, clamped to 1..64. In PER TRACK mode that is the track's own length, otherwise the pattern's. It goes through the stock setter `0x40073984(N)`, so the stock refusals, the ZERO-CROSS ALIGN? question and the stock record writer all run as they do for 16 SLICES. |
| SLICE menu > **CREATE LINEAR** | Asks CLEAR TRACK? SURE?. On YES it does five things, in order: saves the track's undo as CLEAR TRACK TRIGS does; clears the active track in the current pattern with stock's CLEAR TRACK TRIGS (`0x40039df4`, mask 1: trigs, trigless trigs, every lock, the trig words); places trigs on steps 1..len; calls stock's CREATE LINEAR LOCKS writer (`0x40073544`), which puts STRT `2*((s-1) mod count)` on each trig and turns SLIC on; turns AUTO LINEAR on for the track. |
| SLICE menu > **AUTO LINEAR:ON / :OFF** | Toggles the active track's flag. The flag lives in the Part, so SAVE PART and SAVE PROJECT keep it (with Octakit the Part is her Kit, and SAVE KIT keeps it: below). While it is on, a trig the step key adds on an **empty** step gets STRT `2*((s-1) mod count)`, unless that step already holds a STRT lock. A message (AUTO LINEAR ON / OFF) confirms the toggle. |

Both SLICE menus carry the two new rows, just before CHANGE VIEW. The menu with no slice selected has 8 rows, the one with a slice selected 11.

The AUTO LINEAR row draws its state. The detour at the opener rewrites the
label buffer every time the menu opens. The list closes before it calls a
row's handler (`0x4006d8f4`), so the label never needs rewriting while the
menu is open; the toggle confirms itself with a message instead.

Slice k plays when STRT = 2k with SLIC on (voice start `0x4000f63e`: slice =
STRT >> 1, clamped to count − 1). Steps past the last slice wrap.

AUTO LINEAR fires only on the step key's add-to-empty branch
(`0x40051970..0x40051afa`). Nothing else reaches the hooked instruction:
- a removal and the trigless path branch away before it (the trigless path
  rejoins at `0x40051afc`, after it);
- MIDI tracks leave at `0x40051006`;
- another trig mode (`0x46c7dd26` ≠ 0) leaves at `0x400516da`.

Live recording, copy/paste and MIDI-in notes write trigs through other
code. That they never pass `0x40051aea` is read from the code: the gate
measures removal, trigless and MIDI-track adds, not those three.

## Refusals

| action | refuses when | message |
|---|---|---|
| TLEN SLICES | the stock setter refuses (the recorder slot records, no sample) | stock's |
| CREATE LINEAR | the menu's stock guards fail | stock's |
| CREATE LINEAR | the editor's sample is not the active track's: the editor's kind is not STATIC/FLEX, or it differs from the track's machine, or the slot differs | NOT THIS TRACK |
| CREATE LINEAR | the sample has no slices | NO SLICES |
| AUTO LINEAR | the active track is not STATIC or FLEX (for THRU, NEIGHBOR and PICKUP the slot bytes are live) | NO SAMPLE TRACK |
| the step key | the flag is off, the machine has no sample slot, or the slot has no slices | (none: the add stays stock) |

Stock's writer takes the slice count from the EDITOR's slot and writes the
locks to the ACTIVE track. CREATE LINEAR therefore checks that the two
agree before it clears anything. If they differ it refuses rather than
clear one track for another's sample.

## Measured (under the port, `verify_slicetools`, 9 Oct 2026)

`tools/verify/verify_slicetools.py REMIX`, an image gate, ran on
`slice-tools`. It built a fixture from a copy of a real project
(`PROJECT 2025`):
- T1 FLEX on slot 1: a 2 s sine with five slices in `markers.work`;
- A01 LEN 12, NORMAL mode;
- T1 trigs on 1 and 3, a STRT lock 0x20 on the empty step 7, a trigless
  trig with a lock on 20;
- T1's SLIC off and the flag 0 in every part (SLIC off since 10 Oct 2026,
  so that CREATE LINEAR's SLIC write is seen).

Every action below was driven with the panel's own keys: AED, the SLICE
page, YES, DOWN, YES. Results are RAM dumps of the bank's records and
their SRAM twins.

- **TLEN SLICES** wrote 12 slices over the trim range. Its slice record
  equals stock's 12 SLICES byte for byte. With PER TRACK and T1 LEN 6
  (poked), it equals stock's 6 SLICES byte for byte.
- **CREATE LINEAR**:
  - trig mask `0xfff` (steps 1..12), every other mask 0;
  - STRT `0 2 4 6 8 0 2 4 6 8 0 2`, every other lock byte of the track
    0xff (step 7's and step 20's are gone);
  - SLIC (`part + 0x1e1`) 1 and the flag 1, bank and SRAM alike.
- **CREATE LINEAR** on a sample with no slices left the track and the flag
  as loaded.
- **AUTO LINEAR**, in grid recording:
  - step 9 got STRT 6; step 11 got 0 (wrapped at 5); step 18 on page 2
    (LEN poked to 32) got 4;
  - step 7 kept its 0x20;
  - removing step 1, a trigless trig (FUNC + trig 10) and a MIDI track's
    trig 4 wrote no lock;
  - the same keys with the flag off placed the same trigs and wrote no
    lock;
  - the SRAM twin equals the bank.
- **The label** read `AUTO LINEAR:OFF` at the first open and
  `AUTO LINEAR:ON` once toggled, from both menus. The 8-row menu was
  reached with the slot's count poked to 0: opening the editor selects
  slice 0 of a sliced sample, so a sliced sample always gets the 11-row
  menu.
- **Save and reboot**: CREATE LINEAR, then PROJ > SAVE PROJECT. The flag
  is 1 at T1's byte of part 1 in `bank01.work` and `bank01.strd` on the
  card. A second boot from that card loads the flag, SLIC, the trigs and
  the locks as saved. (Remix `slice-tools`, no Octakit; with Octakit see
  below.)
- **The flag byte** was write-watched on its own boot, bank and SRAM.
  T1 went FLEX → THRU through SELECT MACHINE TYPE, then the AED key and the
  slot list's YES were pressed on the THRU track, then T1 went back to
  FLEX. Every write logged after the module's own was from the module.
  Stock wrote nothing there. The editor's kind went to 2 while T1 was THRU
  (`0x40083c8e` hands the editor `slot[machine]`, which is the flag byte).
  The flag read 1 at the end.
- Before the module's first write, stock writes the byte only at boot and
  at load: the part init `0x400056b4`, the file parser `0x400165dc`, and a
  long store at `0x400208b4` over the SRAM twin.

## With Octakit (10 Oct 2026)

This branch carries no Octakit module (main has none); the rig lineage does
(`modules/octakit`, [emuyia/ems-octakit](https://github.com/emuyia/ems-octakit)),
and the unit is written for both: without her runtime her symbols link as 0
and `flag_set` is the stock write alone (measured here: `verify_slicetools
slice-tools`, the reboot keeps the flag and SLIC).

With Octakit in the image a Part is a Kit in her
own store, and the working part is her workspace Kit. Measured under the
port on `bottleservice-pf` (RIGPF12B, the rig lineage: branch
`rig-slice-qrec`; this branch has no remix with both), PROJECT 2025
fixture, write and PC watches on her runtime:

- **A reboot stages her SAVED Kit over the part** (`gk_workspace_prepare` →
  `gk_stage_canonical`, the copy `gk_copy_payload_long_loop`). PROJ > SAVE
  PROJECT writes `kits3a`/`kits3b` from her saved Kits; only SAVE KIT
  (`gk_descriptor_begin_promotion`, then `gk_persistence_v3_mark_kit_dirty`)
  copies the working part into them. So any Kit edit not saved with SAVE
  KIT is gone after a reboot: CREATE LINEAR then SAVE PROJECT, rebooted,
  read the flag 0 **and stock's SLIC 0** (SLIC is written by stock's
  linear-lock writer, which Octakit wraps with her own prepare/finish). The
  bank files held 1 for both; she does not read them for the part.
- **With SAVE KIT the flag lasts the reboot.** CREATE LINEAR, SAVE KIT
  (FUNC+PART, YES, YES), SAVE PROJECT, reboot: flag 1, SLIC 1, trigs and
  locks as saved; her saved Kit holds both.
- **The write goes through her editing functions.** `flag_set` opens her
  workspace the way her wrapper of stock's linear-lock writer does
  (`gk_slice_lock_prepare` / `_finish` in her `slice_lock_operations.S`):
  `gk_stock_current_context_validate`, `gk_workspace_prepare` (bank,
  pattern, current Kit, flags 0; refused unless it returns the workspace
  already open and the current part), `gk_physical_acquire`, then
  `gk_descriptor_store_byte` for the flag (it also writes a pending copy
  when she has one), stock's own SRAM twin store and part/bank dirty marks,
  `gk_workspace_mark_dirty_pending`, `gk_workspace_commit_update`,
  `gk_descriptor_release`. Her symbols are `.weak` in the unit: without her
  runtime they are 0 and the stock write runs alone, as before. If she
  refuses, what she opened is closed as her wrapper closes it
  (`gk_descriptor_release`, `gk_workspace_abort_update`) and the stock
  write runs.
- **What that changes, measured:** after AUTO LINEAR alone her workspace
  is dirty (`__gk_workspace_dirty` 1), as after a wrapped stock edit; the
  module before this change left it 0 (the same gate on RIGPF11B fails
  there). Her saved Kit still reads 0 until SAVE KIT.
- **Kit operations with the flag**, no halt in any: AUTO LINEAR alone then
  SAVE KIT, and on a named Kit the quick save (FUNC+PART held, YES): her
  saved Kit reads 1. Saved as 1, toggled to 0, FUNC+CUE: 1. Saved as 1,
  LOAD KIT 2 (its own 0), LOAD KIT 1: 1. Set and not saved, LOAD KIT 2,
  LOAD KIT > UNDO KIT: 1, still dirty. Part and SRAM twin agree in every
  case.
- **Inferred, not measured:** what her dirty state changes for a user. Both
  SAVE KIT paths above saved the flag with a clean workspace as well. Her
  `gk_part_edit_quick_save` (`part_edit.S`) skips the save of a clean
  workspace; no gesture driven here reached it.

## Not measured

- **Hardware.** Nothing has been flashed.
- **What a THRU track does with the flag at 1.** The editor is handed
  kind 2, slot 1. Opening the AED there ran without a fault under the port;
  what it draws was not looked at.
- **Writes to the flag byte by paths the watch run did not drive.** One
  stock writer is in the image: `0x400795c0` stores `slot[editor kind]`.
  Driving the slot list's YES on a THRU track did not reach it. Not
  driven: Part copy/paste, RELOAD PART, a project's other banks, and a
  sample assigned while the editor is on a THRU track. If any of them
  writes `slot[2]`, the flag of a STATIC/FLEX track could change. The
  value would still be a slot byte, never 0x80 or more (the validator
  `0x400024b6` zeroes negatives).
- **Live recording, copy/paste and MIDI-in notes.** That they never reach
  the hook is inferred from the code, not measured.
- **The voice playing the slices.** No DSP was run.
- **The NOT THIS TRACK refusal.** Not reached: selecting a track points the
  editor at its sample.
- **Pattern indices.** CREATE LINEAR reads the length through `0x80000004`
  (stock's rule) and writes to `0x100b14d0`. They were equal in every run;
  when they differ, stock's own CREATE LINEAR LOCKS has the same split.

## Where the flag lives, and why

T1..T8's THRU slot byte: `part + 0x2cc + 5t`, value 0/1, and the SRAM twin
at `0x100a4ece + P × 0x18b2 + 0x2cc + 5t`.

**Why this byte.** A STATIC or FLEX track never reads its THRU slot:
- the Part init writes 0;
- the bank file parser copies it verbatim;
- the validator only zeroes negatives;
- the file carries it at `part + 9 + 0x2cc + 5t`.

The flag therefore costs no new file field and needs no project stamp.
AUTO LINEAR refuses to set it on a THRU, NEIGHBOR or PICKUP track.

**Why not the run `tools/remix/schema.py` calls free.** schema.py calls
bank `+0x90492..0x905b2` "the one run known free". That run is
part `+0x1712..0x1832` of each Part, the stock LFO designer's data
(`docs/firmware/LFO.md`). SLICE TOOLS does not use it.

## The stock routines it calls

The unit calls these:

| routine | what it is |
|---|---|
| `0x40073984` | grid setter |
| `0x40073544` | linear-lock writer |
| `0x40039df4` | clear track |
| `0x40029584` | undo |
| `0x400581c4` | confirm |
| `0x4005a2b8` | message |
| `0x400339d8` | lock bitmaps |
| `0x40027e00` | after a bank write |
| `0x4006e2cc`, `0x4006dae4` | the SLICE menu's guards |

In `slice-tools` none of them differs from stock (image diff, 9 Oct 2026).
PLOCKS P2 detours `0x40039df4`; in a remix with it, CREATE LINEAR's clear
also clears the track's page-2 locks, as CLEAR TRACK TRIGS does there.

## Placement

- the unit in the DRAM platform runtime;
- the six grown tables in the ROM cave: 432 B at `0x400d6b80..0x400d6e30`
  in `slice-tools`;
- detours at `0x40072c30` (the opener's `lea 0x4006d94c,%a0`) and
  `0x40051aea` (`move.l #1165,%d4`);
- the counts at `0x40072c56`, `0x40072c74` and `0x40072cea`.

No other module claims these sites (`make modules`, 9 Oct 2026).
