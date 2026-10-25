# Editable Living Universe visual source

This directory contains the original editable Source / Destination scene sources, plus the new floating observatory, data store, bit lens and software-rendered fallback. It is a Vite/Three.js development project, **not** the bare-metal kernel.

```bash
npm ci
npm test
npm run build
npm run portable
```

The public root `LivingUniverse.html` is the retained hash-checked offline bundle plus new instruments. `scripts/build_web.py` assembles that static artifact from the vendored original runtime and `source/src/universe-*.js`, `bit-lens.js`, `software-field.js`, and CSS without downloading dependencies. Changing `source/src/scene.js` requires a full Vite rebuild and separate regression testing. Development dependencies are replaceable tools; they are not part of the C kernel.

Read `../docs/BUILD_AND_TEST.md` and `../docs/VALIDATION.md` for scope and caveats. The UI never grants native capabilities.
