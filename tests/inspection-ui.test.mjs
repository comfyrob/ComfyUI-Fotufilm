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
const flush = () => new Promise(resolve => setImmediate(resolve));
const asset = { asset:'first', info:{width:3840,height:2160,frames:240,fps:24,hdr:true} };

test('inspection captures playhead, stage and full recipe without queueing a graph or a clip', async () => {
  const calls=[];let queues=0;
  const studio=createStudio({asset,preview:{render:async (...args)=>{calls.push(args);return {exr:'/view?filename=frame.exr',assetId:'id'};}},onRender:()=>queues++});
  document.body.append(studio.element);
  studio.element.querySelector('video').currentTime=3;
  studio.element.querySelector('.ff-inspection-stage').value='balance';
  const button=studio.element.querySelector('[data-action="inspect"]');button.click();
  assert.equal(button.disabled,true);await flush();
  assert.equal(calls.length,1);assert.equal(calls[0][0],'first');
  assert.equal(calls[0][2].mode,'inspect');assert.equal(calls[0][2].frame,72);assert.equal(calls[0][2].stage,'balance');
  assert.equal(calls[0][2].edge,undefined);assert.equal(queues,0);
  assert.equal(studio.element.querySelector('.ff-inspection-download').hidden,false);
  assert.match(studio.element.querySelector('.ff-inspection-status').textContent,/frame 72/);
  studio.dispose();
});

test('switching source cancels inspection and cannot expose the previous source result', async () => {
  let finish,signal;
  const studio=createStudio({asset,preview:{render:(_a,_r,options)=>{signal=options.signal;return new Promise(resolve=>finish=resolve);}}});
  document.body.append(studio.element);
  studio.element.querySelector('[data-action="inspect"]').click();
  studio.setAsset({...asset,asset:'second'});assert.equal(signal.aborted,true);
  finish({exr:'/view?filename=old.exr'});await flush();
  assert.equal(studio.element.querySelector('.ff-inspection-download').hidden,true);
  assert.equal(studio.element.querySelector('[data-action="inspect"]').disabled,false);
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
