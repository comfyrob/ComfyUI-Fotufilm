/** Run with Node and jsdom available (NODE_PATH may point at an existing install). */
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import test from 'node:test';
const { JSDOM } = createRequire(import.meta.url)('jsdom');
const dom = new JSDOM('<!doctype html><body></body>', { url: 'https://comfy.test/', pretendToBeVisual: true });
for (const name of ['window','document','AbortController','DOMException','HTMLElement']) globalThis[name] = dom.window[name];
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame.bind(dom.window);
globalThis.cancelAnimationFrame = dom.window.cancelAnimationFrame.bind(dom.window);
for (const name of ['load','pause']) dom.window.HTMLMediaElement.prototype[name] = function() {};
const { createStudio } = await import('../web/viewer/studio.js');
const { createPreviewClient } = await import('../web/viewer/preview-client.js');
const { baseRecipe } = await import('../web/viewer/model.js');
const flush = () => new Promise(resolve => setImmediate(resolve));
const asset = { asset:'first', info:{width:3840,height:2160,frames:240,fps:24,hdr:true} };

test('Studio leaves still saving, scopes and source correction to graph nodes', () => {
  const studio=createStudio({recipe:baseRecipe()});document.body.append(studio.element);
  assert.equal(studio.element.querySelector('.ff-inspection'),null);
  assert.equal(studio.element.querySelector('.ff-scopes'),null);
  assert.equal(studio.element.querySelector('[data-grade-stage="balance"]'),null);
  assert.equal(studio.element.querySelector('[data-action="render"]'),null);
  assert.equal(studio.element.querySelector('.ff-legacy-balance').hidden,true);
  studio.dispose();
});

test('preview client uses the inspection endpoint and retains the original EXR URL', async () => {
  const calls=[];
  const api={apiURL:path=>'https://comfy.test'+path,fetchApi:async(path,options)=>{
    calls.push([path,options]);return {ok:true,json:async()=>path.endsWith('/inspect')?{job:'one'}:{status:'complete',result:{exr:{filename:'frame.exr',subfolder:'fotufilm-inspections',type:'output'}}}};
  }};
  const client=createPreviewClient(api);
  const result=await client.render('source',{}, {mode:'inspect',frame:9,stage:'film'});
  assert.equal(calls[0][0],'/fotufilm/inspect');assert.equal(JSON.parse(calls[0][1].body).frame,9);
  assert.match(result.exr,/filename=frame.exr/);assert.doesNotMatch(result.exr,/preview=/);
  assert.ok(calls.every(([path])=>!path.includes('prompt')));
  client.dispose();
});

test('playing timeline seeks update the stream without exporting or queueing the graph', async () => {
  const updates=[];let renders=0,queues=0;
  const studio=createStudio({source:'https://comfy.test/input.mp4',asset,
    preview:{live:()=>({update:value=>updates.push(value),close(){}}),render:()=>{renders++;throw new Error('Unexpected clip render');}},
    onRender:()=>queues++});
  document.body.append(studio.element);
  const video=studio.element.querySelector('video');
  Object.defineProperty(video,'duration',{value:10,configurable:true});
  Object.defineProperty(video,'paused',{value:false,configurable:true});
  const slider=studio.element.querySelector('.ff-scrubber');slider.max='10';slider.value='2';
  slider.dispatchEvent(new dom.window.Event('input'));
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal(updates.at(-1).frame,48);assert.equal(updates.at(-1).playing,true);
  assert.equal(renders,0);assert.equal(queues,0);
  studio.dispose();
});

test('everyday adjustments and visible wheels edit the finish without altering existing input corrections', () => {
  const recipe=baseRecipe();recipe.grading.balance.exposure=1.25;
  const studio=createStudio({recipe});document.body.append(studio.element);
  const root=studio.element;root.querySelector('[data-action="tab-grade"]').click();
  assert.equal(root.querySelector('.ff-legacy-balance').hidden,false);
  const slider=root.querySelector('.ff-grade-quick [data-grade="exposure"]');
  slider.value='.5';slider.dispatchEvent(new dom.window.Event('input'));
  assert.equal(studio.getRecipe().grading.finish.exposure,.5);
  assert.equal(studio.getRecipe().grading.balance.exposure,1.25);
  assert.equal(root.querySelectorAll('.ff-wheels-primary .ff-wheel').length,3);
  const wheel=root.querySelector('.ff-wheels-primary [data-wheel="lift"] [role="slider"]');
  assert.equal(wheel.closest('details'),null);
  wheel.dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
  assert.ok(studio.getRecipe().grading.finish.lift[0]>0);
  assert.deepEqual(studio.getRecipe().grading.balance.lift,[0,0,0]);
  root.querySelector('[aria-label="Reset shadows wheel"]').click();
  assert.deepEqual(studio.getRecipe().grading.finish.lift,[0,0,0]);
  root.querySelector('[data-action="reset-grade"]').click();
  assert.equal(studio.getRecipe().grading.finish.exposure,0);
  assert.equal(studio.getRecipe().grading.balance.exposure,1.25);
  studio.dispose();
});

test('legacy input correction stays intact until explicitly cleared and undo restores it', () => {
  const recipe=baseRecipe();recipe.grading.balance.exposure=1.25;
  const studio=createStudio({recipe});document.body.append(studio.element);
  studio.element.querySelector('[data-action="reset-input"]').click();
  assert.equal(studio.getRecipe().grading.balance.exposure,0);
  assert.equal(studio.element.querySelector('.ff-legacy-balance').hidden,true);
  studio.element.querySelector('[data-action="undo"]').click();
  assert.equal(studio.getRecipe().grading.balance.exposure,1.25);
  studio.dispose();
});

test('numeric edits commit once, Escape cancels, and undo keeps look identity', () => {
  let closes=0;
  const studio=createStudio({recipe:baseRecipe(),lookId:'clean',onClose:()=>closes++});
  document.body.append(studio.element);const root=studio.element;
  const input=root.querySelector('.ff-grade-quick [aria-label="Grade Exposure value EV"]');
  input.focus();input.value='.25';
  assert.equal(studio.getRecipe().grading.finish.exposure,0);
  input.dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  assert.equal(studio.getRecipe().grading.finish.exposure,.25);
  input.focus();input.value='1.5';input.dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  assert.equal(studio.getRecipe().grading.finish.exposure,.25);assert.equal(closes,0);
  root.querySelector('[data-action="undo"]').click();
  assert.equal(studio.getRecipe().grading.finish.exposure,0);assert.equal(studio.getLookId(),'clean');
  input.value='900';input.dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  assert.equal(studio.getRecipe().grading.finish.exposure,5);
  studio.dispose();
});

test('look browsing preserves input corrections, explicit color override and undo/reset semantics', () => {
  const recipe=baseRecipe();recipe.grading.balance.exposure=1.25;recipe.grading.finish.saturation=.73;
  const studio=createStudio({recipe,lookId:'clean'});document.body.append(studio.element);const root=studio.element;
  root.querySelector('[data-look="pastel"]').click();
  assert.equal(studio.getRecipe().grading.balance.exposure,1.25);
  assert.equal(studio.getRecipe().grading.finish.saturation,.9); // Preset default.
  root.querySelector('[data-action="undo"]').click();
  assert.equal(studio.getLookId(),'clean');assert.equal(studio.getRecipe().grading.finish.saturation,.73);
  root.querySelector('.ff-keep-finish').checked=true;
  root.querySelector('[data-look="pastel"]').click();
  assert.equal(studio.getRecipe().grading.finish.saturation,.73);
  root.querySelector('[data-action="reset"]').click();
  assert.equal(studio.getRecipe().grading.balance.exposure,1.25);assert.equal(studio.getRecipe().grading.finish.saturation,.9);
  studio.dispose();
});

test('trial export uses current source frame, original resolution and can be cancelled', async () => {
  const calls=[];let finish;
  const studio=createStudio({asset,preview:{render:(_a,_r,options)=>{calls.push(options);return new Promise(resolve=>finish=resolve);}}});
  document.body.append(studio.element);studio.element.querySelector('video').currentTime=2;
  studio.element.querySelector('[data-action="test-export"]').click();
  assert.equal(calls[0].start,48);assert.equal(calls[0].range,'trial');assert.equal(calls[0].edge,undefined);
  assert.equal(studio.element.querySelector('[data-action="export"]').disabled,true);
  studio.element.querySelector('[data-action="cancel-export"]').click();assert.equal(calls[0].signal.aborted,true);
  finish({after:'trial.mp4'});await flush();studio.dispose();
});
