#!/usr/bin/env python3
"""Stage only the standalone demo and explicit public files; no native service."""
import hashlib, json, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '_site'
subprocess.run(['python3', str(ROOT / 'scripts/build_web.py')], check=True)
subprocess.run(['python3', str(ROOT / 'scripts/check_public_release.py')], check=True)
if OUT.exists():
    if OUT.is_symlink():
        raise SystemExit('Refusing a symlink staging directory')
    shutil.rmtree(OUT)
OUT.mkdir()
for source, destination in [('LivingUniverse.html','index.html'), ('LICENSE','LICENSE'),
        ('THIRD-PARTY-NOTICES.txt','THIRD-PARTY-NOTICES.txt'),
        ('samples/precision.bin','samples/precision.bin'),
        ('samples/precision.json','samples/precision.json')]:
    p = OUT / destination
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / source, p)
(OUT / '.nojekyll').touch()
sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
status = {'project':'Living Universe', 'version':(ROOT/'RELEASE_VERSION').read_text().strip(),
    'source_commit':sha, 'demo_sha256':hashlib.sha256((OUT/'index.html').read_bytes()).hexdigest(),
    'native_service_exposed':False, 'kernel_stage':0}
(OUT/'status.json').write_text(json.dumps(status,indent=2)+'\n')
print('Staged public static website only:', OUT)
