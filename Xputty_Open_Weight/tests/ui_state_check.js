// Pure DOM-state test: no browser automation or network access.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{id,value:'',disabled:false,hidden:false,style:{},classList:{add(){},remove(){},toggle(){}},addEventListener(){},replaceChildren(){},append(){},add(){},close(){},showModal(){},getContext(){return {scale(){},fillRect(){},createRadialGradient(){return {addColorStop(){}}}}},querySelectorAll(){return controls.map(element)}});return elements.get(id)}
const controls=['preset','mode','weight256','weight512','weight1024','weight2048','ramp','warmup','horizon','tokenbudget','savesetup'];
const presets={
 'research-48m-v1':{parameters:48116224,vocab_size:8192,max_context:2048,windows:[256,512,1024,2048],window_weights:[4,3,2,1],ramp_updates:1000,warmup_updates:100,schedule_updates:10000,tokens_per_update:512},
 'tiny-1m-v1':{parameters:1614720,vocab_size:4096,max_context:512,windows:[512],window_weights:[1],ramp_updates:0,warmup_updates:0,schedule_updates:10000,tokens_per_update:1024}
};
const context=vm.createContext({console,document:{getElementById:element,activeElement:null,createElement:()=>element('new')},sessionStorage:{getItem(){return null},setItem(){}},location:{origin:'http://local.test',hash:'',pathname:'/'},history:{replaceState(){}},URL,URLSearchParams,Option:function(){},innerWidth:1000,innerHeight:800,devicePixelRatio:1,addEventListener(){},setInterval(){},setTimeout(){},window:{open(){}},fetch:async url=>({ok:true,json:async()=>url.endsWith('/api/presets')?presets:url.endsWith('/api/projects')?[]:{}})});
vm.runInContext(fs.readFileSync('web/app.js','utf8'),context);
setImmediate(()=>{
 try{
  const state={id:'old',status:'draft',preset:'tiny-1m-v1',files:[],build_config:presets['tiny-1m-v1']};
  vm.runInContext(`renderSetup(${JSON.stringify(state)})`,context);
  assert.equal(element('weight2048').disabled,true);
  element('preset').value='research-48m-v1';element('preset').onchange();
  // A polling refresh must not revert a pending preset change or disable its windows.
  vm.runInContext(`renderSetup(${JSON.stringify(state)})`,context);
  assert.equal(element('weight2048').disabled,false);
  const selected=vm.runInContext('JSON.stringify(readSettings())',context);
  assert.deepEqual(JSON.parse(selected).windows,[256,512,1024,2048]);
  vm.runInContext(`renderSetup(${JSON.stringify({...state,status:'stopped'})})`,context);
  assert.equal(element('preset').disabled,true);
  console.log('UI state checks passed: preset selection survives polling; windows and locked controls agree.');
 }catch(error){console.error(error);process.exitCode=1}
});
