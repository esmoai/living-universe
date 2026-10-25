# Build, test and package

Opening LivingUniverse.html needs a modern browser, not Node or PHP. Development needs Git, Python 3.11+, Node 22+, a C compiler, Clang and LLVM lld-link. Firmware tests additionally need QEMU and matching OVMF/AAVMF firmware.

## Ubuntu 24.04 example

```sh
sudo apt-get update
sudo apt-get install -y build-essential clang-18 lld-18 python3 \
  qemu-system-x86 qemu-system-arm ovmf qemu-efi-aarch64
export CC=clang-18
export LINKER=lld-link-18
```

Use packages suitable for your distribution. Versioned LLVM tools may not appear as unversioned lld-link. CI installs and selects its required linker rather than relying on undocumented runner defaults.

## Web and models

```sh
python3 scripts/build_web.py
node --check validation/extension-syntax.js
node --test source/tests/data.test.js source/tests/universe.test.js
(cd source && npm ci --ignore-scripts --no-audit --fund=false && npm test && npm run build)
```

The offline packager now updates LivingUniverse.html, web/index.html and docs/index.html together. It hash-checks the retained original runtime. Original scene changes require the full Vite build and deliberate adapter review; this wrapper is not a general-purpose compiler. Dependency changes must not silently invalidate the retained runtime.

## Native observer and dual-architecture kernel

```sh
sh scripts/build_bridge.sh
python3 tests/test_bridge.py
python3 tests/test_observer_smoke.py --binary bin/living-universe-observer-linux --web LivingUniverse.html
python3 tests/test_kernel_telemetry.py
sh scripts/build_windows_bridge.sh
sh kernel/scripts/test_host.sh
sh kernel/scripts/build.sh
python3 kernel/scripts/boot_qemu.py --arch both
```

The Windows EXE is unsigned and cross-built without a CRT dependency. CI runs it on Windows in a separate smoke job; that is not a security certification. QEMU uses temporary disk/NVRAM copies, TCG software emulation, no guest networking and no physical disk. Serial fixtures never satisfy the actual boot gate.

## Complete local kit

After building all outputs:

```sh
python3 scripts/package_release.py
```

Packaging fails if a required EXE, observer, EFI or disk image is missing. Outputs are dist/LivingUniverse-Complete-Kit.zip, LivingUniverse-Offline.html, notes and checksums. Source comes from Git's tracked-file list, not a sweep of private archives, arbitrary logs or workspaces. In GitHub CI, explicitly produced emulator logs are included. Review the exact commit and its CI results before claiming a test passed.

Browser regression tests/test_browser.py requires Playwright/Chromium. Earlier tests used an injected document and Canvas2D fallback. WebGL, real touch/VR hardware and physical-board boot need separate acceptance tests. Podman is development tooling, not the operating system under development.
