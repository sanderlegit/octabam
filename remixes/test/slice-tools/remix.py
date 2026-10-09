"""stock effects with SLICE TOOLS: TLEN SLICES, CREATE LINEAR and AUTO LINEAR on the SLICE page."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="slice-tools",
    family="mods", proof=Proof.PORT, proof_note="verify_slicetools, 9 Oct 2026",
    doc="stock effects with SLICE TOOLS: TLEN SLICES, CREATE LINEAR and AUTO LINEAR on the SLICE page.",
    modules=("SLICE TOOLS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
