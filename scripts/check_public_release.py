#!/usr/bin/env python3
"""Fail the public-source gate on tracked archives, secrets, prohibited paths and wrong demo bytes.
Run on tracked files where possible; use filesystem walk before initial git commit.
Conservative release gate, NOT a substitute for full secret/rights reviews.
"""
from pathlib import Path
import hashlib, re, subprocess, sys
ROOT=Path(__file__).resolve().parent.parent
try:
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT,stderr=subprocess.DEVNULL).decode('utf-8').split('\0')
    paths=[p for p in paths if p]
except (FileNotFoundError,subprocess.CalledProcessError):
    paths=[p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not any(x in {'.git','validation','bin','build','node_modules'} for x in p.relative_to(ROOT).parts)]
issues=[]
protected={'reference','private','secrets','validation','bin'}
blocked_ext={'.zip','.7z','.exe','.efi','.img','.iso','.qcow2','.pem','.p12','.pfx','.env','.log','.bundle','.bak'}
for rel in paths:
    p=Path(rel)
    if any(x in protected for x in p.parts):issues.append('private/generated directory: '+rel)
    if p.suffix.lower() in blocked_ext and rel not in {'samples/kernel-contract-fixture.log'}:issues.append('prohibited artifact: '+rel)
    if 'node_modules' in p.parts or p.name.startswith('.env'):issues.append('runtime/dependency material: '+rel)
    if not (ROOT/p).exists():issues.append('missing file: '+rel)
    if (ROOT/p).is_symlink():issues.append('symlink not allowed: '+rel)
    if (ROOT/p).is_file() and (ROOT/p).stat().st_size>2*1024*1024:issues.append('unexpected large tracked file: '+rel)
# Confirm the static public demo stays bit-identical to the tested offline artifact.
for rel in ('docs/index.html','LivingUniverse.html'):
    if not (ROOT/rel).is_file():issues.append('missing static demo: '+rel)
if (ROOT/'docs/index.html').read_bytes() != (ROOT/'LivingUniverse.html').read_bytes(): issues.append('Pages demo does not match root offline HTML')
# Scan text in public source (not vendored minified JS or the license notices) for obvious credentials.
patterns=[('private key block',re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')),
          ('GitHub token',re.compile(r'gh[pousr]_[A-Za-z0-9_]{30,}')),
          ('AWS access key',re.compile(r'AKIA[0-9A-Z]{16}')),
          ('Slack token',re.compile(r'xox[baprs]-[A-Za-z0-9-]{16,}')),
          ('OpenAI key',re.compile(r'sk-proj-[A-Za-z0-9_-]{20,}'))]
for rel in paths:
    if rel.startswith('vendor/') or rel=='THIRD-PARTY-NOTICES.txt':continue
    p=ROOT/rel
    if not p.is_file() or p.suffix.lower() not in {'.md','.js','.py','.c','.h','.sh','.bat','.yml','.yaml','.json','.def','.txt'}:continue
    text=p.read_text('utf-8',errors='replace')
    for label,pattern in patterns:
        if pattern.search(text):issues.append(label+' in '+rel)
if issues:
    print('PUBLIC RELEASE SAFETY GATE FAILED:')
    for issue in issues:print(' -',issue)
    sys.exit(1)
print('PASS: public allowlist policy, obvious secret patterns, static demo identity and file-size caps; review third-party rights separately.')
