# Roadmap and stage gate

## Delivered in this milestone

- Preserved original visual runtime plus selectable, channel-aware data overlay.
- Exact selected-file bytes, JSON property inspection, derived fragment ancestry.
- Voxel bit lens, hex grid, accessible bit controls and camera navigation.
- Local curation, undo/redo, bounded immutable recall, explicit workspace archives.
- Opt-in renderer readings and bounded read-only hosted C observer.
- Shared Stage 0 serial contract and rebuilt x86-64 / AArch64 images.
- Host, model, parser and software-rendered UI validation with explicit limits.

## Pending before claiming runtime platform support

Actual UEFI boots on both emulator targets; real-machine boot/driver validation;
Windows observer execution; WebGL/WebXR scene and headset regression; HTTP-browser
native observation hookup; independent security review. ARM64 portable source and
kernel builds do not imply every ARM64 board or locked device can boot this image.

## Next kernel milestone

Independent memory management, exception and interrupt handling, minimal isolated
user-space tasks and a checked capability/IPC design, implemented in parallel on
both architectures. Only after negative isolation tests: narrow tool executors,
quotas, revocation, watchdogs and independently recoverable services.

## Later universe capabilities

Arbitrary relationship graph editing, persistent event storage beyond the local
bounded archive, stable cross-machine identities, authenticated observations,
consented sensors, richer native telemetry, in-headset detailed instruments and
capability-mediated actions. Agent suggestions should be previews with evidence;
execution authority belongs at the native boundary, never to a UI confidence score.

The bare-metal display/input/GPU stack and a native renderer/application host are
separate major work. The delivered browser experience does not magically run
inside the Stage 0 kernel. RISC-V, broader board drivers and accelerators remain
future explicit ports, not universal compatibility promises.
