import assert from 'node:assert/strict';
import test from 'node:test';
import {createLookPreviews} from '../web/viewer/look-previews.js';
const turn = () => new Promise(r => setTimeout(r, 5));
const items = [{id:'clean',recipe:{stock:'daylight'}},{id:'warm',recipe:{stock:'portrait'}}];

test('repeated playback updates cannot starve a thumbnail batch', async () => {
  const calls=[], shown=[];let resolve;
  const loader=createLookPreviews({delay:0,status(){},show:async(id,url)=>shown.push([id,url]),
    render:(asset,recipe,options)=>{calls.push({asset,recipe,options});return new Promise(r=>resolve=r);}});
  loader.update('clip',items);await turn();
  for(let i=0;i<60;i++)loader.update('clip',structuredClone(items));
  assert.equal(calls.length,1);assert.equal(calls[0].options.signal.aborted,false);
  resolve({after:'daylight.png'});await turn();resolve({after:'portrait.png'});await turn();
  assert.deepEqual(shown,[['clean','daylight.png'],['warm','portrait.png']]);
  loader.update('clip',items);await turn();assert.equal(calls.length,2);
  loader.dispose();
});

test('switching source discards late thumbnails; failed images can be retried', async () => {
  let first;const shown=[],states=[];
  const loader=createLookPreviews({delay:0,status:(id,state)=>states.push([id,state]),
    render:async(asset)=>asset==='old'?await new Promise(r=>first=r):{after:'new.png'},
    show:async(id,url)=>{if(url==='new.png'&&!shown.length){shown.push('failed');throw new Error('Image fetch failed');}shown.push(url);}});
  loader.update('old',items.slice(0,1));await turn();
  loader.update('new',items.slice(0,1));first({after:'old.png'});await turn();
  assert.deepEqual(shown,['failed']);assert.deepEqual(states.at(-1),[null,'error']);
  loader.update('new',items.slice(0,1),true);await turn();
  assert.deepEqual(shown,['failed','new.png']);assert.deepEqual(states.at(-1),[null,'ready']);
  loader.dispose();
});

test('closing and reopening the look tab reuses completed images', async () => {
  let renders=0,images=0;
  const loader=createLookPreviews({delay:0,status(){},render:async()=>{renders++;return {after:'a.png'};},show:async()=>images++});
  loader.update('clip',items);await turn();loader.cancel();loader.update('clip',items);await turn();
  assert.equal(renders,2);assert.equal(images,4);loader.dispose();
});

test('enlarging the same node reuses its decoded-thumbnail URLs', async () => {
  const cache=new Map();let renders=0;
  const options={cache,delay:0,status(){},render:async()=>{renders++;return {after:'a.png'};},show:async()=>{}};
  const inline=createLookPreviews(options);inline.update('clip',items);await turn();inline.dispose();
  const dialog=createLookPreviews(options);dialog.update('clip',items);await turn();
  assert.equal(renders,2);dialog.dispose();
});
