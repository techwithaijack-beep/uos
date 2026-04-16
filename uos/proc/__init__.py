"""Process model — PCB, lifecycle, /proc introspection."""
from uos.proc.pcb import PCB, ProcState
from uos.proc import procfs

__all__ = ["PCB", "ProcState", "procfs"]
