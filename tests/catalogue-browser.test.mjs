import assert from 'node:assert/strict';
import test from 'node:test';
import {createRequire} from 'node:module';
import {films, looks, stockMetadata, baseRecipe} from '../web/viewer/model.js';
import {filterLooks, previewLooks, readFavorites, writeFavorites} from '../web/viewer/catalogue-browser.js';
const {JSDOM}=createRequire(import.meta.url)('jsdom');
const dom=new JSDOM('<body></body>',{url:'https://comfy.test/',pretendToBeVisual:true});
for(const name of ['window','document','AbortController','DOMException','HTMLElement'])globalThis[name]=dom.window[name];
globalThis.requestAnimationFrame=dom.window.requestAnimationFrame.bind(dom.window);
globalThis.cancelAnimationFrame=dom.window.cancelAnimationFrame.bind(dom.window);
for(const name of ['load','pause'])dom.window.HTMLMediaElement.prototype[name]=function(){};
const {createStudio}=await import('../web/viewer/studio.js');
const flush=()=>new Promise(resolve=>setImmediate(resolve));

test('every stock dependency has profile provenance and a supported format',()=>{
  assert.equal(films.length,28);assert.equal(looks.length,54);
  const ids=new Set(films.map(([id])=>id));assert.equal(ids.size,28);
  for(const look of looks)assert.ok(ids.has(look.film),look.id);
  for(const id of ids){assert.equal(stockMetadata[id].profile,`${id}.json`);assert.ok(stockMetadata[id].provenance);assert.ok(['super8','16mm','super35','35mm','120'].includes(stockMetadata[id].defaults.format));}
});

test('search combines collection, stock name and favorites without changing recipes',()=>{
  assert.ok(filterLooks({query:'KODACHROME'}).length>=3);
  assert.equal(filterLooks({query:'kodachrome',group:'portrait'}).length,0);
  assert.deepEqual(filterLooks({favoritesOnly:true,favorites:new Set(['travel-chrome'])}).map(x=>x.id),['travel-chrome']);
  assert.equal(filterLooks({query:'not a real look'}).length,0);
});

test('only visible cards and the selected look request rendering; unavailable stocks are excluded',()=>{
  const result=previewLooks(looks,['warm','travel-chrome','grainy-night'],'clean',stock=>stock!=='delta3200');
  assert.deepEqual(result.map(x=>x.id),['clean','warm','travel-chrome']);
  assert.deepEqual(previewLooks([],[],'clean',()=>false),[]);
});

test('favorites tolerate blocked storage, malformed data and removed look IDs',()=>{
  const storage={getItem:()=>'{broken'};assert.deepEqual([...readFavorites(storage)],[]);
  storage.getItem=()=>JSON.stringify(['clean','removed',null]);assert.deepEqual([...readFavorites(storage)],['clean']);
  assert.doesNotThrow(()=>writeFavorites(undefined,new Set(['clean'])));
});

test('search and favorite buttons never apply a look, and favorites survive reopening',()=>{
  window.localStorage.clear();
  const studio=createStudio({editorMode:'film'});document.body.append(studio.element);
  const root=studio.element,before=studio.getRecipe(),search=root.querySelector('.ff-look-search');
  root.querySelector('[data-favorite="travel-chrome"]').click();
  root.querySelector('[data-action="favorite-filter"]').click();
  assert.deepEqual([...root.querySelectorAll('.ff-look-entry:not([hidden])')].map(x=>x.dataset.entry),['travel-chrome']);
  search.value='no match';search.dispatchEvent(new window.Event('input'));
  assert.equal(root.querySelector('.ff-look-empty').hidden,false);
  assert.deepEqual(studio.getRecipe(),before);studio.dispose();
  const next=createStudio();assert.equal(next.element.querySelector('[data-favorite="travel-chrome"]').getAttribute('aria-pressed'),'true');next.dispose();
});

test('server stock inventory disables missing profiles without silently replacing the recipe',async()=>{
  const recipe=baseRecipe(),studio=createStudio({recipe,preview:{catalogue:async()=>({engine:'test',stocks:['vision250d']})}});
  await flush();
  assert.equal(studio.element.querySelector('[data-look="clean"]').disabled,false);
  assert.equal(studio.element.querySelector('[data-look="travel-chrome"]').disabled,true);
  assert.equal(studio.element.querySelector('[data-film="kodachrome64"]').disabled,true);
  studio.element.querySelector('[data-look="travel-chrome"]').click();
  assert.deepEqual(studio.getRecipe(),recipe);studio.dispose();
});

test('failed inventory leaves selectors unavailable and explains recovery',async()=>{
  const studio=createStudio({preview:{catalogue:async()=>{throw new Error('offline');}}});await flush();
  assert.ok([...studio.element.querySelectorAll('[data-look]')].every(button=>button.disabled));
  assert.match(studio.element.querySelector('.ff-catalogue-note').textContent,/Could not check server stocks/);studio.dispose();
});
