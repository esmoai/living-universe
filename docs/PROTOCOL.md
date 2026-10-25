# Observation contracts v1

## Evidence vocabulary

`simulated`: authored scene/example data. `imported`: selected bytes/content.
`observed`: readings directly collected by this application or observer.
`reported`: a source asserts a value, e.g. an unauthenticated kernel log.
`derived`: extracted value with parent/provenance. `unknown`: unestablished source.
A restored workspace sets `provenance.recorded = true`; an observed record then
renders as a recorded observation, not a live measurement. These labels communicate
origin, not cryptographic confidence.

## Shared kernel line

One bounded ASCII JSON object per line, after the exact `@LU1 ` prefix:

```json
{"v":1,"source":"c-native-kernel","event":"boot.snapshot","stage":0,"arch":"AArch64","sequence":1,"firmware_exited":true,"user_space_isolation":false,"native_tool_execution":false,"conventional_pages":4113,"memory_map_bytes":120,"descriptor_size":40}
```

The JSON above is an **authored contract example**, not a captured boot.
`arch` is `x86-64` or `AArch64`. Numeric fields are nonnegative safe integers.
`conventional_pages` counts UEFI conventional-memory pages in the final firmware
map. It is not free memory from a functioning allocator. Sequence is process/boot
local, not globally unique. Host-clock timestamps added on import are receipt times,
not a claim that the kernel had a synchronized wall clock.

The importer rejects claims that Stage 0 isolation/execution already exist.
At most the newest 24 unique accepted records from one import are emitted. A log
starting a line with `# LU_TEST_FIXTURE` classifies its reports as simulated.
This is an accidental-confusion aid, not authentication. Dedupe IDs use a local
noncryptographic locator hash and do not define a global object identity.

## Hosted bridge

GET `/` or `/LivingUniverse.html`: the selected HTML bytes, no directory listing.
GET `/api/snapshot`: requires `X-Universe-Key: <64 lowercase hex characters>`.
All other methods/paths are rejected. No POST, mutation, exec, proxy or path query.
Use the exact printed `127.0.0.1:<port>` origin; keys are not query parameters.

Snapshot fields: the exact required schema is
`living-universe.bridge`, `version=1`, `read_only=true`, plus architecture,
host_os, scope, uptime_ms, cpu_time_ms, requests_handled, peak_rss_bytes,
execution_available=false, filesystem_write_available=false, log_attached,
log_read_ok, log_tail_only and serial_log. `peak_rss_bytes` is null on Windows.
Serial tails are at most 128 KiB. The ASCII `@LU1` payload is the supported kernel
wire format; arbitrary non-ASCII bytes in a log are escaped bytewise by the bridge.
Use the file importer for preservation of the entire original log encoding.

The UI polls only after an explicit Connect, every 5 seconds, pausing during
recall and when hidden. CPU time is cumulative observer-process time in ms.
No endpoint claims total machine usage, native program execution or kernel access.

## Portable workspace

`schema=living-universe.workspace`, `version=1`. `pool` holds normalized immutable
record revisions. `frames[].objects` and `current` are integer indices into that
pool. `blobs` contains base64 original selected-file bytes and their sizes.
`authority` states `none; workspace data only`. Unknown permission-like fields do
not grant authority. Imports validate all references before replacing state.

Bounds: 160 current objects, 64 frames, 4096 pooled revisions on import, 256 KiB per
selected file/payload, 1 MiB total attached bytes, 8 MiB workspace archive, 2000
annotation characters. An export/import does not persist Undo/Redo stacks, selected
UI view, panel positions, bridge keys or live connections. The copied event history
is retained. Resetting panel layout does not alter underlying data.
