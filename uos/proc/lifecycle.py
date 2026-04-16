"""Lifecycle helpers — state-transition validation.

Kept trivial on purpose: the source of truth is the kernel dispatch loop;
this module just documents the legal transitions.
"""
from uos.proc.pcb import ProcState


LEGAL: dict[ProcState, set[ProcState]] = {
    ProcState.NEW:     {ProcState.READY, ProcState.ZOMBIE},
    ProcState.READY:   {ProcState.RUNNING, ProcState.ZOMBIE},
    ProcState.RUNNING: {ProcState.READY, ProcState.BLOCKED, ProcState.ZOMBIE},
    ProcState.BLOCKED: {ProcState.READY, ProcState.ZOMBIE},
    ProcState.ZOMBIE:  set(),
}


def can_transition(src: ProcState, dst: ProcState) -> bool:
    return dst in LEGAL.get(src, set())
