# Architecture and trust boundaries

## Three independent layers

```text
LivingUniverse.html - browser spatial perception and local workspace
    | user explicitly selects read-only observation
    v
Hosted C observer - loopback authenticated snapshots; one chosen serial log
    | reads already-existing log bytes; never sends kernel commands
    v
Kernel serial report - shared C encoder, x86-64 + AArch64 Stage 0
```

The visual application is not running inside the bare-metal kernel. The C observer
is a temporary Windows/Linux user-space development tool, not the final authority.
The kernel independently compiles into native UEFI images. No PHP/Node runtime is
required by the UI artifact, observer or boot images; browser JavaScript still
implements the visual client. Development utilities are replaceable tooling.

## Spatial layer

The preserved engine owns the original globe, cube, funnels, curved travel,
procedural chambers and XR session logic. `UniverseField` adds selectable data
meshes and delegates navigation through a narrow adapter. Decorative particles
remain clearly distinct from inspectable records. The fallback separately projects
similar geometry through Canvas2D when WebGL creation fails; it is not full parity.

The instrument panel is deliberately floating, dismissible and movable rather
than a permanent full-screen control dashboard. List-based inspection, keyboard
controls, explicit units and evidence labels remain available when visual effects
are unavailable. Detailed cards are DOM UI, not native headset surfaces.

## Reality graph and memory

Each packet has an ID, channel, chamber, payload, evidence classification,
provenance, note, pin state and local revision. Parent ID + JSON pointer express
fragment derivation. Chamber membership and ancestry are the implemented graph
relationships; arbitrary graph editing, distributed discovery and a global entity
registry are not implemented. IDs survive workspace export/import but are not a
cryptographic or globally coordinated identity system.

States are immutable snapshots using structural sharing. The rolling history
contains at most 64 states. Recall is read-only. There is no OS checkpoint,
transaction-log recovery, remote-machine rewind or unrecorded past reconstruction.
Undo/redo restore local workspace snapshots, not native side effects. New imported
observations between edits may also be absent from an older undo snapshot.

Exact bytes live in a bounded attachment store. A fragment has its own JSON value
and ancestry; its JSON serialization is not falsely described as the parent file's
original encoding. Digest calculation is optional when WebCrypto is unavailable;
the UI does not fabricate hashes. Local locator hashes are not security primitives.

## Hosted observation layer

The C process serves a single HTML document and one authenticated snapshot route.
It has no route to choose files, invoke commands or forward network requests.
The chosen log handle stays fixed even if a different path later replaces the file;
restart deliberately after log rotation. The bridge can observe its own uptime,
CPU time and request count. Linux peak RSS is a process high-water mark. It is not
system-wide memory telemetry. Windows peak RSS is absent/null, not a false zero.

No browser-visible capability label enforces OS isolation. The decisive constraint
in this milestone is **absence of dangerous operations**, plus a deliberately
small observation API. The process still runs with its user's OS privileges.

## Kernel boundary

The shared kernel emits a bounded ASCII JSON record after firmware handoff and on
`universe`. It reports architecture, sequence and final UEFI memory-map figures.
The record explicitly says isolation and native tool execution are false.
This extension adds no system calls, scheduler, VM manager or permission broker.
The original Stage 0 serial polling loop and framebuffer remain.

Next: validate both boot paths, then implement own page tables, exceptions,
interrupts, allocation and user-space domains in parallel. A future isolated
user-space observer can implement this contract. Only a verified capability
boundary may later expose narrow mutation requests. Porting the renderer/display
stack into our OS is separate driver and application-host work.
