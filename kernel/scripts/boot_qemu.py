#!/usr/bin/env python3
"""C-Native Kernel v0.2: non-destructive x86-64 and ARM64 QEMU UEFI boot gate.

Requires QEMU and UEFI firmware installed on a Linux host. This runs only QEMU
software emulation (TCG) to remain usable on WSL2 and conventional Linux.
No host disk or USB device is opened. The test image and NVRAM are copied into a
temporary directory; serial logs are retained in runtime-tests/.
"""

import argparse
import json
import datetime
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
RESULTS = ROOT / "runtime-tests"

X86_FIRMWARE_PAIRS = [
    ("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
    ("/usr/share/OVMF/OVMF_CODE.fd", "/usr/share/OVMF/OVMF_VARS.fd"),
    ("/usr/share/edk2/ovmf/OVMF_CODE.fd", "/usr/share/edk2/ovmf/OVMF_VARS.fd"),
    ("/usr/share/edk2/ovmf/OVMF_CODE_4M.fd", "/usr/share/edk2/ovmf/OVMF_VARS_4M.fd"),
]
ARM_FIRMWARE_PAIRS = [
    ("/usr/share/AAVMF/AAVMF_CODE.fd", "/usr/share/AAVMF/AAVMF_VARS.fd"),
    ("/usr/share/qemu/edk2-aarch64-code.fd", "/usr/share/qemu/edk2-arm-vars.fd"),
]
ARM_BIOS = [
    "/usr/share/qemu-efi-aarch64/QEMU_EFI.fd",
    "/usr/share/qemu/QEMU_EFI.fd",
]


def firmware(arch):
    if arch == "x86_64":
        code_var = (os.environ.get("CNATIVE_OVMF_CODE"), os.environ.get("CNATIVE_OVMF_VARS"))
        pairs = [code_var] if all(code_var) else []
        pairs += X86_FIRMWARE_PAIRS
    else:
        code_var = (os.environ.get("CNATIVE_AAVMF_CODE"), os.environ.get("CNATIVE_AAVMF_VARS"))
        pairs = [code_var] if all(code_var) else []
        pairs += ARM_FIRMWARE_PAIRS
    for code, var in pairs:
        if Path(code).is_file() and Path(var).is_file():
            return ("pflash", Path(code), Path(var))
    if arch == "aarch64":
        custom = os.environ.get("CNATIVE_QEMU_EFI")
        for path in ([custom] if custom else []) + ARM_BIOS:
            if path and Path(path).is_file():
                return ("bios", Path(path), None)
    return None


def qemu_arguments(arch, disk, fw, temp):
    emulator = "qemu-system-x86_64" if arch == "x86_64" else "qemu-system-aarch64"
    binary = shutil.which(emulator)
    if binary is None:
        raise RuntimeError(f"Missing {emulator}. Install qemu-system-x86 qemu-system-arm (Ubuntu/Debian).")
    common = ["-accel", "tcg,thread=multi", "-display", "none", "-monitor", "none",
              "-serial", "stdio", "-no-reboot", "-nic", "none"]
    if arch == "x86_64":
        args = [binary, "-machine", "q35", "-cpu", "qemu64", "-m", "512M", "-smp", "1"]
    else:
        args = [binary, "-machine", "virt,gic-version=3", "-cpu", "cortex-a57", "-m", "1024M", "-smp", "1"]
    kind, code, var = fw
    if kind == "pflash":
        nvram = temp / f"{arch}-VARS.fd"
        shutil.copyfile(var, nvram)
        args += ["-drive", f"if=pflash,format=raw,readonly=on,file={code}",
                 "-drive", f"if=pflash,format=raw,file={nvram}"]
    else:
        args += ["-bios", str(code)]
    if arch == "x86_64":
        args += ["-drive", f"if=virtio,format=raw,file={disk}"]
    else:
        args += ["-drive", f"if=none,format=raw,id=bootdisk,file={disk}",
                 "-device", "virtio-blk-device,drive=bootdisk"]
    return args + common


def emit(log, text, quiet=False):
    log.write(text)
    log.flush()
    if not quiet:
        sys.stdout.write(text)
        sys.stdout.flush()


def valid_universe_response(segment, arch):
    """Validate an observed response; authored fixtures never count as a boot."""
    if "LU_TEST_FIXTURE" in segment:
        return False
    for line in segment.splitlines():
        if "@LU1 " not in line:
            continue
        try:
            p = json.loads(line.split("@LU1 ", 1)[1])
            expected_arch = "x86-64" if arch == "x86_64" else "AArch64"
            if (p.get("v") != 1 or p.get("source") != "c-native-kernel" or
                p.get("event") != "boot.snapshot" or p.get("stage") != 0 or
                p.get("arch") != expected_arch or p.get("firmware_exited") is not True or
                p.get("user_space_isolation") is not False or p.get("native_tool_execution") is not False):
                continue
            if all(type(p.get(k)) is int and 0 <= p[k] <= 9007199254740991 for k in
                   ("sequence", "conventional_pages", "memory_map_bytes", "descriptor_size")):
                return True
        except (ValueError, TypeError, AttributeError):
            continue
    return False


def run_one(arch, timeout_sec):
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = RESULTS / f"{arch}-{stamp}.log"
    image_name = ("c-native-kernel-dual-uefi.img" if arch == "x86_64"
                  else "c-native-kernel-aarch64-qemu-virt.img")
    orig_image = BUILD / image_name
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        emit(log, f"=== {arch} QEMU boot gate: {stamp} ===\n")
        if not orig_image.is_file():
            emit(log, f"FAIL: Image not found: {orig_image}\n")
            return False, log_path
        fw = firmware(arch)
        if fw is None:
            emit(log, f"FAIL: UEFI firmware missing for {arch}.\n")
            emit(log, "Ubuntu/Debian: sudo apt install ovmf qemu-efi-aarch64\n")
            return False, log_path
        with tempfile.TemporaryDirectory(prefix="cnative-uefi-") as tmp:
            temp = Path(tmp)
            disk = temp / "boot-test.img"
            shutil.copyfile(orig_image, disk)
            try:
                cmd = qemu_arguments(arch, disk, fw, temp)
            except RuntimeError as exc:
                emit(log, f"FAIL: {exc}\n")
                return False, log_path
            emit(log, f"Firmware type: {fw[0]}; firmware: {fw[1]}\n")
            emit(log, "Boot image is a temporary copy; QEMU networking disabled.\n")
            emit(log, "--- BEGIN SERIAL OUTPUT ---\n")
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, bufsize=0, start_new_session=True)
            except OSError as exc:
                emit(log, f"FAIL: Could not launch QEMU: {exc}\n")
                return False, log_path
            assert proc.stdout is not None and proc.stdin is not None
            # Stage expected serial output and replies, checked only after sending.
            phases = [
                (None, "C-NATIVE BARE-METAL KERNEL v0.2", "kernel> "),
                ("help", "commands: help status mem cpu universe halt", "kernel> "),
                ("status", "firmware boot services exited", "kernel> "),
                ("cpu", f"architecture: {'x86-64' if arch == 'x86_64' else 'AArch64'}", "kernel> "),
                ("mem", "UEFI conventional RAM remaining:", "kernel> "),
                ("universe", "@LU1 ", "kernel> "),
            ]
            phase = 0
            segment = ""
            deadline = time.monotonic() + timeout_sec
            success = False
            try:
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        break
                    readable, _, _ = select.select([proc.stdout], [], [], 0.25)
                    if not readable:
                        continue
                    chunk = os.read(proc.stdout.fileno(), 8192)
                    if not chunk:
                        break
                    decoded = chunk.decode("utf-8", errors="replace")
                    emit(log, decoded, quiet=True)
                    segment += decoded
                    if len(segment) > 131072:
                        segment = segment[-131072:]
                    _, expected, prompt = phases[phase]
                    if (expected in segment and prompt in segment[segment.find(expected):]
                            and (phases[phase][0] != "universe" or valid_universe_response(segment, arch))):
                        phase += 1
                        if phase == len(phases):
                            success = True
                            break
                        cmd_text = phases[phase][0] + "\n"
                        try:
                            proc.stdin.write(cmd_text.encode("ascii"))
                            proc.stdin.flush()
                        except (BrokenPipeError, OSError):
                            break
                        segment = ""
                emit(log, "\n--- END SERIAL OUTPUT ---\n")
                if success:
                    emit(log, f"PASS: {arch}: boot banner + help/status/cpu/mem/universe command responses verified.\n")
                else:
                    msg = (f"FAIL: {arch}: did not reach expected phase {phase + 1}/"
                           f"{len(phases)} within {timeout_sec}s; QEMU exit={proc.poll()}.\n")
                    emit(log, msg)
                return success, log_path
            finally:
                # Shut down only the QEMU process group spawned by this test.
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=["x86_64", "aarch64", "both"], default="both")
    parser.add_argument("--timeout-x86", type=int, default=90)
    parser.add_argument("--timeout-arm", type=int, default=180)
    args = parser.parse_args()
    arches = ["x86_64", "aarch64"] if args.arch == "both" else [args.arch]
    outcomes = []
    for arch in arches:
        timeout_sec = args.timeout_x86 if arch == "x86_64" else args.timeout_arm
        ok, log_path = run_one(arch, timeout_sec)
        outcomes.append(ok)
        print(f"{arch}: {'PASS' if ok else 'FAIL'} | log: {log_path}")
    if all(outcomes):
        print("PASS: BOTH ARCHITECTURES VERIFIED" if len(outcomes) == 2 else "PASS: BOOT GATE VERIFIED")
        return 0
    print("FAIL: Runtime verification incomplete; inspect runtime-tests/*.log")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
