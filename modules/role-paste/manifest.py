"""ROLE PASTE -- an FX2 page paste or a track paste in the rig keeps the
destination track's role (T1 BusDelay, T5 BusVerb, T8 RETURNS, every other
track SEND); only the sends (DEL, REV) cross.

A page paste copies the effect id with the knobs, so T1's FX2 page pasted
on T2 gave T2 the hidden BusDelay -- a dry pass off its host slot, with a
page that reads like SEND's: the sends did nothing (RIGPF11B, 9 Oct 2026).
HOST LOCK guards the chooser, not a paste. Two detours in stock's page-PASTE
handler (0x4005df40, called whole by Octakit's wrapper) and two in the track
paste (0x4002b988, GRID REC + FUNC + STOP), none at a site her recipe
claims: the head rewrites the clipboard's FX2 for the destination track,
the tail puts the clipboard back. The paste itself, its undo, its dirty
marks and every Octakit check are stock's.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex


def ids_inc(modules):
    """The rig's FX2 ids, from the manifests; ID_T8 is RETURNS' when the
    remix carries it, else 0 (T8 has no role and keeps what it holds)."""
    from remix import registry
    every = dict(registry.modules()); every.update(modules)
    lines = [f"        .set    {name}, {every[key].menu.fx2_id}\n"
             for name, key in (("ID_DELAY", "DELAY SERVER"), ("ID_VERB", "REVERB SERVER"), ("ID_SEND", "SEND"))]
    t8 = modules["RETURNS"].menu.fx2_id if "RETURNS" in modules else 0
    return "".join(lines) + f"        .set    ID_T8, {t8}\n"


MODULE = Module(
    name="role-paste",
    key="ROLE PASTE",
    kind=Kind.CF_PATCH,
    category=Category.BUS, author="dries", author_url="https://github.com/sanderlegit",
    proof=Proof.PORT,
    proof_note="verify_role_paste under the port (bottleservice-pf, 9 Oct 2026); not yet on a unit",
    doc="An FX2 page or track paste keeps the destination's bus role (T1 BusDelay, T5 BusVerb, "
        "T8 RETURNS, else SEND); only DEL/REV cross.",
    requires=("RIG HOSTS",),
    linked=(Linked("rolepaste", "modules/role-paste/rolepaste.s", dram=True, include=ids_inc),),
    detours=(
        Detour(0x4005DF40, H("2f3980000012"), "rolepaste", "rp_page",
               "page PASTE handler head: the clipboard's FX page rewritten for this track's role"),
        Detour(0x4005DFE8, H("70ff2f400004"), "rolepaste", "rp_page_done",
               "page PASTE handler, the join of its exits: the clipboard put back as copied"),
        Detour(0x4002B996, H("2f2f00082f2f0008"), "rolepaste", "rp_track",
               "track paste past its tag check: the clipboard's FX2 rewritten for this track's role",
               pad_to=8),
        Detour(0x4002B9A8, H("70014fef000c"), "rolepaste", "rp_track_done",
               "track paste, the return of its jsr 0x4002b654 (the address Octakit checks stays): "
               "the clipboard put back as copied"),
    ),
    gates=(Gate("tools/verify/verify_role_paste.py", venv=True),),
)
