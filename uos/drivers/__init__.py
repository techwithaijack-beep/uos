"""LLM drivers — the CPUs of μOS.

A Driver.think(prompt, tools, max_tokens) returns (response_text, usage_dict).
Implement your own by subclassing `Driver` in drivers/base.py.
"""
from uos.drivers.base import Driver
from uos.drivers.mock import MockDriver

__all__ = ["Driver", "MockDriver"]
