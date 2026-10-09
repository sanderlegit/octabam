"""HOST LOCK -- on T1 and T5 the FX2 chooser changes nothing, so the bus
servers RIG HOSTS put there stay; on T8, in a remix with RETURNS, it
selects only RETURNS (9 Oct 2026), so the master keeps its returns and a
part that lost them can be given them back on the unit.

The rig's servers are hidden (no chooser row) and locked to their host
slot; a pick on T1 or T5 replaced the server and nothing on the unit could
bring it back (RIGPF7BP, 30 Sep 2026; `ot_project.py host` or a new part
did). The FX2 chooser's YES record is repointed to hostlock.s, which answers
NO on those two tracks and YES everywhere else. Stock's select routine and
Octakit's wrapper around it are untouched.
"""

from remix.schema import Category, Gate, Kind, Linked, Module, Proof, SymbolRef


def ids_inc(modules):
    """ID_T8: RETURNS' id when the remix carries it, else 0 (no T8 rule)."""
    t8 = modules["RETURNS"].menu.fx2_id if "RETURNS" in modules else 0
    return f"        .set    ID_T8, {t8}\n"

MODULE = Module(
    name="host-lock",
    key="HOST LOCK",
    kind=Kind.CF_PATCH,
    category=Category.BUS, author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.HARDWARE,
    proof_note="an MKII, RIGPF8BP (bottleservice-pf), 30 Sep 2026: T1/T5 keep their server; verify_hostlock",
    doc="The FX2 chooser changes nothing on T1 and T5 (their bus servers stay) and picks only RETURNS on T8.",
    requires=("RIG HOSTS",),
    linked=(Linked("hostlock", "modules/host-lock/hostlock.s", dram=True, include=ids_inc),),
    symbol_refs=(
        SymbolRef(0x400BC374, 0x40052474, "hostlock", "hl_yes",
                  "the FX2 chooser's YES record: NO on T1 and T5, RETURNS only on T8, the select elsewhere"),
    ),
    gates=(Gate("tools/verify/verify_hostlock.py", venv=True),),
)
