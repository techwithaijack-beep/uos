"""μOS — a kernel for LLM-native computing.

Public API:
    Agent, tool, kernel, Capability, Driver
"""
from uos.sdk.agent import Agent, Result
from uos.sdk.tools import tool
from uos.kernel.capabilities import Capability
from uos.kernel.dispatch import Kernel
from uos.drivers.base import Driver

__version__ = "0.1.0"
__all__ = ["Agent", "Result", "tool", "kernel", "Capability", "Kernel", "Driver"]


def kernel(**kwargs) -> "Kernel":
    """Create a new μOS kernel."""
    return Kernel(**kwargs)
