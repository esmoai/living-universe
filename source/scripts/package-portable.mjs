import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseAst } from 'rollup/parseAst';

// Run after the production Vite build. Rollup's parser is already installed
// by Vite; this packaging step adds no runtime or package dependencies.
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dist = path.join(project, 'dist');
const output = path.join(project, 'portable');
const input = path.join(dist, 'index.html');
const target = path.join(output, 'SourceDestination.html');
const assets = new Set();
let scriptCount = 0;
let stylesheetCount = 0;

const mimeTypes = new Map([
  ['.svg', 'image/svg+xml'], ['.png', 'image/png'], ['.jpg', 'image/jpeg'],
  ['.jpeg', 'image/jpeg'], ['.gif', 'image/gif'], ['.webp', 'image/webp'],
  ['.avif', 'image/avif'], ['.ico', 'image/x-icon'], ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'], ['.ttf', 'font/ttf'], ['.otf', 'font/otf'],
  ['.mp3', 'audio/mpeg'], ['.ogg', 'audio/ogg'], ['.wav', 'audio/wav'],
  ['.mp4', 'video/mp4'], ['.webm', 'video/webm'], ['.json', 'application/json'],
]);

function fail(message) {
  throw new Error(`Portable packaging: ${message}`);
}

function attributes(tag) {
  const result = new Map();
  const expression = /([^\s=<>/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
  for (const match of tag.matchAll(expression)) {
    result.set(match[1].toLowerCase(), match[2] ?? match[3] ?? match[4] ?? '');
  }
  return result;
}

function decodeAttribute(value) {
  return value.replace(/&amp;/gi, '&').replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'").replace(/&#x([\da-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)));
}

function localAsset(reference, parent = input) {
  const ref = decodeAttribute(reference).trim();
  if (!ref || ref.startsWith('#') || /^data:/i.test(ref)) return null;
  if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(ref)) {
    fail(`remote or protocol asset is not allowed: ${ref.slice(0, 180)}`);
  }
  const pathname = decodeURIComponent(ref.split(/[?#]/, 1)[0]);
  const resolved = pathname.startsWith('/')
    ? path.resolve(dist, `.${pathname}`)
    : path.resolve(path.dirname(parent), pathname);
  const relative = path.relative(dist, resolved);
  if (relative.startsWith(`..${path.sep}`) || relative === '..' || path.isAbsolute(relative)) {
    fail(`asset escapes the production build: ${reference}`);
  }
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) fail(`missing local asset: ${reference}`);
  assets.add(resolved);
  return resolved;
}

function dataUri(reference, parent = input) {
  const filename = localAsset(reference, parent);
  if (!filename) return reference;
  const type = mimeTypes.get(path.extname(filename).toLowerCase()) || 'application/octet-stream';
  const fragment = reference.includes('#') ? `#${reference.split('#').slice(1).join('#')}` : '';
  return `data:${type};base64,${fs.readFileSync(filename).toString('base64')}${fragment}`;
}

function escapeAttribute(value) {
  return value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
}

function inlineCss(css, filename) {
  if (/@import\s/i.test(css)) fail('CSS still contains @import. Bundle every stylesheet before packaging.');
  const inlined = css.replace(/url\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*?))\s*\)/gi, (_, a, b, c) => {
    const ref = (a ?? b ?? c).trim();
    return `url("${dataUri(ref, filename).replaceAll('"', '\\"')}")`;
  });
  // A literal closing style tag inside a CSS string/comment must not end the
  // enclosing HTML raw-text element. CSS accepts the escaped slash.
  return inlined.replace(/<\/style/gi, '<\\/style');
}

function assertSelfContainedModule(code, filename) {
  let tree;
  try { tree = parseAst(code); } catch (error) { fail(`cannot parse ${path.basename(filename)}: ${error.message}`); }
  const pending = [tree];
  while (pending.length) {
    const node = pending.pop();
    if (!node || typeof node !== 'object') continue;
    if (node.type === 'ImportDeclaration' || node.type === 'ImportExpression' ||
        (node.type === 'ExportNamedDeclaration' && node.source) || node.type === 'ExportAllDeclaration') {
      fail(`${path.basename(filename)} has an unresolved module import. Build a single JavaScript bundle before packaging.`);
    }
    if (node.type === 'MetaProperty' && node.meta?.name === 'import') {
      fail(`${path.basename(filename)} still depends on import.meta. Inline its referenced assets in the production build first.`);
    }
    if (node.type === 'Literal' && typeof node.value === 'string' && /^\.?\/?assets\//.test(node.value)) {
      fail(`${path.basename(filename)} still references a separate runtime asset (${node.value}). Configure Vite to inline that asset first.`);
    }
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) pending.push(...value);
      else if (value && typeof value === 'object') pending.push(value);
    }
  }
}

function inlineScript(code, filename) {
  // External source maps are not needed by the portable release.
  const clean = code.replace(/^\s*\/\/# sourceMappingURL=.*$/gm, '')
    .replace(/\/\*# sourceMappingURL=[\s\S]*?\*\//g, '');
  assertSelfContainedModule(clean, filename);
  const escaped = clean.replace(/<\/script/gi, '<\\/script');
  assertSelfContainedModule(escaped, filename);
  return escaped;
}

function thirdPartyNotices() {
  const components = [
    { name: 'Three.js', folder: 'three' },
    { name: 'Vite (build-generated module preload helper)', folder: 'vite' },
  ];
  const sections = ['SOURCE / DESTINATION - THIRD-PARTY NOTICES\n\nThe portable HTML includes bundled open-source code.\n'];
  for (const component of components) {
    const base = path.join(project, 'node_modules', component.folder);
    const license = ['LICENSE', 'LICENSE.md', 'LICENSE.txt'].map(name => path.join(base, name)).find(name => fs.existsSync(name));
    if (!license) {
      if (component.folder === 'three') fail('Three.js LICENSE is missing. Restore the installed dependency before packaging.');
      continue;
    }
    const metadata = JSON.parse(fs.readFileSync(path.join(base, 'package.json'), 'utf8'));
    sections.push(`\n${'='.repeat(72)}\n${component.name} ${metadata.version}\n${'='.repeat(72)}\n\n${fs.readFileSync(license, 'utf8').trim()}\n`);
  }
  return sections.join('');
}

try {
  if (!fs.existsSync(input)) fail('dist/index.html does not exist. Run the Vite production build first.');
  let html = fs.readFileSync(input, 'utf8');
  if (/<base\b/i.test(html)) fail('a base URL would prevent reliable file:// operation. Remove it before packaging.');

  html = html.replace(/<link\b[^>]*>/gi, tag => {
    const attrs = attributes(tag);
    const rel = (attrs.get('rel') || '').toLowerCase().split(/\s+/);
    const href = attrs.get('href');
    if (rel.includes('stylesheet')) {
      if (!href) fail('stylesheet link is missing its href.');
      const filename = localAsset(href);
      if (!filename) fail('expected a local emitted CSS file for the stylesheet.');
      stylesheetCount++;
      const media = attrs.has('media') ? ` media="${escapeAttribute(attrs.get('media'))}"` : '';
      return `<style${media}>\n${inlineCss(fs.readFileSync(filename, 'utf8'), filename)}\n</style>`;
    }
    if (rel.includes('modulepreload') || rel.includes('preload') || rel.includes('prefetch')) {
      if (href) localAsset(href); // Reject remote fetches, even for removed hints.
      return '';
    }
    if (rel.includes('preconnect') || rel.includes('dns-prefetch')) fail('remove remote connection hints before portable packaging.');
    if (rel.some(value => ['icon', 'apple-touch-icon', 'mask-icon'].includes(value)) && href) {
      return tag.replace(/\bhref\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/i, `href="${escapeAttribute(dataUri(href))}"`);
    }
    if (rel.includes('manifest')) fail('a web app manifest is a separate dependency; omit it from the portable build.');
    return tag;
  });

  // Replace media URLs before embedding JavaScript, so HTML-looking strings
  // inside the JavaScript bundle can never be mistaken for document tags.
  html = html.replace(/<(?:img|source|video|audio|input|iframe|embed|object)\b[^>]*>/gi, tag => {
    if (/\bsrcset\s*=/i.test(tag)) fail('srcset needs to be flattened to one local image before packaging.');
    return tag.replace(/\b(src|poster|data)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi,
      (_, name, a, b, c) => `${name}="${escapeAttribute(dataUri(a ?? b ?? c))}"`);
  });

  html = html.replace(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi, (tag, attributeText, body) => {
    const attrs = attributes(attributeText);
    const src = attrs.get('src');
    if (attrs.get('type') === 'application/ld+json') return tag;
    if (attrs.get('type') === 'importmap') fail('an import map is not needed by a self-contained bundle.');
    if (src) {
      const filename = localAsset(src);
      if (!filename) fail('expected a local emitted JavaScript file for the entry script.');
      scriptCount++;
      const type = attrs.get('type') === 'module' ? ' type="module"' : '';
      return `<script${type}>\n${inlineScript(fs.readFileSync(filename, 'utf8'), filename)}\n</script>`;
    }
    if (body.trim()) assertSelfContainedModule(body, input);
    return tag;
  });

  if (!scriptCount) fail('the build has no emitted entry script to bundle.');
  const markup = html.replace(/(<(?:script|style)\b[^>]*>)[\s\S]*?(<\/(?:script|style)\s*>)/gi, '$1$2');
  for (const match of markup.matchAll(/<(?:script|img|source|video|audio|iframe|embed)\b[^>]*>/gi)) {
    const source = attributes(match[0]).get('src');
    if (source && !/^data:/i.test(source)) fail('an HTML resource still requires a separate file.');
  }
  const notices = thirdPartyNotices();
  html = html.replace(/<!doctype html>/i, '<!doctype html>\n<!-- Portable Source / Destination: all runtime JavaScript and CSS are embedded. -->\n<!--\n' + notices.replaceAll('--', '—') + '\n-->');
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(`${target}.tmp`, html, 'utf8');
  fs.renameSync(`${target}.tmp`, target);
  fs.writeFileSync(path.join(output, 'THIRD-PARTY-NOTICES.txt'), notices, 'utf8');
  console.log(JSON.stringify({
    output: target,
    bytes: Buffer.byteLength(html),
    javascriptBundles: scriptCount,
    stylesheets: stylesheetCount,
    embeddedLocalAssets: assets.size,
    externalRuntimeImports: 0,
    launcher: path.join(output, 'Launch-SourceDestination.bat'),
  }, null, 2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
