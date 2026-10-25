# Codex: completeness and truthful verification

Read AGENTS.md, START_HERE.md, docs/ARCHITECTURE.md and SECURITY.md. Maintain both architecture ports and the shared C core. Preserve the spectral world and floating instruments. Do not add an unrestricted executor to make the prototype appear complete.

Inspect exact CI logs, install/select the compiler and linker, and run source/model tests, native API checks, telemetry formatter, both kernel builds, real QEMU gates and Windows EXE smoke validation. Compilation, fixtures, emulation and real hardware are separate claims.

Run scripts/build_web.py to synchronize all three HTML outputs. Stage Pages only through scripts/stage_pages.py. The owner must enable Settings > Pages > GitHub Actions. Check the deployed status.json commit. Files committed to main do not establish a live website.

Build release kits through scripts/package_release.py. They contain source, launchers, Windows EXE, Linux observer, three EFI files and four disk images. Generated artifacts belong in downloads, not a private backup dump. docs/FILE_COVERAGE.md accounts for the input archives. Keep private reference media, notes and workspaces out of public releases.

After both boot gates pass, implement independent memory management, exceptions, allocation, interrupts, user-space domains and checked capabilities on both ISAs. Native rendering/drivers are separate work; today's browser client is not executing inside Stage 0.

Do not force-push, overwrite releases, auto-merge dependency changes, flash host disks, add broad credentials or downgrade tests. Capture failures and distinguish missing prerequisites from actual defects.
