// Software-rendered fallback for restricted/unsupported WebGL environments.
// This is a real projected 3D scene, not a screenshot or synthetic telemetry.
import { CHANNELS, hashText } from './universe-core.js';
const TAU = Math.PI * 2;
const PORTALS = [
 { id:'intelligence', center:[-3,1,1], u:[0,1,0], v:[0,0,1] },
 { id:'collaboration', center:[1,1,-3], u:[1,0,0], v:[0,1,0] },
 { id:'tools', center:[1,-3,1], u:[0,0,1], v:[1,0,0] }
];
function random(seed) { return () => { seed = (Math.imul(seed,1664525)+1013904223) >>> 0; return seed/4294967296; }; }
export class SoftwareField {
 constructor({ onSelect, onNode, notice }) {
  this.onSelect=onSelect;this.onNode=onNode;this.notice=notice;this.enabled=false;this.items=[];this.selected=null;this.node='core';
  this.yaw=Math.PI/4;this.pitch=.615;this.zoom=1;this.speed=1;this.panX=0;this.panY=0;this.time=0;this.last=0;this.lastDraw=0;this.paused=matchMedia('(prefers-reduced-motion: reduce)').matches;this.inside=false;this.quality='medium';this.keys=new Set();this.drag=null;this.hits=[];this.travelState=null;
  this.canvas=document.createElement('canvas');this.canvas.setAttribute('aria-label','Software-rendered three-dimensional field. Drag to orbit; scroll to approach. Open Instruments for accessible data inspection.');this.canvas.tabIndex=0;this.canvas.style.cssText='display:block;width:100vw;height:100dvh;touch-action:none;';document.querySelector('#world').replaceChildren(this.canvas);this.ctx=this.canvas.getContext('2d');
  const rng=random(812104);this.stars=Array.from({length:1100},(_,i)=>({p:[rng()*6-3,rng()*6-3,rng()*6-3],hue:rng()*360,white:i%5!==0,size:rng()*.8+.45}));
  this.resize=()=>{const ratio=Math.min(devicePixelRatio||1,1.5);this.w=innerWidth;this.h=innerHeight;this.canvas.width=Math.round(this.w*ratio);this.canvas.height=Math.round(this.h*ratio);this.ctx.setTransform(ratio,0,0,ratio,0,0);};this.resize();window.addEventListener('resize',this.resize);
  document.querySelector('#loading').hidden=true;document.body.classList.remove('graphics-unavailable');document.body.classList.add('software-field');
  this.canvas.addEventListener('pointerdown',e=>{this.drag={x:e.clientX,y:e.clientY,sx:e.clientX,sy:e.clientY};this.canvas.setPointerCapture(e.pointerId);});
  this.canvas.addEventListener('pointermove',e=>{if(this.drag){this.yaw+=(e.clientX-this.drag.x)*.006;this.pitch=Math.max(-1.4,Math.min(1.4,this.pitch+(e.clientY-this.drag.y)*.006));this.drag.x=e.clientX;this.drag.y=e.clientY;}else{const hit=this.pick(e.clientX,e.clientY);this.canvas.style.cursor=hit?'pointer':'grab';}});
  this.canvas.addEventListener('pointerup',e=>{if(this.drag&&Math.hypot(e.clientX-this.drag.sx,e.clientY-this.drag.sy)<5){const hit=this.pick(e.clientX,e.clientY);if(hit?.id){this.select(hit.id);onSelect(hit.id);}else if(hit?.portal)this.travel(hit.portal);else if(Math.hypot(e.clientX-this.w/2,e.clientY-this.h/2)<this.h*.2)this.enter();}this.drag=null;});
  this.canvas.addEventListener('pointercancel',()=>this.drag=null);
  this.canvas.addEventListener('wheel',e=>{e.preventDefault();this.zoom=Math.max(.45,Math.min(5,this.zoom*Math.exp(-e.deltaY*.001)));},{passive:false});
  const menu=document.querySelector('#field-menu');document.querySelector('#open-menu').addEventListener('click',()=>menu.showModal());document.querySelector('#close-menu').addEventListener('click',()=>menu.close());
  document.querySelector('#enter').addEventListener('click',()=>this.inside?this.home():this.enter());document.querySelector('#home').addEventListener('click',()=>this.home());
  document.querySelector('#pause').addEventListener('click',()=>{this.paused=!this.paused;document.querySelector('#pause').setAttribute('aria-pressed',String(this.paused));document.querySelector('#pause-icon').setAttribute('href',this.paused?'#i-play':'#i-pause');});
  document.querySelector('#vr').addEventListener('click',()=>notice('Software rendering is active. VR requires WebGL and a compatible WebXR browser.'));
  document.querySelector('#vr-status').textContent='Software field active. WebGL / VR is unavailable in this browser environment.';
  document.querySelectorAll('[data-portal]').forEach((b,i)=>b.addEventListener('click',()=>{menu.close();this.travel(PORTALS[i].id);}));
  document.querySelectorAll('[data-speed]').forEach(b=>b.addEventListener('click',()=>{this.speed=Number(b.dataset.speed);document.querySelectorAll('[data-speed]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));}));
  document.querySelector('#comfort').disabled=true;document.querySelector('#comfort').title='VR comfort applies only to the WebGL / WebXR renderer.';
  document.querySelector('#quality').addEventListener('change',e=>this.quality=e.target.value);
  document.querySelector('#fullscreen').addEventListener('click',async()=>{try{await document.documentElement.requestFullscreen();}catch{notice('Fullscreen is unavailable in this browser.');}});
  window.addEventListener('keydown',e=>{if(e.target.closest('input,textarea,select,button,[contenteditable]')||menu.open)return;this.keys.add(e.key.toLowerCase());if(e.key==='Home')this.home();if(e.key==='Enter')this.inside?this.home():this.enter();if(['1','2','3'].includes(e.key))this.travel(PORTALS[Number(e.key)-1].id);if(e.code==='Space'){e.preventDefault();document.querySelector('#pause').click();}if(e.key.toLowerCase()==='h')menu.showModal();if(e.key==='Escape'&&this.travelState)this.home();});
  window.addEventListener('keyup',e=>this.keys.delete(e.key.toLowerCase()));window.addEventListener('blur',()=>{this.keys.clear();this.drag=null;});
  document.querySelector('#pause').setAttribute('aria-pressed',String(this.paused));document.querySelector('#pause-icon').setAttribute('href',this.paused?'#i-play':'#i-pause');this.setMode();this.raf=requestAnimationFrame(t=>this.frame(t));notice('Software-rendered field active. Data inspection works; VR is unavailable.');
 }
 project(p) {
  const [x,y,z]=p,a=Math.cos(this.yaw),b=Math.sin(this.yaw),c=Math.cos(this.pitch),d=Math.sin(this.pitch),xx=x*a-z*b,zz=x*b+z*a,yy=y*c-zz*d,depth=y*d+zz*c;
  const perspective=this.inside?Math.max(.25,9/(9-depth)):1;
  const scale=Math.min(this.w/13,this.h/11)*this.zoom*perspective;
  return {x:this.w/2+(xx-this.panX)*scale,y:this.h/2-(yy-this.panY)*scale,z:depth,scale};
 }
 path(points,hue,alpha=.6,width=.7) { const c=this.ctx;c.beginPath();points.forEach((p,i)=>{const q=this.project(p);if(i)c.lineTo(q.x,q.y);else c.moveTo(q.x,q.y);});c.strokeStyle=`hsla(${hue},100%,65%,${alpha})`;c.lineWidth=width;c.stroke(); }
 portalPoint(p,t,a){const r=.13+1.65*Math.pow(1-t,2.15);return p.center.map((v,i)=>v*(1-.64*t)+p.u[i]*Math.cos(a)*r+p.v[i]*Math.sin(a)*r);}
 positionFor(p){const h=parseInt(hashText(p.id),16),phi=(h%65536)/65536*TAU,y=(h>>>16)/65535*1.7-.85,r=2.55+(p.channel%4)*.15;return[Math.sqrt(1-y*y)*Math.cos(phi)*r,y*r,Math.sqrt(1-y*y)*Math.sin(phi)*r];}
 setPackets(packets){this.items=packets.map(p=>({packet:p,p:this.positionFor(p)}));}
 show(value){this.enabled=value;}
 select(id){this.selected=id;}
 peer(id){const m=this.items.find(x=>x.packet.id===id);if(!m)return;this.selected=id;this.enabled=true;this.zoom=1.55;this.notice('Selected record highlighted in the software field. Drag or scroll to change perspective.');}
 pick(x,y){return [...this.hits].reverse().find(p=>Math.hypot(p.x-x,p.y-y)<p.r);}
 enter(){this.inside=true;this.zoom=2;this.setMode();}
 home(){this.travelState=null;this.yaw=Math.PI/4;this.pitch=.615;this.zoom=1;this.panX=this.panY=0;this.inside=false;this.node='core';this.onNode('core');this.setMode();}
 setMode(){document.body.dataset.mode=this.inside?'inside':'orbit';document.querySelector('#enter-label').textContent=this.inside?'Outside view':'Enter the field';document.querySelector('#hint').textContent=this.inside?'Software field / drag to look / WASD to move / Q & E for height':'Software field / drag to orbit / scroll to approach / select records';}
 travel(node){if(this.travelState)return;this.travelState={node,t:0,startZoom:this.zoom};this.notice(`Following the stream / ${node}`);}
 frame(stamp){this.raf=requestAnimationFrame(t=>this.frame(t));if(document.hidden)return;if(stamp-this.lastDraw<33)return;const dt=Math.min(.1,(stamp-(this.lastDraw||stamp))/1000);this.lastDraw=stamp;if(!this.paused)this.time+=dt*this.speed;this.stats={renderer:'software Canvas2D',renderedAtMs:Math.round(stamp),decorativePoints:this.stars.length,visibleRecords:this.enabled?this.items.length:0};
  if(this.inside){this.panX+=((this.keys.has('d')?1:0)-(this.keys.has('a')?1:0))*dt*2;this.panY+=((this.keys.has('e')?1:0)-(this.keys.has('q')?1:0))*dt*2;this.zoom=Math.max(.45,Math.min(5,this.zoom+((this.keys.has('w')?1:0)-(this.keys.has('s')?1:0))*dt));}
  if(this.travelState){const tr=this.travelState;tr.t+=dt*1.5;this.zoom=tr.startZoom+Math.sin(Math.min(1,tr.t)*Math.PI)*2.5;if(tr.t>=1){this.node=tr.node;this.onNode(tr.node);this.travelState=null;this.zoom=1;this.inside=false;this.setMode();this.notice(`Arrived / ${tr.node}. Records remain local; no external service has been contacted.`);}}
  this.draw();
 }
 draw(){const c=this.ctx;c.clearRect(0,0,this.w,this.h);this.hits=[];
  for(const star of this.stars.slice(0,this.quality==='low'?500:1100)){const q=this.project(star.p);c.fillStyle=star.white?'rgba(218,235,248,.58)':`hsla(${star.hue},100%,70%,.8)`;c.fillRect(q.x,q.y,star.size,star.size);}
  const corners=[[-3,-3,-3],[-3,-3,3],[-3,3,-3],[-3,3,3],[3,-3,-3],[3,-3,3],[3,3,-3],[3,3,3]];
  [[0,1],[0,2],[0,4],[1,3],[1,5],[2,3],[2,6],[3,7],[4,5],[4,6],[5,7],[6,7]].forEach(([a,b],i)=>this.path([corners[a],corners[b]],i*31,.55,.8));
  for(const portal of PORTALS){for(let k=0;k<=11;k++){const t=k/11,points=[];for(let a=0;a<=48;a++)points.push(this.portalPoint(portal,t,a/48*TAU));this.path(points,k*31+this.time*4,.65,.7);}for(let a=0;a<24;a++){const pts=[];for(let k=0;k<=18;k++)pts.push(this.portalPoint(portal,k/18,a/24*TAU));this.path(pts,a*15+this.time*3,.7,.7);}const q=this.project(portal.center);this.hits.push({...q,r:55*this.zoom,portal:portal.id});
    for(let k=0;k<24;k++){const t=(k/24+this.time*.1)%1,p=portal.center.map(v=>v*(1-.67*t)),q=this.project(p);c.fillStyle=`hsl(${k*15+this.time*20},100%,60%)`;c.beginPath();c.arc(q.x,q.y,Math.max(2,8*this.zoom*(.6+t*.4)),0,TAU);c.fill();}}
  const r=2.28;for(let k=1;k<20;k++){const lat=-Math.PI/2+k/20*Math.PI,pts=[];for(let a=0;a<=72;a++){const angle=a/72*TAU+this.time*.12;pts.push([Math.cos(lat)*Math.cos(angle)*r,Math.sin(lat)*r,Math.cos(lat)*Math.sin(angle)*r]);}this.path(pts,k*19+this.time*6,.65,.65);}for(let j=0;j<36;j++){const a=j/36*TAU+this.time*.12,pts=[];for(let k=0;k<=40;k++){const t=-Math.PI/2+k/40*Math.PI;pts.push([Math.cos(t)*Math.cos(a)*r,Math.sin(t)*r,Math.cos(t)*Math.sin(a)*r]);}this.path(pts,j*10-this.time*4,.8,.7);}
  // Bright toroidal ribbons: explicitly decorative, not data.
  for(let j=0;j<3;j++)for(let i=0;i<26;i++){const a=i/26*1.8+j*2.1+this.time*.3;const p=[Math.cos(a)*1.3,Math.sin(a)*1.3,Math.sin(a*2+this.time)*.65];const q=this.project(p);c.fillStyle=`hsla(${i*7+j*110+this.time*15},100%,58%,.7)`;c.beginPath();c.arc(q.x,q.y,Math.max(2,q.scale*.13),0,TAU);c.fill();}
  if(this.enabled){for(const item of [...this.items].sort((a,b)=>this.project(a.p).z-this.project(b.p).z)){const q=this.project(item.p),p=item.packet,col=p.channel===8?'#cad9ed':CHANNELS[p.channel-1].hex;c.fillStyle=col;c.shadowColor=col;c.shadowBlur=12;const r=p.pinned?7:5;c.beginPath();c.arc(q.x,q.y,r,0,TAU);c.fill();c.shadowBlur=0;this.hits.push({...q,r:Math.max(13,r),id:p.id});if(p.id===this.selected){c.strokeStyle='#d2ffed';c.lineWidth=1;c.beginPath();c.arc(q.x,q.y,13,0,TAU);c.stroke();c.font='11px system-ui';c.fillStyle='#d5eee7';c.fillText(p.name.slice(0,35),q.x+20,q.y+4);}}}
  c.font='10px ui-monospace,monospace';c.fillStyle='rgba(171,196,205,.65)';c.textAlign='center';c.fillText('SOFTWARE FIELD / WEBGL UNAVAILABLE / NO VR',this.w/2,this.h-112);c.textAlign='left';
 }
}
