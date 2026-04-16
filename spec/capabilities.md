# Capabilities

μOS uses object-capability security. Every privileged operation requires an unforgeable capability.

## Definitions

A **capability** is an opaque handle `c` with:

- `id` — unique identifier (kernel-private).
- `privileges` — set of strings, e.g. `{"mem.read", "mem.write", "proc.fork", "fs.read:/home/user/docs"}`. Supports prefix match (`fs.read` authorizes any `fs.read:*`).
- `parent` — the capability from which this one was derived (root caps have `None`).
- `restriction` — optional predicate on call-site (e.g. argument patterns).
- `valid` — boolean; flipped to False by `cap_revoke`, which propagates to descendants.

The capability table is kernel-private. Userland receives opaque tokens; there is no way to construct a capability except by `cap_mint` (root only) or `cap_subset`.

## Privileges (initial set)

```
mem.read       mem.write       mem.admin
proc.fork      proc.join       proc.kill
ipc.send       ipc.recv        ipc.shm
cap.mint       cap.revoke
fs.read        fs.write
net.http       net.http:<host>
introspect.read
tool.<name>    tool.*
```

Tool privileges are namespaced by tool name. A tool `web_search` requires `tool.web_search`; a broadly authorized agent can hold `tool.*`.

## Delegation

```python
# Parent with many privileges narrows capabilities for a child
child_caps = cap.subset(["tool.web_search", "mem.read"])
child = fork(researcher, caps=child_caps, budget_tokens=2000)
```

The child cannot invoke anything outside `{"tool.web_search", "mem.read"}`, even via prompt injection.

## Revocation

```python
cap.revoke(child_caps)        # child's pending/future syscalls now TRAP
```

Revocation propagates down the derivation tree in O(descendants). Already-completed calls are unaffected (revocation is forward-in-time only).

## Threat model

μOS defends against:

1. **Prompt injection** — content read from memory or tools cannot grant privileges; content can only instruct a model, never bypass a capability check.
2. **Untrusted tool output** — return values from tools are inserted at L1 but carry no capability; they cannot authorize subsequent calls.
3. **Rogue sub-agent** — a compromised child can only exercise its delegated subset. The parent revokes on suspicion.
4. **Trace forgery** — traces are append-only and include the capability id per call; a rogue process cannot retroactively plant a legitimate-looking call.

μOS does **not** defend against:

- A compromised LLM driver (the inference backend is the TCB).
- Side channels (timing, content disclosure via error messages).
- Physical or hypervisor-level attacks on the host.

## Audit

Every `CALL` trace record names the cap id. An audit reduces to:

```
filter(T, lambda i: i.opcode == "CALL" and i.cap_id in {cap_ids_of_interest})
```

`introspect_trace` exposes this via syscall. The `/proc/<pid>/calls` pseudofile exposes the same in textual form.

## Example

```python
# Root capability held by the supervisor process
root = cap_mint("tool.*", "mem.*", "proc.*", "net.http", "ipc.*", "introspect.*")

# Researcher gets web + memory-read + no networking beyond a specific host
researcher_caps = root.subset([
    "tool.web_search",
    "tool.fetch",
    "mem.read",
    "net.http:arxiv.org",
])

researcher = fork(do_research, caps=researcher_caps, budget_tokens=10_000)

# Writer gets only memory read/write; no tools, no network
writer_caps = root.subset(["mem.read", "mem.write"])
writer = fork(write_summary, caps=writer_caps, budget_tokens=3_000)
```

Capabilities are boring, well-understood, and powerful. They are also almost completely absent from current agent frameworks.
