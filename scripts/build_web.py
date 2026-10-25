#!/usr/bin/env python3
"""Offline, deterministic packager for the retained Source/Destination runtime.
No package installation or network is required. This is deliberately NOT a general
JavaScript bundler: only the checked named-import/export subset used by our modules.
The original, pinned production bundle remains intact except for a narrow adapter.
The editable Vite source also provides a conventional full-source rebuild path.
"""
from pathlib import Path
import re, hashlib
ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'source' / 'src'
# Clean public input: exact original build material without the private backup ZIP.
upstream = ROOT / 'vendor' / 'source-destination'
html_bytes = (upstream / 'SourceDestination.html').read_bytes()
html = html_bytes.decode('utf-8')
if hashlib.sha256(html_bytes).hexdigest() != '9faad85e8fdcaa84c868eab7e9da50f49c4e1a332cc62a9ca09cec853252284f':
    raise SystemExit('Original standalone HTML changed; audit the adapter before rebuilding.')
bundle = (upstream / 'index-JSZFV_jB.js').read_bytes()
original_hash = hashlib.sha256(bundle).hexdigest()
if original_hash != '0f47498180888a022873a2a9b6d21f616c2434317491700007fe23def8b37faf':
    raise SystemExit('Retained runtime changed; rebuild the adapter from source.')
for token in ['Yt=new xg(', 'class Je extends', 'class Xn extends', 'class Yn extends', 'class nr extends', 'class de extends']:
    if token not in bundle.decode('utf-8'):
        raise SystemExit('Retained runtime symbols changed; rebuild adapter from source.')
modules = ['data.js', 'universe-core.js', 'bit-lens.js', 'universe-field.js', 'software-field.js', 'universe-ui.js']
compiled = []
for name in modules:
    code = (SOURCE / name).read_text()
    exports = re.findall(r'export\s+(?:async\s+)?(?:function|class|const|let)\s+([A-Za-z_$][\w$]*)', code)
    def export_list(match):
        exports.extend(x.strip() for x in match.group(1).split(',') if x.strip())
        return ''
    code = re.sub(r'export\s*\{([^}]+)\};?', export_list, code)
    def imported(match):
        fields, module = match.groups()
        key = Path(module).name
        if key not in modules: raise SystemExit(f'Unknown module {key}')
        return f'const {{{fields}}} = require({key!r});'
    code = re.sub(r'import\s*\{([^}]+)\}\s*from\s*[\'"]([^\'"]+)[\'"];?', imported, code)
    code = re.sub(r'\bexport\s+(?=(?:async\s+)?(?:function|class|const|let)\b)', '', code)
    if re.search(r'^\s*(?:import|export)\s', code, re.M): raise SystemExit(f'Unsupported module syntax in {name}')
    compiled.append(f'{name!r}: function(require) {{\n{code}\nreturn {{{", ".join(dict.fromkeys(exports))}}};\n}}')
adapter = '\nwindow.SourceDestination={experience:Yt,notice:mi,types:{Group:Je,Mesh:de,SphereGeometry:Yn,BoxGeometry:nr,MeshBasicMaterial:Xn,Vector3:Yt?Yt.orbitCamera.position.constructor:null,Color:Gt}};\n'
# The original portable page has one application module script.
pattern = r'(<script\b[^>]*type="module"[^>]*>)([\s\S]*?)(</script\s*>)'
matches = list(re.finditer(pattern, html))
if len(matches) != 1: raise SystemExit('Expected exactly one retained application script.')
m = matches[0]
if 'Yt=new xg(' not in m.group(2): raise SystemExit('Portable runtime symbols do not match the adapter.')
html = html[:m.start()] + m.group(1) + m.group(2) + adapter + m.group(3) + html[m.end():]
script = '(function(){"use strict";const factories={\n' + ',\n'.join(compiled) + '\n};const cache=Object.create(null);function require(id){if(!Object.hasOwn(cache,id))cache[id]=factories[id](require);return cache[id];}require("universe-ui.js").mountUniverse(window.SourceDestination||{});})();'
script = script.replace('</script', '<\\/script')
css = (SOURCE / 'universe.css').read_text().replace('</style', '<\\/style')
html = html.replace('</head>', '<style>\n'+css+'\n</style>\n</head>')
html = html.replace('</body>', '<script type="module">\n'+script+'\n</script>\n</body>')
html = html.replace('<title>Source / Destination', '<title>Living Universe v0.3 / Source / Destination')
(ROOT / 'LivingUniverse.html').write_text(html)
(ROOT / 'web').mkdir(exist_ok=True)
(ROOT / 'web' / 'index.html').write_text(html)
(ROOT / 'validation').mkdir(parents=True, exist_ok=True)
(ROOT / 'validation' / 'extension-syntax.js').write_text(script)
(ROOT / 'validation' / 'web-build.json').write_text(__import__('json').dumps({'original_bundle_sha256':original_hash,'html_sha256':hashlib.sha256(html.encode()).hexdigest(),'html_bytes':len(html.encode()),'new_modules':modules,'network_required':False},indent=2)+'\n')
print(f'Offline HTML built: {len(html.encode()):,} bytes; retained field runtime + {len(modules)} local modules.')
