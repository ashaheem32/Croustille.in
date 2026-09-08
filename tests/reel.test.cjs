const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('script.js', 'utf8');
const block = source.slice(source.indexOf('  const reelSection'), source.indexOf('  /* ── Scroll-linked drift'));
function setup(reduceMotion = false) {
  let frames = new Map(), next = 0, seeks = [], classes = new Set(), props = new Map(), listeners = {}, time = 0;
  const caps = [0, 1].map(() => ({on:false, classList:{toggle(_, on){this.owner.on=on;}}}));
  caps.forEach(c => c.classList.owner=c);
  const video = {duration:19.24, readyState:0, seeking:false, pause(){}, load(){}, removeAttribute(){},
    addEventListener(e, fn){(listeners[e] ||= []).push(fn);},
    get currentTime(){return time;}, set currentTime(t){assert.equal(this.seeking,false,'overlapping seek'); time=t; this.seeking=true; seeks.push(t);}};
  const section = {querySelector(){return {};}, querySelectorAll(){return caps;}, classList:{add(c){classes.add(c);},remove(c){classes.delete(c);}},style:{setProperty(k,v){props.set(k,v);},removeProperty(k){props.delete(k);}}};
  const ctx = vm.createContext({reduceMotion, document:{querySelector(){return section;},getElementById(){return video;}},window:{},requestAnimationFrame(fn){frames.set(++next,fn);return next;},cancelAnimationFrame(id){frames.delete(id);},queueDrift(){},console});
  vm.runInContext(block+'\nglobalThis.target = p => {reelTarget=p;queueReel();};',ctx);
  const emit = e => (listeners[e]||[]).forEach(fn=>fn());
  const flush = () => {const batch=[...frames.values()];frames.clear();batch.forEach(fn=>fn());};
  return {video,seeks,caps,classes,props,emit,flush,target:ctx.target,settle(){video.seeking=false;emit('seeked');flush();}};
}
const t=setup();
t.emit('loadedmetadata');t.flush();assert.equal(t.classes.size,0,'metadata alone must not pin');
t.video.readyState=2;t.emit('loadeddata');t.flush();assert(t.classes.has('reel--live'));
t.target(.25);t.flush();assert.equal(t.seeks.length,1);
t.target(.8);t.flush();assert.equal(t.seeks.length,1,'wait for decode');assert(t.caps[0].on);
t.settle();assert.equal(t.seeks.length,2);t.settle();assert(t.caps[1].on);
t.target(.1);t.flush();t.settle();assert(Math.abs(t.video.currentTime-1.924)<.001);assert(t.caps[0].on);
t.video.readyState=1;t.target(.6);t.flush();const count=t.seeks.length;t.video.readyState=2;t.emit('progress');t.flush();assert.equal(t.seeks.length,count+1);t.settle();
t.target(1);t.flush();t.settle();assert(t.video.currentTime<t.video.duration);
t.emit('error');assert.equal(t.classes.size,0);assert.equal(t.props.size,0);
const reduced=setup(true);reduced.video.readyState=2;reduced.emit('loadeddata');reduced.flush();assert.equal(reduced.classes.size,0);
console.log('PASS: loading, serialized seeks, latest target, reverse, buffering recovery, end frame, media error, reduced motion');
