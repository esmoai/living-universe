import * as THREE from 'three';
import { MarchingCubes } from 'three/addons/objects/MarchingCubes.js';
import { HALF, GLOBE_RADIUS, PORTALS, SPEED, TAU, V, spectrum, portalCenter, portalPoint, wallPoint, random } from './geometry.js';

// The entire reference is geometry. There are no image planes, backdrop movies,
// hidden front walls, or extra satellites in the exterior composition.
const QUALITY = {
  high: { walls: 1150, shell: 10500, mist: 1500, resolution: 44, blobHz: 22, spokes: 32 },
  medium: { walls: 820, shell: 7200, mist: 900, resolution: 36, blobHz: 20, spokes: 32 },
  low: { walls: 520, shell: 3900, mist: 450, resolution: 28, blobHz: 16, spokes: 24 },
};
const VIEW_AXIS = V(1, 1, 1).normalize();
const HSV = `
vec3 spectrum(float h) {
  vec3 p=abs(fract(vec3(h)+vec3(0.,2./3.,1./3.))*6.-3.);
  return clamp(p-1.,0.,1.);
}`;

function buffer(positions, colors, attributes = {}) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  if (colors) g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  for (const [key, [array, size]] of Object.entries(attributes)) {
    g.setAttribute(key, new THREE.Float32BufferAttribute(array, size));
  }
  g.computeBoundingSphere();
  return g;
}

/** Camera-independent, deterministic reconstruction of the supplied motion reference. */
export class ReferenceWorld {
  constructor({ quality = 'high' } = {}) {
    this.quality = Object.hasOwn(QUALITY, quality) ? quality : 'high';
    this.detail = QUALITY[this.quality];
    this.random = random(7384);
    this.root = new THREE.Group();
    this.root.name = 'Reference · open three-wall cube';
    this.materials = [];
    this.portals = [];
    this.lastBlob = -Infinity;
    this.emphasis = null;
    this.time = 0;
    this._makeCube();
    this._makePortals();
    this._makeGlobe();
    this._makeCore();
    this._makeFluid();
    this.update(0);
  }

  _wire(positions, colors, { opacity = .8, scatter = .002, centers, axis = [0, 1, 0], spin = 0 } = {}) {
    const seed = Array.from({ length: positions.length / 3 }, (_, i) => Math.sin(i * 1.73) * .5 + .5);
    const material = new THREE.ShaderMaterial({
      vertexColors: true, transparent: true, depthWrite: false, toneMapped: false,
      uniforms: {
        uTime: { value: 0 }, uOpacity: { value: opacity }, uScatter: { value: scatter },
        uAxis: { value: V(...axis) }, uSpin: { value: spin }, uEmphasis: { value: 0 },
      },
      vertexShader: `
        attribute float aSeed;
        attribute vec3 aCenter;
        uniform float uTime,uSpin,uScatter;
        uniform vec3 uAxis;
        varying vec3 vColor;
        void main(){
          vec3 d=position-aCenter;
          float angle=uTime*uSpin;
          vec3 p=aCenter+d*cos(angle)+cross(uAxis,d)*sin(angle)+uAxis*dot(uAxis,d)*(1.-cos(angle));
          p+=uScatter*sin(vec3(17.3,29.1,13.7)*aSeed+floor(uTime*11.)*vec3(1.31,2.17,2.87));
          vColor=color;
          gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.);
        }`,
      fragmentShader: `
        uniform float uOpacity,uEmphasis;
        varying vec3 vColor;
        void main(){
          vec3 c=mix(vColor,vec3(1.),uEmphasis*.22);
          gl_FragColor=vec4(c,min(1.,uOpacity+uEmphasis*.18));
          #include <colorspace_fragment>
        }`,
    });
    this.materials.push(material);
    return new THREE.LineSegments(buffer(positions, colors, {
      aSeed: [seed, 1], aCenter: [centers || Array(positions.length).fill(0), 3],
    }), material);
  }

  _points(positions, colors, { size = .025, scatter = .02, opacity = 1, twinkle = .5, axis = [0, 1, 0], spin = 0, centers, surface = false } = {}) {
    const seeds = [], sizes = [], rnd = this.random;
    for (let i = 0; i < positions.length / 3; i++) {
      seeds.push(rnd() * 100);
      sizes.push(size * (.45 + rnd() * 1.45));
    }
    const material = new THREE.ShaderMaterial({
      vertexColors: true, transparent: true, depthWrite: false, toneMapped: false,
      uniforms: {
        uTime: { value: 0 }, uPixelRatio: { value: 1 }, uScale: { value: 60 },
        uPerspective: { value: 0 }, uScatter: { value: scatter }, uOpacity: { value: opacity },
        uTwinkle: { value: twinkle }, uAxis: { value: V(...axis) }, uSpin: { value: spin },
        uSurface: { value: surface ? 1 : 0 },
      },
      vertexShader: `
        attribute float aSeed,aSize;
        attribute vec3 aCenter;
        uniform float uTime,uPixelRatio,uScale,uPerspective,uScatter,uTwinkle,uSpin,uSurface;
        uniform vec3 uAxis;
        varying vec3 vColor;
        varying float vAlpha;
        void main(){
          float angle=uTime*uSpin;
          vec3 d=position-aCenter;
          vec3 p=aCenter+d*cos(angle)+cross(uAxis,d)*sin(angle)+uAxis*dot(uAxis,d)*(1.-cos(angle));
          float tick=floor(uTime*13.);
          vec3 jitter=sin(vec3(aSeed*21.1,aSeed*17.3,aSeed*13.7)+tick*vec3(1.37,3.17,2.11));
          p+=jitter*uScatter;
          vec4 mv=modelViewMatrix*vec4(p,1.);
          float scale=uPerspective>.5?500./max(.25,-mv.z):uScale;
          gl_PointSize=clamp(aSize*scale*uPixelRatio,.7,7.5*uPixelRatio);
          gl_Position=projectionMatrix*mv;
          vColor=color;
          vAlpha=1.-uTwinkle*(.5+.5*sin(aSeed*73.1+tick*1.47));
          if(uSurface>.5){
            vec3 normal=normalize(normalMatrix*normalize(position));
            float rim=1.-abs(dot(normal,normalize(-mv.xyz)));
            vAlpha*=.38+.62*pow(rim,.55);
          }
        }`,
      fragmentShader: `
        uniform float uOpacity;
        varying vec3 vColor;
        varying float vAlpha;
        void main(){
          float r=length(gl_PointCoord*2.-1.);
          if(r>1.)discard;
          float shape=1.-smoothstep(.55,1.,r);
          gl_FragColor=vec4(vColor,uOpacity*vAlpha*shape);
          #include <colorspace_fragment>
        }`,
    });
    this.materials.push(material);
    const points = new THREE.Points(buffer(positions, colors, {
      aSeed: [seeds, 1], aSize: [sizes, 1], aCenter: [centers || Array(positions.length).fill(0), 3],
    }), material);
    points.frustumCulled = false;
    return points;
  }

  _makeCube() {
    const walls = new THREE.Group();
    walls.name = 'Floor and two rear walls · no front or top';
    this.root.add(walls);
    const edgeMap = new Map();
    const rnd = this.random;
    for (const wall of ['rear-left', 'rear-right', 'bottom']) {
      const corners = [wallPoint(wall, -HALF, -HALF), wallPoint(wall, HALF, -HALF), wallPoint(wall, HALF, HALF), wallPoint(wall, -HALF, HALF)];
      for (let j = 0; j < 4; j++) {
        const a = corners[j], b = corners[(j + 1) % 4];
        edgeMap.set([a.join(','), b.join(',')].sort().join('|'), [a, b]);
      }
      const positions = [], colors = [];
      for (let i = 0; i < this.detail.walls; i++) {
        let a, b;
        // The flared mouth is a real opening in each star-covered surface.
        do { a = (rnd() * 2 - 1) * HALF; b = (rnd() * 2 - 1) * HALF; }
        while ((a - 1) ** 2 + (b - 1) ** 2 < 1.76 ** 2);
        positions.push(...wallPoint(wall, a, b));
        const c = i % 4 === 0 ? spectrum(rnd()) : new THREE.Color().setScalar(.72 + rnd() * .28);
        colors.push(c.r, c.g, c.b);
      }
      const points = this._points(positions, colors, { size: .026, scatter: .015, twinkle: .64 });
      points.name = `Constellations · ${wall}`;
      points.userData.wall = wall;
      walls.add(points);
    }

    const positions = [], colors = [];
    let index = 0;
    for (const [start, end] of edgeMap.values()) {
      for (let j = 0; j < 48; j++) {
        for (const t of [j / 48, (j + 1) / 48]) {
          positions.push(...V(...start).lerp(V(...end), t).toArray());
          const c = spectrum(index * .137 + t * .78);
          colors.push(c.r, c.g, c.b);
        }
      }
      index++;
    }
    const edges = this._wire(positions, colors, { opacity: .76, scatter: .0014 });
    edges.name = 'Nine open-cube edges';
    walls.add(edges);
    const corners = [...new Set([...edgeMap.values()].flat().map(p => p.join(',')))].map(p => p.split(',').map(Number));
    const vertices = this._points(corners.flat(), corners.flatMap(() => [1, 1, 1]), { size: .055, scatter: .001, twinkle: .18 });
    vertices.name = 'Cube vertices';
    walls.add(vertices);
    this.stats = { wallCount: 3, edgeCount: edgeMap.size, wallParticles: this.detail.walls * 3, shellParticles: this.detail.shell };
  }

  _makePortals() {
    for (const portal of PORTALS) {
      const positions = [], colors = [], centers = [], knots = [], knotColors = [], knotCenters = [];
      const spokes = this.detail.spokes;
      const add = (t, a, t2, a2) => {
        for (const [depth, angle] of [[t, a], [t2, a2]]) {
          positions.push(...portalPoint(portal, depth, angle).toArray());
          centers.push(...portalCenter(portal, depth).toArray());
          const c = spectrum(angle / TAU + .09 + depth * .22);
          colors.push(c.r, c.g, c.b);
        }
      };
      for (let spoke = 0; spoke < spokes; spoke++) {
        for (let j = 0; j < 32; j++) add(j / 32, spoke / spokes * TAU, (j + 1) / 32, spoke / spokes * TAU);
      }
      for (let ring = 0; ring <= 13; ring++) {
        const t = ring / 13;
        for (let j = 0; j < 96; j++) add(t, j / 96 * TAU, t, (j + 1) / 96 * TAU);
        for (let j = 0; j < spokes; j++) {
          knots.push(...portalPoint(portal, t, j / spokes * TAU).toArray());
          knotCenters.push(...portalCenter(portal, t).toArray());
          knotColors.push(1, 1, 1);
        }
      }
      const grid = this._wire(positions, colors, { opacity: .85, centers, axis: portal.normal, spin: SPEED.portals, scatter: .0013 });
      grid.name = `Counterclockwise funnel · ${portal.id}`;
      this.root.add(grid);
      const joints = this._points(knots, knotColors, { size: .024, scatter: .001, opacity: .82, twinkle: .15, centers: knotCenters, axis: portal.normal, spin: SPEED.portals });
      joints.name = `Funnel intersections · ${portal.id}`;
      this.root.add(joints);

      const hit = new THREE.Mesh(new THREE.CircleGeometry(1.8, 48), new THREE.MeshBasicMaterial({ visible: false, side: THREE.DoubleSide }));
      hit.position.fromArray(portal.center);
      hit.quaternion.setFromUnitVectors(V(0, 0, 1), V(...portal.normal));
      hit.userData.portal = portal;
      hit.name = `Portal target · ${portal.id}`;
      this.root.add(hit);

      // The cores travel from broad wall mouths inward to the coalescing shell.
      const path = new THREE.CatmullRomCurve3([
        V(...portal.center), portalCenter(portal, .45), portalCenter(portal, .86), V(...portal.center).normalize().multiplyScalar(1.35),
      ]);
      const stream = new THREE.Mesh(new THREE.TubeGeometry(path, 88, .168, 18, false), this._streamMaterial(PORTALS.indexOf(portal)));
      stream.name = `Inward fluorescent fluid · ${portal.id}`;
      this.root.add(stream);
      const streamSkin = new THREE.Mesh(new THREE.TubeGeometry(path, 72, .189, 12, false), this._streamSkinMaterial(PORTALS.indexOf(portal)));
      streamSkin.name = `Aerogel edge · ${portal.id}`;
      this.root.add(streamSkin);
      this.portals.push({ portal, hit, grid, joints, path, stream, streamSkin });
    }
  }

  _streamMaterial(index) {
    const material = new THREE.ShaderMaterial({
      toneMapped: false,
      uniforms: { uTime: { value: 0 }, uPhase: { value: index * .17 } },
      vertexShader: `
        varying vec2 vUv;
        varying vec3 vNormal,vView;
        uniform float uTime;
        void main(){
          vUv=uv;
          vec3 p=position+normal*(.011*sin(uv.x*32.-uTime*4.7)+.006*sin(uv.y*18.85+uTime*2.3));
          vec4 mv=modelViewMatrix*vec4(p,1.);
          vNormal=normalize(normalMatrix*normal);
          vView=normalize(-mv.xyz);
          gl_Position=projectionMatrix*mv;
        }`,
      fragmentShader: `
        varying vec2 vUv;
        varying vec3 vNormal,vView;
        uniform float uTime,uPhase;
        ${HSV}
        void main(){
          float phase=vUv.x*2.5-uTime*.62+uPhase;
          vec3 c=spectrum(phase+.025*sin(vUv.y*6.283+uTime*1.2));
          float white=pow(.5+.5*cos(phase*6.283),28.);
          c=mix(c,vec3(1.),white*.98);
          float facing=abs(dot(normalize(vNormal),normalize(vView)));
          c*=.7+.3*sqrt(facing);
          gl_FragColor=vec4(c,1.);
          #include <colorspace_fragment>
        }`,
    });
    this.materials.push(material);
    return material;
  }

  _streamSkinMaterial(index) {
    const material = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false,
      uniforms: { uTime: { value: 0 }, uPhase: { value: index * .17 } },
      vertexShader: `varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader: `
        varying vec2 vUv;uniform float uTime,uPhase;${HSV}
        void main(){
          float fleck=pow(.5+.5*sin(vUv.x*490.+sin(vUv.y*72.)*3.-uTime*18.),9.);
          gl_FragColor=vec4(spectrum(vUv.x*2.5-uTime*.62+uPhase),fleck*.19);
          #include <colorspace_fragment>
        }`,
    });
    this.materials.push(material);
    return material;
  }

  _makeGlobe() {
    this.globe = new THREE.Group();
    this.globe.name = 'Counterclockwise latitude-longitude globe';
    this.root.add(this.globe);
    const positions = [], colors = [];
    const spherical = (p, a) => V(Math.sin(p) * Math.cos(a) * GLOBE_RADIUS, Math.cos(p) * GLOBE_RADIUS, Math.sin(p) * Math.sin(a) * GLOBE_RADIUS);
    const add = (p, a, p2, a2, h, h2 = h) => {
      positions.push(...spherical(p, a).toArray(), ...spherical(p2, a2).toArray());
      for (const hue of [h, h2]) { const c = spectrum(hue); colors.push(c.r, c.g, c.b); }
    };
    for (let longitude = 0; longitude < 36; longitude++) {
      const angle = longitude / 36 * TAU;
      for (let i = 0; i < 80; i++) add(i / 80 * Math.PI, angle, (i + 1) / 80 * Math.PI, angle, longitude / 36 + i / 80 * .2);
    }
    for (let latitude = 1; latitude < 24; latitude++) {
      const p = latitude / 24 * Math.PI;
      for (let i = 0; i < 144; i++) add(p, i / 144 * TAU, p, (i + 1) / 144 * TAU, i / 144 + latitude / 24 * .2, (i + 1) / 144 + latitude / 24 * .2);
    }
    this.globeWire = this._wire(positions, colors, { opacity: .79, scatter: .002 });
    this.globe.add(this.globeWire);
    this.globeHit = new THREE.Mesh(new THREE.SphereGeometry(GLOBE_RADIUS, 32, 24), new THREE.MeshBasicMaterial({ visible: false, side: THREE.DoubleSide }));
    this.globeHit.name = 'Globe entry target';
    this.root.add(this.globeHit);

    this.shellFlow = new THREE.Group();
    this.shellFlow.name = 'Clockwise fluorescent aerogel shell';
    this.root.add(this.shellFlow);
    const pos = [], col = [], rnd = this.random;
    for (let i = 0; i < this.detail.shell; i++) {
      const a = rnd() * TAU, y = rnd() * 2 - 1;
      const r = GLOBE_RADIUS - rnd() ** 2 * .24;
      const horizontal = Math.sqrt(1 - y * y);
      pos.push(Math.cos(a) * horizontal * r, y * r, Math.sin(a) * horizontal * r);
      const c = spectrum(a / TAU + y * .16 + .09 * Math.sin(a * 3));
      col.push(c.r, c.g, c.b);
    }
    const shell = this._points(pos, col, { size: .024, scatter: .028, opacity: .84, twinkle: .45, surface: true });
    shell.name = 'Fine fluorescent shell grains';
    this.shellFlow.add(shell);

    // A restrained edge film strengthens the rainbow silhouette without washing
    // out its black center, its fine grid, or the incoming liquid cores.
    const rimMaterial = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, side: THREE.FrontSide, toneMapped: false,
      uniforms: { uTime: { value: 0 } },
      vertexShader: `
        varying vec3 vPosition,vNormal,vView;
        void main(){vPosition=position;vec4 mv=modelViewMatrix*vec4(position,1.);vNormal=normalize(normalMatrix*normal);vView=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `
        varying vec3 vPosition,vNormal,vView;uniform float uTime;${HSV}
        void main(){
          float rim=pow(1.-abs(dot(normalize(vNormal),normalize(vView))),3.3);
          float hue=atan(vPosition.z,vPosition.x)/6.283+vPosition.y*.06-uTime*.027;
          gl_FragColor=vec4(spectrum(hue),rim*.105);
          #include <colorspace_fragment>
        }`,
    });
    this.materials.push(rimMaterial);
    const rim = new THREE.Mesh(new THREE.SphereGeometry(GLOBE_RADIUS - .014, 64, 48), rimMaterial);
    rim.name = 'Subtle aerogel edge film';
    this.root.add(rim);
  }

  _makeCore() {
    this.orb = new THREE.Mesh(new THREE.SphereGeometry(1.23, 64, 48), new THREE.MeshBasicMaterial({ color: 0x000003, toneMapped: false }));
    this.orb.name = 'Black coalescence orb';
    this.root.add(this.orb);
  }

  _makeFluid() {
    this.fluidRoot = new THREE.Group();
    this.fluidRoot.name = 'Clockwise coalescing fluid';
    this.fluidRoot.quaternion.setFromUnitVectors(V(0, 0, 1), VIEW_AXIS);
    this.root.add(this.fluidRoot);
    const material = new THREE.ShaderMaterial({
      vertexColors: true, toneMapped: false,
      uniforms: { uTime: { value: 0 } },
      vertexShader: `
        varying vec3 vColor,vNormal,vView,vPosition;
        void main(){vColor=color;vPosition=position;vec4 mv=modelViewMatrix*vec4(position,1.);vNormal=normalize(normalMatrix*normal);vView=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `
        varying vec3 vColor,vNormal,vView,vPosition;uniform float uTime;
        void main(){
          vec3 c=vColor/max(.0001,max(vColor.r,max(vColor.g,vColor.b)));
          // Keep the liquid saturated even where metaball color fields blend.
          c=pow(c,vec3(1.35));
          float facing=abs(dot(normalize(vNormal),normalize(vView)));
          float softLight=.67+.33*sqrt(facing);
          float grain=fract(sin(dot(floor(vPosition*680.),vec3(12.9898,78.233,45.164)))*43758.5453);
          c*=softLight*(.94+.06*grain);
          gl_FragColor=vec4(c,1.);
          #include <colorspace_fragment>
        }`,
    });
    this.materials.push(material);
    this.blob = new MarchingCubes(this.detail.resolution, material, false, true, 36000);
    this.blob.name = 'Merging fluorescent liquid field';
    this.blob.scale.setScalar(2.18);
    this.blob.frustumCulled = false;
    this.fluidRoot.add(this.blob);
    this._updateBlob(0);
  }

  _updateBlob(t) {
    this.blob.reset();
    // Offset towards the open corner: the central void remains visible, while
    // thick aerogel folds move around it and merge over its near surface.
    const count = 15;
    for (let i = 0; i < count; i++) {
      const a = i / count * TAU;
      const radius = 1.32 + .11 * Math.sin(a * 3 + t * .65) + .1 * Math.cos(a * 2 - t * .72);
      const x = Math.cos(a) * radius, y = Math.sin(a) * radius;
      const z = .61 + .2 * Math.sin(a * 2 + t * .65);
      const swell = .5 + .5 * Math.sin(a * 3 - t * .8);
      const strength = .18 + .55 * swell * swell;
      this.blob.addBall(.5 + x / 4.36, .5 + y / 4.36, .5 + z / 4.36, strength, 22, spectrum(i / count + .12));
    }
    // Small detached lobes approach the annulus and merge back into it. They
    // stay outside the central void, which is a defining part of the reference.
    for (let i = 0; i < 2; i++) {
      const a = i / 2 * TAU + t * .38;
      const radius = 1.39 + .24 * Math.sin(t * .65 + i * 2.15);
      const z = .77 + .15 * Math.cos(t * .72 + i);
      const strength = .22 + .13 * (.5 + .5 * Math.sin(t * .6 + i));
      this.blob.addBall(.5 + Math.cos(a) * radius / 4.36, .5 + Math.sin(a) * radius / 4.36, .5 + z / 4.36, strength, 24, spectrum(i / 2 + t * .025 + .04));
    }
    // One much smaller droplet passes across the void without bridging it.
    const dropletAngle = t * .52 + 1.9;
    const dropletRadius = .65 + .25 * Math.sin(t * .71);
    const dropletStrength = .025 + .13 * Math.max(0, Math.sin(t * .8 + .7));
    this.blob.addBall(.5 + Math.cos(dropletAngle) * dropletRadius / 4.36,
      .5 + Math.sin(dropletAngle) * dropletRadius / 4.36,
      .5 + 1.26 / 4.36, dropletStrength, 36, spectrum(t * .045 + .82));
    this.blob.update();
    this.lastBlob = t;
  }

  setEmphasis(id = null) {
    this.emphasis = id;
    for (const item of this.portals) item.grid.material.uniforms.uEmphasis.value = id === item.portal.id ? 1 : 0;
    this.globeWire.material.uniforms.uEmphasis.value = id === 'globe' ? 1 : 0;
  }

  update(time, { pixelRatio = 1, pointScale = 60, perspective = false } = {}) {
    this.time = time;
    // Randomized scatter does most of the visual pulsing; the structural size
    // varies by less than half a percent so navigation remains comfortable.
    this.root.scale.setScalar(1 + .0028 * Math.sin(time * .63) + .0013 * Math.sin(time * 2.17 + Math.sin(time * .7)));
    this.globe.rotation.y = time * SPEED.globe;
    this.shellFlow.rotation.y = time * SPEED.fluid;
    this.blob.rotation.z = time * SPEED.fluid;
    if (time < this.lastBlob || time - this.lastBlob >= 1 / this.detail.blobHz) this._updateBlob(time);
    for (const material of this.materials) {
      const u = material.uniforms;
      if (u.uTime) u.uTime.value = time;
      if (u.uPixelRatio) u.uPixelRatio.value = pixelRatio;
      if (u.uScale) u.uScale.value = pointScale;
      if (u.uPerspective) u.uPerspective.value = perspective ? 1 : 0;
    }
  }

  dispose() {
    const geometries = new Set(), materials = new Set();
    this.root.traverse(object => {
      if (object.geometry) geometries.add(object.geometry);
      if (object.material) for (const material of Array.isArray(object.material) ? object.material : [object.material]) materials.add(material);
    });
    for (const geometry of geometries) geometry.dispose();
    for (const material of materials) material.dispose();
    this.root.clear();
    this.materials.length = 0;
    this.portals.length = 0;
  }
}
