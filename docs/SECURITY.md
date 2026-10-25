# Security and privacy: prototype, not a production sandbox

## Verified runtime scope

Release v0.3.1-prealpha at commit 10272c09f668cd528b182b5f912dd369b823a2c5 passed public CI run 40170633060, including the actual Windows observer smoke test and both configured QEMU boots. This supersedes the original local staging note that Windows and firmware execution had not been tested. See [Validation](VALIDATION.md). The v0.3.2 publication refresh updates these status documents; it does not add kernel isolation or expand hardware support.

## What this implementation constrains

The browser reads files explicitly selected through its file picker. It makes no external asset requests or default observer connection. Imported values enter the interface as text, not executable markup. Payload validation bounds depth, element count and size. The local permission helper is a data-model restriction, not a security boundary against hostile JavaScript.

The native C observer binds to IPv4 loopback 127.0.0.1 and accepts only its exact Host and permitted Origin. Sensitive snapshots require a per-launch OS-generated 256-bit key. Duplicate authority headers, unexpected methods/paths, body framing and oversized requests are rejected. It grants no CORS access, proxying, shell execution or host-write endpoint. Connection and response sizes/time are bounded.

Only the explicitly selected HTML and optional regular log are opened. Final-component symlinks/reparse points and nonregular files are rejected; this is not proof that every ancestor directory is symlink-free. Logs are pre-opened read-only. The process retains its normal user's OS privileges. It is not confined by a capability kernel, VM, seccomp jail, AppContainer or separate restricted account.

## Limits and mitigations

The Windows x64 binary is cross-built and unsigned. Its native Windows CI smoke checks prove the tested startup and endpoint behavior, not broad OS-version compatibility, an independent audit or a hardened exploit-mitigation toolchain. ASLR/NX flags are enabled. Linux builds use stack protection, PIE and RELRO. These mitigations do not make C memory-safe. Neither observer should run elevated, and users should never disable OS protections to launch it.

Compiler correctness, local-malware resistance, malicious browser extensions, hostile same-origin scripts, multiuser isolation, cache side channels, comprehensive denial-of-service resistance and cryptographic boot attestation remain unproven. A single-threaded observer may be delayed by local clients despite per-connection timeouts. Sanitizers and malformed-input checks are not a sandbox-escape assessment or security certification.

## Privacy and data ownership

Workspace exports and explicit browser-local saves contain plaintext payloads, notes, retained history and original imported bytes. They are not encrypted or redacted. Removing a browser save does not erase exported backups or current session RAM. Do not import credentials or confidential logs unless you intend to handle them accordingly. The application includes no analytics, account service or unsolicited telemetry upload.

Serial reports are unauthenticated source assertions. A fixture marker avoids accidental confusion but cannot stop deliberate forgery. A SHA-256 inventory checks contents only relative to a trusted manifest; it is not a signature or proof of identity. The default kernel images and Windows EXE are unsigned.

Keep the observer on a trusted development machine. Do not forward its port, bind it to a LAN, expose it through a tunnel, remove Origin checks or share its session URL. The client removes the URL fragment after reading the key, but the URL initially exists in the console and browser history. A malicious extension or same-origin script could read in-memory data.

## Future native authority gate

Before any host/kernel mutation: implement hardware-enforced address spaces, capability delegation/revocation, checked IPC, resource budgets, crash containment and independent negative tests on both ISAs. Keep external interpreters, parsers and native plugins outside privileged kernel memory. Permissions must be enforced at the native boundary, not inferred from a visual button or model confidence.
