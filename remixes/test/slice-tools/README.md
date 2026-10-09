# `slice-tools` — SLICE TOOLS

One ColdFire module and the stock effects.

## What is in it

- **SLICE TOOLS** — the audio editor's SLICE page gains:
  - CREATE SLICE GRID > TLEN SLICES;
  - SLICE menu > CREATE LINEAR;
  - SLICE menu > AUTO LINEAR.

  [The module page](../../../modules/slice-tools/README.md) says what each
  one does and what is measured.
- **The 14 stock effects**, listed so the FX2 chooser is stock's.

## Status

Under the port: `tools/verify/verify_slicetools.py` (9 Oct 2026). Not flashed.

## Build

```bash
make image REMIX=slice-tools BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=slice-tools` runs every gate first.
