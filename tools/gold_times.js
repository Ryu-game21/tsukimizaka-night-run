// Gold time per course x car, computed by the game itself (goldTime) - headless, like tests/run.js.
// usage: node tools/gold_times.js   (writes api/_gold.mjs)   (the server's floor for submitted laps is a share of it)
// Headless logic tests for the game (no WebGL, no audio, no network).
// usage: node tests/run.js          -> prints PASS/FAIL lines, exit code 1 on any failure
// The game's last <script> is pulled out of site/index.html and a hook exposing internals is injected
// just before the closing "})();". THREE is stubbed except Vector3 / CatmullRomCurve3 (track maths).
const fs=require('fs'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'..','site','index.html'),'utf8');
const i0=html.lastIndexOf('<script>'),i1=html.indexOf('</script>',i0);
let src=html.slice(i0+8,i1);const end=src.lastIndexOf('})();');
src=src.slice(0,end)+`global.__gold=()=>goldTime();global.__t={CARS,COURSES,AI,pl,get N(){return N},get P(){return P},get TH(){return TH},get laps(){return laps},get TL(){return TL},get HW(){return HW},get NR(){return NR},get bestLap(){return best},GROUND,groundApply,tlLimits,get TLP(){return TLP},get TLN(){return TLN},
selectCourse,selectCar,start,frame,setMode,setTM,shiftGear,setWeather,showStep,nextStep,prevStep,toMenu,startReplay,endReplay,startTutorial,
loadRp,keys,get state(){return state},get step(){return step},get sessRp(){return sessRp},get tut(){return tut},get GRIP(){return GRIP},
get BR_P(){return BR_P},get CAR(){return CAR},get rpTime(){return rpTime},get sel(){return sel},get mode(){return mode},get revWarn(){return revWarn},ACH,get ACHS(){return ACHS},setReal(o){REAL=o;realSig='';realChanged();},get wind(){return wind},get tempC(){return tempC},get wxSel(){return wxSel},get timeSel(){return timeSel},parseOpenMeteo,achLoad,renderAch,encodeGhost,decodeGhost,get ghost(){return ghost},get ghostInfo(){return ghostInfo},get ownGhost(){return ownGhost},get shared(){return shared},RIGS,rigUpdate,profSummary,publishProf,renderProf,profPlayers,openProf,cleanProf,get PROFS(){return PROFS},set PROFS(v){PROFS=v},STORE_:null,get wqP(){return wq},get scar(){return scar},goldTime,chDailies,chWeekly,chEv,chSync,totalPts,lvOf,renderChal,cosSet,cosGet,chOwnedTitles,TITLES,get chToday(){return chToday},set chToday(v){chToday=v},get chWk(){return chWk},set chWk(v){chWk=v},cleanProf,get SCL(){return SCL},get LAPS(){return LAPS},get RD(){return RD},get vT(){return vT},get ds(){return ds},tyreReset,get tyreK(){return tyreK},get tyreT(){return tyreT},get tyreStat(){return tyreStat},fieldList,get L(){return L},get raceT(){return raceT},opts,crCheck,crReset(){crSeen=null;crLive=false;crQ.length=0;crShowing=false;delete __LS['fpr-crseen'];},addBoard(r){board=board.concat(r);},get crShowing(){return crShowing},get crQ(){return crQ},GR,grResultRows,csPull,csPush,csMergeAch,achBlank,set ACHS(v){ACHS=v},get csDoc(){return csDoc},towerEntries,get towerPos(){return towerPos},get finishRank(){return finishRank}};\n`+src.slice(end);
function U(name='u'){const f=function(){};return new Proxy(f,{
  get(t,k){if(k===Symbol.toPrimitive)return()=>0;if(k==='then')return undefined;if(k==='length')return 0;if(k===Symbol.iterator)return function*(){};return U(name+'.'+String(k));},
  set(){return true;},apply(){return U(name+'()');},construct(){return U('new '+name);} });}

class V3{constructor(x=0,y=0,z=0){this.x=x;this.y=y;this.z=z;}set(x,y,z){this.x=x;this.y=y;this.z=z;return this;}copy(v){return this.set(v.x,v.y,v.z);}
 subVectors(a,b){return this.set(a.x-b.x,a.y-b.y,a.z-b.z);}normalize(){const l=Math.hypot(this.x,this.y,this.z)||1;return this.set(this.x/l,this.y/l,this.z/l);}
 distanceTo(v){return Math.hypot(this.x-v.x,this.y-v.y,this.z-v.z);}applyQuaternion(){return this;}clone(){return new V3(this.x,this.y,this.z);}}
class Curve{constructor(p){this.p=p;}getSpacedPoints(n){const out=[],m=this.p.length;for(let i=0;i<=n;i++){const f=i/n*m,k=Math.floor(f)%m,t=f-Math.floor(f),a=this.p[k],b=this.p[(k+1)%m];out.push(new V3(a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,a.z+(b.z-a.z)*t));}return out;}
 getLength(){let L=0;for(let i=0;i<this.p.length;i++)L+=this.p[i].distanceTo(this.p[(i+1)%this.p.length]);return L;}}
const base=U('THREE');
global.THREE=new Proxy({},{get(t,k){if(k==='Vector3')return V3;if(k==='CatmullRomCurve3')return Curve;return base[k];}});

const els={};
global.document={getElementById:id=>els[id]||(els[id]=U('#'+id)),querySelectorAll:()=>[],querySelector:()=>null,createElement:()=>U('el'),addEventListener(){},fonts:{ready:Promise.resolve()},activeElement:null,body:U('body')};
global.window=global;global.addEventListener=()=>{};global.matchMedia=()=>({matches:false});
const LS={'fpr-player':'T'};global.localStorage={getItem:k=>k in LS?LS[k]:null,setItem(k,v){LS[k]=String(v)},removeItem(k){delete LS[k]},get length(){return Object.keys(LS).length},key:i=>Object.keys(LS)[i]};global.__LS=LS;global.requestAnimationFrame=()=>{};global.performance={now:()=>0};
global.innerWidth=1400;global.innerHeight=800;global.devicePixelRatio=1;global.navigator={};
// fake shared database (same calls the game makes): one signed-in viewer U1 plus a rival U2 seeded below
const STORE={'records/U2':{players:[{name:'Rival',best:{'tsukimi__s30z':{t:20.5,at:1}}}]}};console.warn=()=>{};
const fakeDb={doc:p=>({set:async v=>{STORE[p]=JSON.parse(JSON.stringify(v));},get:async()=>({exists:p in STORE,data:()=>STORE[p]}),onSnapshot(cb){setTimeout(()=>cb({exists:p in STORE,data:()=>STORE[p]}),0);return()=>{};}}),
  collection:p=>({onSnapshot(cb){const docs=Object.keys(STORE).filter(k=>k.startsWith(p+'/')&&k.split('/').length===2).map(k=>({id:k.split('/')[1],data:()=>STORE[k]}));setTimeout(()=>cb({docs}),0);return()=>{};}})};
global.fetch=async()=>({status:503,ok:false,json:async()=>({error:true,reason:'offline test'})});global.claude={use:async n=>n==='db'?fakeDb:n==='user'?{id:async()=>'U1',can:()=>true}:null};

console.warn=()=>{};console.error=()=>{};
eval(src);global.AudioContext=function(){return U('ac');};
const t=global.__t;let now=0;const step=n=>{for(let k=0;k<n;k++){now+=16;t.frame(now);}};
const res={};
t.COURSES.forEach((c,ci)=>{res[c.id]={};t.CARS.forEach((car,k)=>{if(car.hide)return;t.selectCar(k);t.selectCourse(ci);t.setMode('free');t.start();step(2);res[c.id][car.id]=Math.round(global.__gold()*100)/100;t.toMenu&&t.toMenu();});});
fs.writeFileSync(path.join(__dirname,'..','api','_gold.mjs'),'// generated by tools/gold_times.js - the game\'s gold time (s) per course x car\nexport default '+JSON.stringify(res)+';\n');console.log('wrote api/_gold.mjs',Object.keys(res).length,'courses');
