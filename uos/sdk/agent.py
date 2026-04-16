"""Agent — the ergonomic ReAct-style wrapper over the kernel.

Most users will interact with μOS through Agent. Internally Agent runs a
THINK→CALL loop, parsing tool calls out of the model's text output in a
very simple protocol:

    CALL <tool_name> <json_args>           # one call
    DONE <final_answer>                    # terminate

This parser is intentionally dumb. Drivers that expose native tool-use can
override by emitting structured tool_calls; the agent will pick those up via
`usage["tool_calls"]`. See examples/ for how to teach a model the protocol.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
import json
import re

from uos.kernel.dispatch import Kernel
from uos.kernel.capabilities import Capability
from uos.kernel.trace import Trace
from uos.sdk.tools import Tool
from uos.proc.pcb import PCB


_CALL_RE = re.compile(r"^\s*CALL\s+(\w+)\s*(.*)$", re.MULTILINE)
_DONE_RE = re.compile(r"^\s*DONE\s*(.*)$", re.MULTILINE | re.DOTALL)


_PROTOCOL_PRELUDE = """\
You are a μOS agent. You respond with one of:

  CALL <tool_name> <json-args>
  DONE <final answer>

Tools available: {tools}

Rules:
- Each response is exactly ONE CALL or ONE DONE line.
- <json-args> is a JSON object, e.g. {{"a": 1, "b": 2}}.
- Use DONE when you have the final answer.

Goal: {goal}

Observations so far:
{observations}
"""


@dataclass
class Result:
    answer: Any
    trace: Trace
    pid: int
    tokens_consumed: int


@dataclass
class Agent:
    """Convenience wrapper: one goal → one process → one answer."""
    goal: str
    tools: list[Tool] = field(default_factory=list)
    driver: Any = None                    # a Driver
    budget_tokens: int = 10_000
    max_steps: int = 20
    l1_capacity: int = 32
    privileges_extra: list[str] = field(default_factory=list)

    def run(self) -> Result:
        k = Kernel(driver=self.driver, l1_capacity=self.l1_capacity)
        for t in self.tools:
            k.register_tool(t.name, t.fn, token_cost=t.token_cost)
        tool_privs = [f"tool.{t.name}" for t in self.tools]
        cap = k.root_cap().subset(tool_privs + [
            "mem.read", "mem.write", "introspect.read",
        ] + list(self.privileges_extra))

        agent_body = _make_body(self.goal, self.tools, self.max_steps)
        pcb = k.spawn(self.goal, body=agent_body, caps=cap,
                      budget_tokens=self.budget_tokens)
        exit_value = k.run(pcb)
        return Result(
            answer=exit_value,
            trace=k.trace,
            pid=pcb.pid,
            tokens_consumed=pcb.tokens_consumed,
        )


def _make_body(goal: str, tools: list[Tool], max_steps: int) -> Callable:
    def body(k: Kernel, pcb: PCB) -> Any:
        observations: list[str] = []
        tool_list = ", ".join(t.name for t in tools) or "(none)"
        for step in range(max_steps):
            prompt = _PROTOCOL_PRELUDE.format(
                tools=tool_list,
                goal=goal,
                observations="\n".join(observations) or "(none)",
            )
            resp = k.think(pcb, prompt, max_tokens=256)

            # DONE?
            m_done = _DONE_RE.search(resp)
            if m_done:
                return m_done.group(1).strip()

            # CALL?
            m_call = _CALL_RE.search(resp)
            if m_call:
                name = m_call.group(1)
                args_str = m_call.group(2).strip() or "{}"
                try:
                    kwargs = json.loads(args_str) if args_str else {}
                    if not isinstance(kwargs, dict):
                        kwargs = {"value": kwargs}
                except Exception:
                    observations.append(f"PARSE_ERROR: {args_str!r}")
                    continue
                try:
                    result = k.call(pcb, pcb.caps, name, **kwargs)
                    observations.append(f"{name}({args_str}) → {result!r}")
                except Exception as e:
                    observations.append(f"{name}({args_str}) !! {type(e).__name__}: {e}")
                continue

            # Neither DONE nor CALL → unknown output; capture and continue.
            observations.append(f"UNKNOWN: {resp.strip()[:200]}")

        return observations[-1] if observations else "(no result)"
    return body
