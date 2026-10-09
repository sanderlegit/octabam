# `qrec-tlen` — QREC TLEN on the recorder path

QREC TLEN with the two other recorder modules and the stock effects. For
anyone who records loops by hand in PER TRACK mode and wants a take to start
on the track's own loop point, not the master's.

## What is in it

- **QREC TLEN** — QREC value `TLEN`, past 256. A manual take (TRACK + REC)
  starts on the recording track's next loop point. Stock PLEN waits for the
  master, and at master INF never starts. `modules/qrec-tlen/README.md`.
- **RLEN PLEN** — RLEN value `PLEN`: one loop of the track's pattern on its
  own scale. With TLEN and TRIG `ONE`, one press records exactly one loop,
  starting on it. `modules/rlen-plen/README.md`.
- **RECORDER LOOP FIX** — the recorder loop click.
  `modules/recorder-loop-fix/README.md`.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Measured under the ColdFire port (`python3 tools/verify/verify_qrec_tlen.py
qrec-tlen` with `OT_PROJECT=<dir>`, 9 Oct 2026). Not flashed.

## Build

```bash
make image REMIX=qrec-tlen BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) walks from a fresh machine to
a flashed unit. `make check REMIX=qrec-tlen` runs every gate first.
