# Validation provenance and current limits

The source archive preceding this public release reported local model, native C, sanitizer and Canvas2D browser tests. These reports were **not recorded in a public CI run yet**. They are useful development evidence, not independent hardware verification. New CI results will be linked from GitHub Actions after upload.

Earlier local development results: 34 source/model tests; 123 native Linux bridge checks (repeated under sanitizers); 42 Playwright browser tests under Canvas2D software rendering; 12 shared-C telemetry/parser checks; static x86-64 and AArch64 PE/GPT/FAT checks. Do not aggregate separately repeated checks into distinct coverage. Some results were from authored test fixtures.

**Not demonstrated:** firmware execution of either boot image, successful boot on physical ARM64 or x86-64 hardware, hardware-enforced process isolation, native tool execution, actual WebGL/WebXR/headset behavior, Windows executable execution, broad browser HTTP bridge hookup, full dependency-source build in the original restricted environment or security certification.

When running `kernel/scripts/test_qemu.sh`, preserve both architecture logs and the matching build hashes. Distinguish `PASS`, `FAIL`, and `NOT RUN`; a build that exits zero is not evidence of runtime boot. Release compatibility claims should always be anchored to actual machine/firmware tests.
