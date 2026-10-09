"""Stock effects plus QREC TLEN, stacked with the two other modules on the
recorder path (RLEN PLEN, RECORDER LOOP FIX): the end-to-end take is QREC
TLEN + RLEN PLEN + TRIG ONE."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="qrec-tlen",
    family="mods", proof=Proof.PORT, proof_note="verify_qrec_tlen, 9 Oct 2026",
    doc="stock effects with QREC TLEN (a manual take on the track's own loop point), "
        "RLEN PLEN and the recorder loop fix.",
    modules=("QREC TLEN", "RLEN PLEN", "RECORDER LOOP FIX",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
