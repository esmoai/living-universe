# Start here: source, website and complete download

The repository contains the full maintained source. The complete runnable kit adds the Windows EXE, Linux observer, native EFI files and all four boot disk images. GitHub's Code > Download ZIP is source-only; gitignored build products belong in release assets.

## Portable experience

Open https://github.com/esmoai/living-universe/releases and download LivingUniverse-Complete-Kit.zip from the newest pre-alpha. Extract the folder, then open Launch-LivingUniverse.bat or LivingUniverse.html. No server, Node runtime, PHP or administrator access is needed for the visual application.

A release appears only after its commit passes the required CI gates. Missing releases mean verification has not completed successfully; inspect Actions rather than assuming success.

Use Just explore to keep the field clear. Drag to orbit; scroll to approach; select a portal or Enter the field. Home returns to source. I opens the floating instruments. Import samples/precision.bin and verify bytes 81 42 00 FF 80 41 and first-byte bits 10000001. Recall is read-only. Annotations and chamber moves affect local records, not source files. Export before closing; no silent save is claimed.

## Optional native observer

Launch-LivingUniverse-Native.bat starts the included unsigned Windows x64 observer. Copy its entire private loopback URL into your browser and explicitly Connect in Instruments. Do not share the URL, run elevated or disable system security. Ctrl+C stops it. No native execution or host-write endpoint exists.

Linux users can run sh launch-native.sh, which compiles with the local C toolchain. The C observer is hosted development tooling, not the bare-metal kernel.

## Website activation

A GitHub Pages 404 is not evidence that runtime source is missing. Set Settings > Pages > Source to GitHub Actions, then run Deploy interactive demo. See docs/PUBLISHING.md. The deployment verifies its source commit via status.json and exposes only static public files.

## Kernel testing

After building, run sh kernel/scripts/test_qemu.sh --arch both. Both architectures remain Stage 0. A successful QEMU test proves only that tested firmware/emulator configuration, not arbitrary hardware support or completed isolation. Do not flash a production drive. See docs/BUILD_AND_TEST.md and docs/FILE_COVERAGE.md.
