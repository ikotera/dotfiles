# ACP gateway viewer: show child activity on the running delegate_task card

## Problem

Start a foreground `delegate_task` from an editor connected through `hermes acp`.
The editor receives the parent tool start and eventual result, but no progress in
between. A healthy long-running delegation looks like a stalled call. The missing
update is reproducible at the ACP `session/update` boundary without running Zed.

## Cause (investigated at `caafe5389ae`)

`gateway/local_viewer_events.py::publish_progress` already publishes child events
on the canonical session stream. `tui_gateway/tool_progress.py::_subagent_payload`
includes a zero-based task index, goal and event-specific details. `parent_id` is
an agent identity, not the parent tool call ID. `delegation_id` is a delegation
identity, not a substitute for a tool call ID. `acp_adapter/gateway_server.py`'s
`GatewayACPAgent._project` does not project `subagent.*` into editor updates.

## Proposed change

- Send `tool_call_update` with status `in_progress` against the existing parent's
  editor card. Replace its content with the most recent 12 progress lines. The
  normal tool completion still owns the terminal status and result.
- Prefer an explicit parent tool call ID if available; otherwise use the most
  recently opened `delegate_task` in the same session **and admission**. Concurrent
  delegations in one admission are ambiguous without upstream call IDs. Ignore
  detached/background events rather than inject them into another turn or into
  the assistant's reply.
- Show queued/started goals, tool previews, batched progress, and child outcome
  with elapsed seconds. Respect missing reasoning text, redact before truncating,
  and do not forward the child's output or raw payload.
- Coalesce bursts per card over 0.5 seconds; deliver trailing updates even when
  the stream goes quiet. Flush at child/parent completion and abandoned-call
  cleanup. Discard queued updates on disconnect. A display failure must not
  stop the gateway event pump or fail unrelated prompt waiters.
- Scope: gateway-backed ACP viewer only. No protocol or gateway publisher change.

## Tests

`python -m pytest tests/acp_adapter/test_gateway_subagent_progress.py -q`
checks the serialized editor update, bounded snapshots, coalescing and idle
flush, routing, redaction and withheld reasoning, normal and abandoned closure,
background events, disconnect, and a failing editor connection. Run
`python -m pytest tests/acp_adapter -q` for the broader adapter regression suite.
Manual verification in Zed is still needed.
