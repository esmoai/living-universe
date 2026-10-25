#!/usr/bin/env python3
"""Build a complete runnable kit from this commit, not private backup archives."""
import hashlib, json, os, re, stat, subprocess, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'dist'
version = (ROOT/'RELEASE_VERSION').read_text().strip()
if not re.fullmatch(r'v\d+\.\d+\.\d+-prealpha',version):
    raise SystemExit('Invalid pre-alpha release version')
sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
tracked = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
source = [p for p in tracked if p]
generated = ['LivingUniverse-Observer.exe','bin/living-universe-observer-linux',
    'kernel/build/x86_64/BOOTX64.EFI','kernel/build/aarch64/BOOTAA64.EFI',
    'kernel/build/aarch64_virt/BOOTAA64.EFI','kernel/build/SHA256SUMS',
    'kernel/build/c-native-kernel-x86_64-uefi.img',
    'kernel/build/c-native-kernel-aarch64-uefi.img',
    'kernel/build/c-native-kernel-aarch64-qemu-virt.img',
    'kernel/build/c-native-kernel-dual-uefi.img']
for name in generated:
    p=ROOT/name
    if not p.is_file() or p.is_symlink():
        raise SystemExit('Missing generated deliverable: '+name)
evidence = [name for name in ['validation/bridge-tests.json',
    'validation/kernel-telemetry-tests.json','validation/model-tests.tap'] if (ROOT/name).is_file()]
if os.environ.get('GITHUB_ACTIONS') == 'true':
    evidence += [p.relative_to(ROOT).as_posix() for p in (ROOT/'kernel/runtime-tests').glob('*.log')]
files = sorted(set(source+generated+evidence))
OUT.mkdir(exist_ok=True)
prefix='Living_Universe_'+version
manifest=[]
kit=OUT/'LivingUniverse-Complete-Kit.zip'
with zipfile.ZipFile(kit,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for name in files:
        p=ROOT/name
        if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(ROOT.resolve()):
            raise SystemExit('Unsafe release file: '+name)
        data=p.read_bytes()
        manifest.append(hashlib.sha256(data).hexdigest()+'  '+name)
        info=zipfile.ZipInfo(prefix+'/'+name,(2026,10,25,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        mode=0o755 if name.startswith('bin/') or name.endswith('.sh') else 0o644
        info.external_attr=(stat.S_IFREG|mode)<<16
        archive.writestr(info,data)
    metadata={'version':version,'source_commit':sha,'kernel_stage':0,
        'scope':'Hosted observer plus experimental boot images; not a complete operating system',
        'windows_signature':'unsigned',
        'runtime_verification':'Consult this commit CI jobs and included logs; compilation alone is not boot verification'}
    archive.writestr(prefix+'/BUILD_INFO.json',json.dumps(metadata,indent=2)+'\n')
    archive.writestr(prefix+'/FILE_SHA256SUMS.txt','\n'.join(manifest)+'\n')
with zipfile.ZipFile(kit) as archive:
    if archive.testzip() is not None:
        raise SystemExit('Release ZIP integrity check failed')
html=OUT/'LivingUniverse-Offline.html'
html.write_bytes((ROOT/'LivingUniverse.html').read_bytes())
notes='''Living Universe %s - complete pre-alpha developer kit

Includes editable source, offline HTML, Windows launchers and unsigned x64 EXE,
Linux observer, both generic UEFI executables, ARM64 QEMU variant, all four
64-MiB boot images, tests, examples, notices and documentation.
Source commit: %s
The kernel remains Stage 0. No physical-hardware or production-security claim.
Never write the disk images to a production disk. Start with QEMU.
Open LivingUniverse.html or Launch-LivingUniverse.bat after extracting the ZIP.
''' % (version,sha)
(OUT/'RELEASE_NOTES.txt').write_text(notes)
(OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
    for p in [kit,html,OUT/'RELEASE_NOTES.txt']))
print('Complete release kit:',kit,'bytes:',kit.stat().st_size,'files:',len(files))
