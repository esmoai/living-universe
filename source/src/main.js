import * as THREE from 'three';
import './universe.css';
import { mountUniverse } from './universe-ui.js';
import './style.css';
import { CubeExperience } from './scene.js';
import { canTypeTarget } from './navigation.js';

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const menu = $('#field-menu');
let experience, noticeTimer, quietTimer, nodeTimer;
let controlsHidden = false, failed = false;

function wake({ reveal = false } = {}) {
  if (reveal) { controlsHidden = false; document.body.classList.remove('controls-hidden'); }
  document.body.classList.remove('quiet');
  clearTimeout(quietTimer);
  quietTimer = setTimeout(() => {
    const focus = document.activeElement;
    if (!menu.open && !(focus?.closest('.chrome') && focus.matches(':focus-visible'))) document.body.classList.add('quiet');
  }, 5000);
}

function notice(message) {
  $('#notice').textContent = message;
  $('#notice').classList.add('visible');
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => $('#notice').classList.remove('visible'), 4700);
}

function modeChanged(mode) {
  document.body.dataset.mode = mode;
  if (mode !== 'inside') stopTouch();
  $('#crosshair').hidden = mode !== 'inside';
  $('#enter-label').textContent = mode === 'orbit' ? 'Enter the field' : mode === 'travel' ? 'Return home' : 'Outside view';
  $('#enter').setAttribute('aria-label', mode === 'orbit' ? 'Enter the living field' : 'Return to the reference view');
  $('#hint').textContent = mode === 'orbit' ? 'Drag to orbit  ·  Scroll to approach  ·  Choose a portal' : mode === 'travel' ? 'Follow the stream  ·  Esc to return' : 'Drag to look  ·  WASD to fly  ·  Q / E to rise or descend';
  wake();
}

function showNode({ name = '', subtitle = '', visit = 0 } = {}) {
  $('#node-name').textContent = name;
  $('#node-subtitle').textContent = subtitle;
  clearTimeout(nodeTimer);
  if (visit) { $('#node-label').classList.add('visible'); nodeTimer = setTimeout(() => $('#node-label').classList.remove('visible'), 3500); }
}

function showHover(target) {
  const label = $('#hover-label');
  if (!target || menu.open || controlsHidden || !Number.isFinite(target.x) || !Number.isFinite(target.y)) { label.hidden = true; return; }
  label.textContent = target.label;
  label.style.left = `${Math.max(12, Math.min(innerWidth - 200, target.x + 16))}px`;
  label.style.top = `${Math.max(12, Math.min(innerHeight - 50, target.y + 16))}px`;
  label.hidden = false;
}

function showJourney({ active, name, progress = 0 }) {
  $('#journey').hidden = !active;
  if (!active) return;
  $('#node-label').classList.remove('visible');
  $('#hover-label').hidden = true;
  if (name) $('#journey-name').textContent = `Following the stream · ${name}`;
  const p = Math.min(1, Math.max(0, progress));
  $('#journey-progress').style.transform = `scaleX(${p})`;
  $('.journey-track').setAttribute('aria-valuenow', String(Math.round(p * 100)));
}

function syncPause() {
  if (!experience) return;
  const label = experience.paused ? 'Resume motion' : 'Pause motion';
  $('#pause').setAttribute('aria-label', label);
  $('#pause').setAttribute('aria-pressed', String(experience.paused));
  $('#pause').title = `${label} · Space`;
  $('#pause-icon').setAttribute('href', experience.paused ? '#i-play' : '#i-pause');
}

function stopTouch() {
  if (experience?.touchMove) Object.assign(experience.touchMove, { x: 0, y: 0, vertical: 0 });
  $('#joystick-thumb').style.transform = 'translate(0,0)';
}

function closeMenu() {
  menu.close();
  experience?.keys.clear();
  stopTouch();
  wake();
  experience?.renderer?.domElement.focus({ preventScroll: true });
}

function toggleMenu() {
  if (menu.open) return closeMenu();
  experience?.keys.clear();
  stopTouch();
  $('#hover-label').hidden = true;
  menu.showModal();
  wake({ reveal: true });
}

async function fullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
    else notice('Use your browser’s fullscreen control on this device.');
  } catch { notice('Fullscreen is unavailable in this browser view.'); }
}

function showError(message) {
  failed = true;
  document.body.classList.add('graphics-unavailable');
  const loading = $('#loading');
  loading.hidden = false;
  loading.style.opacity = '1';
  loading.replaceChildren();
  const card = document.createElement('div'); card.className = 'error-state';
  const title = document.createElement('strong'); title.textContent = 'The field could not open.';
  const description = document.createElement('span'); description.textContent = message || 'This experience needs WebGL. Enable graphics acceleration, then reload.';
  const reload = document.createElement('button'); reload.textContent = 'Try again'; reload.addEventListener('click', () => location.reload());
  card.append(title, description, reload); loading.append(card);
}

try {
  experience = new CubeExperience($('#world'), {
    onMode: modeChanged, onNotice: notice, onNode: showNode, onHover: showHover, onJourney: showJourney,
    onXR(active) {
      document.body.classList.toggle('in-vr', active);
      if (active && menu.open) menu.close();
      stopTouch(); syncPause();
      $('#vr').setAttribute('aria-label', active ? 'Exit VR' : 'Enter VR');
    },
    onError: showError,
  });
  $('#quality').value = experience.quality || 'high';
  $('#comfort').checked = experience.comfort ?? true;
  syncPause();
  $('#enter').addEventListener('click', () => experience.mode === 'orbit' ? experience.enter() : experience.home());
  $('#home').addEventListener('click', () => experience.home());
  $('#pause').addEventListener('click', () => { experience.paused = !experience.paused; syncPause(); wake(); });
  $('#vr').addEventListener('click', async () => {
    try { await experience.enterVR(); }
    catch (error) { notice(error.message || 'Open this page in a compatible WebXR headset browser to enter VR.'); }
  });
  $('#open-menu').addEventListener('click', toggleMenu);
  $('#close-menu').addEventListener('click', closeMenu);
  menu.addEventListener('cancel', () => { experience.keys.clear(); stopTouch(); wake(); });
  menu.addEventListener('click', event => {
    if (event.target !== menu) return;
    const rect = menu.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeMenu();
  });
  $$('[data-portal]').forEach(button => button.addEventListener('click', () => { closeMenu(); experience.travel(button.dataset.portal); }));
  $('#quality').addEventListener('change', async event => {
    const select = event.currentTarget; select.disabled = true;
    try { await experience.setQuality(select.value); }
    catch (error) { notice(error.message || 'That detail level could not be applied.'); }
    finally { select.disabled = false; select.value = experience.quality || select.value; }
  });
  $$('[data-speed]').forEach(button => button.addEventListener('click', () => {
    experience.speed = Number(button.dataset.speed);
    $$('[data-speed]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  }));
  $('#comfort').addEventListener('change', event => { experience.comfort = event.currentTarget.checked; });
  $('#fullscreen').addEventListener('click', fullscreen);
  document.addEventListener('fullscreenchange', () => { $('#fullscreen span').textContent = document.fullscreenElement ? 'Leave fullscreen' : 'Fill the screen'; });

  const pad = $('#joystick'); let touchId = null;
  function moveThumb(event) {
    const rect = pad.getBoundingClientRect();
    let x = (event.clientX - rect.left - rect.width / 2) / 35;
    let y = (event.clientY - rect.top - rect.height / 2) / 35;
    const length = Math.hypot(x, y); if (length > 1) { x /= length; y /= length; }
    Object.assign(experience.touchMove, { x, y: -y });
    $('#joystick-thumb').style.transform = `translate(${x * 32}px,${y * 32}px)`;
  }
  pad.addEventListener('pointerdown', event => { if (touchId !== null) return; event.preventDefault(); touchId = event.pointerId; pad.setPointerCapture(touchId); moveThumb(event); });
  pad.addEventListener('pointermove', event => { if (event.pointerId === touchId) moveThumb(event); });
  for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) pad.addEventListener(name, event => {
    if (event.pointerId !== touchId) return;
    touchId = null; experience.touchMove.x = 0; experience.touchMove.y = 0; $('#joystick-thumb').style.transform = 'translate(0,0)';
  });
  for (const [selector, direction] of [['#rise', 1], ['#descend', -1]]) {
    const button = $(selector);
    button.addEventListener('pointerdown', event => { event.preventDefault(); button.setPointerCapture(event.pointerId); experience.touchMove.vertical = direction; });
    for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(name, () => { experience.touchMove.vertical = 0; });
  }
  window.addEventListener('blur', stopTouch);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopTouch(); });
  document.addEventListener('keydown', event => {
    if (event.repeat || canTypeTarget(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
    const key = event.key.toLowerCase();
    if (key === 'h') { event.preventDefault(); toggleMenu(); return; }
    if (menu.open) return;
    if (key === 'u') { controlsHidden = !controlsHidden; document.body.classList.toggle('controls-hidden', controlsHidden); $('#hover-label').hidden = true; }
    else if (event.code === 'Space') {
      if (event.target.closest('button')) return;
      event.preventDefault(); experience.paused = !experience.paused; syncPause(); wake();
    } else if (key === 'f') { event.preventDefault(); fullscreen(); }
    else wake();
  });
  document.addEventListener('pointermove', event => {
    if (event.clientY < 95 || event.clientY > innerHeight - 120 || event.clientX < 70 || event.clientX > innerWidth - 80) wake();
  }, { passive: true });
  document.addEventListener('pointerdown', () => wake({ reveal: true }), { passive: true });
  document.addEventListener('focusin', event => { if (event.target.closest('.chrome')) wake(); });
  Promise.resolve(experience.xr?.checkSupport?.()).then(result => {
    if (!result) return;
    const ready = Boolean(result.supported);
    $('#vr').classList.toggle('available', ready); $('.vr-status').classList.toggle('available', ready);
    $('#vr-status').textContent = ready ? 'VR is available. Enter from your headset.' : result.reason || 'VR needs a compatible headset browser over HTTPS.';
  }).catch(() => { $('#vr-status').textContent = 'VR needs a compatible headset browser over HTTPS.'; });
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (failed) return;
    $('#loading').style.opacity = '0';
    setTimeout(() => { if (!failed) $('#loading').hidden = true; }, 700);
  }));
  if (experience.reduced) notice('Reduced motion is on. Use the play button when you are ready.');
  wake();
} catch (error) {
  console.error('The living field could not start:', error);
  showError(/WebGL/i.test(error.message) ? 'WebGL 2 graphics are unavailable in this browser. Enable hardware acceleration or open the HTML in a browser with WebGL 2 support, then try again.' : error.message);
}

mountUniverse({ experience, notice, types: THREE });
