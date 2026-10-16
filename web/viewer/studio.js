import { baseRecipe, clone, films, formats, looks, lookGroups, looksInGroup, lookRecipe, matchLook, filmName, sameRecipe, timecode, neutralGrade, normalizeRecipe, selectLook } from './model.js';
import {composeGrade,gradeOverrides} from './stage-recipe.js';
import {attachNumericControl} from './numeric-control.js';
import {createLookPreviews} from './look-previews.js';
import {filterLooks, previewLooks, readFavorites, writeFavorites} from './catalogue-browser.js';

const icons = {
  play: '<path d="m8 5 11 7-11 7z"/>', pause: '<path d="M8 5v14M16 5v14"/>',
  back: '<path d="M6 5v14m12-14L8 12l10 7z"/>', next: '<path d="M18 5v14M6 5l10 7-10 7z"/>',
  loop: '<path d="M19 8a7 7 0 0 0-12-3L4 8m0-5v5h5m-4 8a7 7 0 0 0 12 3l3-3m0 5v-5h-5"/>',
  audio: '<path d="m11 4-6 5H2v6h3l6 5zM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
  mute: '<path d="m11 4-6 5H2v6h3l6 5zM16 9l6 6m0-6-6 6"/>',
  expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  compare: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 2v20"/>',
  undo: '<path d="M4 9h10a6 6 0 0 1 0 12M4 9l5-5M4 9l5 5"/>',
  check: '<path d="m5 12 4 4 10-10"/>', chevron: '<path d="m9 5 7 7-7 7"/>',
  film: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M7 3v18M17 3v18M3 8h4m-4 8h4m10-8h4m-4 8h4"/>',
  folder: '<path d="M3 7V4h6l3 3h9v13H3z"/>',
};
export const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || ''}</svg>`;
const button = (name, label, svg, extra = '') => `<button type="button" data-action="${name}" ${extra}>${svg ? icon(svg) : ''}${label ? `<span>${label}</span>` : ''}</button>`;
const iconButton = (name, label, svg) => button(name, '', svg, `class="ff-icon-button" aria-label="${label}" title="${label}"`);

export function createStudio(options = {}) {
  const editorMode=options.editorMode||'studio';
  let baseGradeRecipe=normalizeRecipe(options.baseRecipe||options.recipe||baseRecipe());
  const view={mode:'output',exposure:0,stage:'finish',comparison:editorMode==='grade'?'film':'source'};
  const gradeDefault=()=>editorMode==='grade'?baseGradeRecipe.grading.finish:neutralGrade();
  const abort = new AbortController();
  const on = (element, event, callback) => element.addEventListener(event, callback, { signal: abort.signal });
  const root = document.createElement('section');
  root.className = 'ff-studio';
  root.setAttribute('aria-label', 'Fotufilm studio');
  let recipe = normalizeRecipe(options.recipe || baseRecipe());
  let gradeChanges=clone(options.adjustments||gradeOverrides(baseGradeRecipe,recipe));
  let previousGrade=clone(recipe.grading.finish);
  let startingRecipe = clone(recipe);
  let selectedLook = looks.some(look=>look.id===options.lookId) ? options.lookId : matchLook(recipe)?.id || null;
  let startingLook = selectedLook;
  let lookGroup = 'all', lookQuery = '', favoritesOnly = false;
  let favoriteStorage;try{favoriteStorage=window.localStorage;}catch{}
  const favorites=readFavorites(favoriteStorage);
  let availableStocks=null, catalogueReady=!options.preview?.catalogue, catalogueError='', renderEngine='';
  const stockAvailable=id=>catalogueReady && (availableStocks===null || availableStocks.has(id));
  const visibleLookIds=new Set();
  let lookObserver=null, viewportTimer=0;

  let tab = 'looks', sourceMode = options.asset?.info?.hdr ? 'hdr' : 'original', comparing = false, zoom = 1, rate = 1;
  let sources = {original: options.source || '', hdr: options.enhanced || ''};
  let rendered = options.rendered || '';
  let renderedRecipe = options.renderedRecipe || null;
  let label = options.label || 'Your video';
  let fps = Math.max(1, options.fps || 24);
  let asset=options.asset||null, previewController=null, previewTimer=0, previewKey='', previewStatus='', previewEdge=1280, stillReady=false;
  let activeRenderedSource=sourceMode, previewClipKey='', pendingClipKey='', clipController=null, stillFrame=-1, swappingMedia=false;
  let hasHDR=Boolean(options.hasHDR||asset?.info?.hdr), exporting=false, exportController=null;
  let live=null, liveFrame=-1, liveStatsStart=0, liveFrames=0, deliveredFPS=0;
  const snapshot = () => ({recipe:clone(recipe),lookId:selectedLook});
  const history=[snapshot()]; let historyTimer=0, interacting=false, editStarted=0;
  const numericControls=new WeakMap();
  let frameCallback = 0, raf = 0, thumbnailToken = 0, destroyed = false;
  let ownedURLs = [], pan = {x: 0, y: 0}, lastPointer = null;
  root.innerHTML = `
    <header class="ff-header">
      <div class="ff-brand">${icon('film')}<strong>Fotufilm</strong><span class="ff-header-slash">/</span><span>Studio</span></div>
      <span class="ff-prototype">Interface preview</span>
      <div class="ff-header-actions">${button('cancel', 'Cancel')}${button('save', 'Save to node', 'check', 'class="ff-primary"')}</div>
    </header>
    <div class="ff-workspace">
      <main class="ff-main">
        <div class="ff-sourcebar">
          <div class="ff-file"><span class="ff-file-name"></span><span class="ff-file-info"></span></div>
          <div class="ff-source-switch" role="group" aria-label="Video source"><span>Source</span>
            ${button('source-original', 'Original', '', 'aria-pressed="true"')}
            ${button('source-hdr', 'Enhanced HDR', '', 'aria-pressed="false" title="Switch between your original video and reconstructed float HDR master."')}
          </div>
        </div>
        <div class="ff-stage" tabindex="0" aria-label="Video preview. Space to play or pause. Arrow keys to step frames.">
          <div class="ff-picture"><video class="ff-main-video" playsinline preload="auto" muted></video>
            <canvas class="ff-live-after" hidden></canvas><img class="ff-after-still" alt="Fotufilm preview" hidden/><div class="ff-before"><video class="ff-before-video" playsinline preload="auto" muted></video><canvas class="ff-live-before" hidden></canvas><img class="ff-before-still" alt="Source before finishing" hidden/></div>
          </div>
          <div class="ff-stage-label ff-stage-left" hidden>Original</div><div class="ff-stage-label ff-stage-right"></div>
          <label class="ff-wipe" hidden><span class="ff-wipe-line"><span>↔</span></span><input type="range" min="0" max="100" value="50" aria-label="Before and after divider"></label>
          <div class="ff-empty">${icon('film')}<h2>Your footage, in a new light.</h2><p>Connect a loaded video. Existing files appear without running the graph.</p>${button('open-file', 'Open video', 'folder')}<small>Connect linear HDR frames from LTX to the images input. Saving a master is optional.</small></div>
          <div class="ff-video-error" role="alert" hidden></div>
        </div>
        <div class="ff-transport">
          <div class="ff-playback">${iconButton('back', 'Previous frame (Left arrow)', 'back')}${iconButton('play', 'Play (Space)', 'play')}${iconButton('next', 'Next frame (Right arrow)', 'next')}<span class="ff-time">00:00:00 <span>/ 00:00:00</span></span></div>
          <div class="ff-view-actions">${button('compare', 'Before / after', 'compare', 'aria-pressed="false" title="Drag the divider to compare this source before and after grading and film."')}${iconButton('loop', 'Loop playback', 'loop')}${iconButton('audio', 'Unmute audio', 'mute')}<label class="ff-rate"><span class="ff-sr-only">Playback speed</span><select aria-label="Playback speed"><option value=".5">0.5×</option><option value="1" selected>1×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></label><span class="ff-divider"></span>${button('fit', 'Fit', '', 'aria-pressed="true"')}${button('minus', '−', '', 'aria-label="Zoom out"')}<span class="ff-zoom">100%</span>${button('plus', '+', '', 'aria-label="Zoom in"')}${iconButton('fullscreen', 'Fullscreen viewer', 'expand')}</div>
        </div>
        <div class="ff-timeline">
          <div class="ff-ticks" aria-hidden="true"><span>00:00</span><span>00:01</span><span>00:02</span><span>00:03</span><span>00:04</span><span>00:05</span></div>
          <div class="ff-filmstrip" aria-hidden="true">${Array.from({length:12},()=>'<span></span>').join('')}</div>
          <div class="ff-playhead" aria-hidden="true"></div><input class="ff-scrubber" type="range" aria-label="Video timeline" min="0" max="1" step="0.001" value="0">
        </div>
        <details class="ff-view-inspector"><summary>Inspect HDR <span>Viewing tools · export unchanged</span></summary>
        <div class="ff-view-settings" aria-label="Monitor settings">
          <label>Display mapping <select class="ff-view-mode" title="Fits HDR brightness onto this SDR preview. Does not change your grade or export."><option value="output">SDR output</option><option value="rolloff">Compress highlights</option><option value="clip">Show clipping</option></select></label>
          <label>Processing stage <select class="ff-view-stage"><option value="finish">Finished result</option><option value="film">Film before color grade</option><option value="source">Connected source</option></select></label>
          <label title="Temporary viewing exposure. Lower it to inspect bright detail; use Exposure in Color Grade to change the finished video.">Preview brightness <input class="ff-view-ev" type="number" min="-10" max="10" step=".25" value="0" aria-label="Viewer exposure"/> EV</label>
          <span class="ff-view-note">Return to SDR output · Finished result · 0 EV for the normal view.</span>
        </div></details>
        <div class="ff-monitor-status"><span class="ff-display">SDR video preview</span><span class="ff-render-state">Source playback</span></div>
      </main>
      <aside class="ff-sidebar" aria-label="Film recipe">
        <div class="ff-current"><div class="ff-current-preview" aria-hidden="true"><img alt="" hidden/>${icon('film')}</div><div class="ff-current-copy"><span class="ff-current-label">Selected look</span><div class="ff-look-title"><h1 aria-live="polite"></h1><span class="ff-modified" hidden>Modified</span></div><p class="ff-recipe-summary"></p></div>${iconButton('reset', 'Reset this look', 'undo')}</div>
        <nav class="ff-tabs" aria-label="Recipe editor">${button('tab-looks', 'Looks', '', 'aria-pressed="true"')}${button('tab-customize', 'Film', '', 'aria-pressed="false"')}${button('tab-grade','Color & texture','','aria-pressed="false"')}</nav>
        <div class="ff-panel-content">
          <section class="ff-looks-panel"><p class="ff-intro">One look. Film, color and texture together.</p><label class="ff-keep-color" title="Keep your current finishing color adjustments when choosing a look."><input type="checkbox" class="ff-keep-finish"> Keep my color settings</label><div class="ff-look-search-row"><input class="ff-look-search" type="search" aria-label="Search looks or film stocks" placeholder="Search looks or stocks"/><button type="button" data-action="favorite-filter" aria-pressed="false" title="Show your favorite looks">☆ Favorites</button></div><div class="ff-look-filters" role="group" aria-label="Filter looks">${lookGroups.map(([id,label])=>`<button type="button" data-look-group="${id}" aria-pressed="${id===lookGroup}">${label}</button>`).join('')}</div><p class="ff-catalogue-note" role="status"></p><p class="ff-look-empty" hidden>No matching looks. Try another search or collection.</p><div class="ff-look-grid">${looks.map(look=>`<div class="ff-look-entry" data-entry="${look.id}"><button class="ff-look" type="button" data-look="${look.id}" aria-pressed="false"><span class="ff-look-image"><img alt="" hidden/><span class="ff-thumb-empty">Connect a video</span><span class="ff-look-check">${icon('check')}<span>Selected</span></span></span><span class="ff-look-name">${look.name}</span><span class="ff-look-note">${look.note}</span></button><button type="button" class="ff-favorite" data-favorite="${look.id}" aria-label="Favorite ${look.name}" aria-pressed="${favorites.has(look.id)}" title="Favorite ${look.name}">${favorites.has(look.id)?'★':'☆'}</button></div>`).join('')}</div><div class="ff-thumbnail-status"><p class="ff-thumbnail-note" role="status">First-frame previews</p>${button('retry-looks','Retry previews','','hidden')}</div></section>
          <section class="ff-customize-panel" hidden>
            <div class="ff-section"><div class="ff-section-heading"><h2>Film</h2><span>The foundation of your look</span></div><div class="ff-films">${films.map(([id,name,note])=>`<button type="button" data-film="${id}" aria-pressed="false"><span>${name}</span><small>${note}</small>${icon('check')}</button>`).join('')}</div>
              <h3>Film size</h3><div class="ff-chips">${formats.map(([id,name])=>`<button type="button" data-format="${id}" aria-pressed="false">${name}</button>`).join('')}</div><p class="ff-help">Changes the scale of grain and halation, not the crop.</p>
              <h3>Print / scan</h3><div class="ff-print">${[['screen','Digital reference'],['vision-2383','Kodak 2383'],['vision-2393','Kodak 2393']].map(([id,name])=>`<button type="button" data-medium="${id}" aria-pressed="false">${name}</button>`).join('')}</div>
              <label class="ff-reference">Screen conversion<select data-control="digitalReference"><option value="graded-print">Graded print</option><option value="reference-exposure">Reference exposure</option></select></label>
            </div>
            <details class="ff-section"><summary>Film exposure & print response</summary><div class="ff-light-sliders"></div></details>
          </section>
          <section class="ff-grade-panel" hidden>
            <p class="ff-intro">Shape the finished look.</p>
            <section class="ff-wheel-panel" aria-label="Color wheels">
              <div class="ff-section-heading"><h2>Color wheels</h2><span>Tint the dark, middle or bright areas.</span></div>
              <div class="ff-wheels ff-wheels-primary"></div>
              <p class="ff-help">Move toward a color to add it. Center is neutral.</p>
            </section>
            <div class="ff-grade-sliders ff-grade-quick"></div><div class="ff-texture-sliders ff-grade-quick"></div>
            <details class="ff-grade-more"><summary>More color controls</summary><div class="ff-grade-extra"></div><div class="ff-wheels ff-wheel-overall"></div></details>
            ${button('reset-grade','Reset color adjustments','','class="ff-reset-section" title="Reset finishing color. Keep film and texture."')}
            <div class="ff-legacy-balance" hidden><span>Saved input correction is active.</span>${button('reset-input','Clear correction','','title="Remove the before-film correction stored in this older recipe. Undo restores it."')}</div>
          </section>

        </div>
        <footer class="ff-sidebar-footer"><div class="ff-preview-settings"><label>Preview <select class="ff-quality" aria-label="Preview quality"><option value="640">640px · Fast</option><option value="960">960px · Balanced</option><option value="1280" selected>1280px · Detailed</option><option value="1920">1920px · Inspect</option></select></label>${button('undo','Undo','undo')}</div><div class="ff-export-row"><select class="ff-export-format" aria-label="Export format"><option value="mp4">MP4 · SDR</option><option value="prores422hq">ProRes 422 HQ · SDR</option><option value="hlg">HEVC · HDR HLG</option></select>${button('export','Export video')}</div><div class="ff-trial-row">${button('test-export','Test 5 seconds','','title="Export up to five seconds from the playhead, at full resolution and the selected format."')}${button('cancel-export','Cancel export','','hidden')}</div><a class="ff-download" hidden download>Download finished video ↗</a><p>Automatic previews use native Fotufilm and Gear grading.</p></footer>
      </aside>
    </div><div class="ff-toast" role="status" hidden></div><input class="ff-file-input" type="file" accept="video/mp4,video/webm,video/quicktime" hidden>`;
  const $ = s => root.querySelector(s);
  const $$ = s => [...root.querySelectorAll(s)];
  const video = $('.ff-main-video'), before = $('.ff-before-video'), stage = $('.ff-stage');
  const action = name => $(`[data-action="${name}"]`);
  video.loop = true; before.loop = true; video.muted = true; before.muted = true;
  action('loop').setAttribute('aria-pressed', 'true');
  let toastTimer;
  const toast = message => { $('.ff-toast').textContent = message; $('.ff-toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(()=>$('.ff-toast').hidden=true, 4200); };
  const filmLabel = () => filmName(recipe.stock);
  const changed = () => !sameRecipe(recipe, startingRecipe);
  function setStatus(text){previewStatus=text;$('.ff-render-state').textContent=text;}
  function showStill(value){$('.ff-after-still').hidden=!(value&&stillReady);$('.ff-before-still').hidden=!(value&&stillReady);}
  function moveWipe(event){
    const bounds=stage.getBoundingClientRect(),value=Math.max(0,Math.min(100,100*(event.clientX-bounds.left)/bounds.width));
    $('.ff-wipe input').value=value;stage.style.setProperty('--wipe',`${value}%`);$('.ff-before').style.clipPath=`inset(0 ${100-value}% 0 0)`;
  }
  function closeLive(){
    live?.close();live=null;liveFrame=-1;liveFrames=0;liveStatsStart=0;
    $('.ff-live-after').hidden=true;$('.ff-live-before').hidden=true;
  }
  function commitHistory(){
    clearTimeout(historyTimer);
    const previous=history.at(-1);
    if(previous.lookId!==selectedLook||!sameRecipe(previous.recipe,recipe)){
      history.push(snapshot());if(history.length>30)history.shift();
    }
    action('undo').disabled=history.length<2;
  }
  function bindNumeric(input, apply){
    numericControls.set(input,attachNumericControl(input,{on,commit:value=>{commitHistory();apply(value);commitHistory();}}));
  }
  const isGesture = target => target.matches('input[type="range"][data-grade],input[type="range"][data-section],.ff-wheel-master input,.ff-wheel');
  root.addEventListener('pointerdown',event=>{if(isGesture(event.target)){commitHistory();interacting=true;}},{signal:abort.signal,capture:true});
  function endGesture(){if(!interacting)return;interacting=false;editStarted=performance.now();commitHistory();schedulePreview(true);}
  for(const event of ['pointerup','pointercancel','blur'])window.addEventListener(event,endGesture,{signal:abort.signal,capture:true});
  const lookPreviews=createLookPreviews({
    cache:options.preview?.lookCache,
    render:(...args)=>options.preview.render(...args),
    async show(id,url,signal){
      const loaded=new Image();loaded.src=url;await loaded.decode();
      if(signal.aborted||destroyed)return;
      const image=$(`[data-look="${id}"] img`);image.src=url;image.hidden=false;image.nextElementSibling.hidden=true;syncCurrentLookPreview();
    },
    status(id,state){
      if(destroyed)return;
      if(id){const card=$(`[data-look="${id}"]`);card.dataset.previewState=state;card.setAttribute('aria-busy',String(state==='loading'));const placeholder=card.querySelector('.ff-thumb-empty');
        if(state==='loading'&&card.querySelector('img').hidden)placeholder.textContent='Rendering…';
        if(state==='error'){card.querySelector('img').hidden=true;placeholder.hidden=false;placeholder.textContent='Preview unavailable';}
      }else{
        if(state==='loading')$$('.ff-look:not(:disabled) .ff-look-image img').forEach(img=>{if(img.hidden)img.nextElementSibling.textContent='First-frame preview';});
        $('.ff-thumbnail-note').textContent=state==='loading'?'Rendering first-frame previews…':state==='error'?'Some previews could not load. Try again.':'First-frame previews · Fotufilm';action('retry-looks').hidden=state!=='error';
      }
    }
  });
  on($('.ff-keep-finish'),'change',()=>scheduleLookPreviews());
  function candidateLook(id){const next=selectLook(recipe,id,$('.ff-keep-finish').checked);if(recipe.sdr_output)next.sdr_output=recipe.sdr_output;return next;}
  function scheduleLookPreviews(force=false){
    if(!options.preview||!asset||destroyed||tab!=='looks'||interacting)return;
    const entries=filteredLooks();
    const items=previewLooks(entries,visibleLookIds,selectedLook,stockAvailable);
    lookPreviews.update(asset.asset,items.map(look=>({id:look.id,recipe:candidateLook(look.id)})),force,renderEngine);
  }
  function filteredLooks(){return filterLooks({group:lookGroup,query:lookQuery,favorites,favoritesOnly});}
  function refreshVisibleLooks(){
    clearTimeout(viewportTimer);
    // IntersectionObserver handles normal layouts. The geometry fallback also
    // works while an inline node is being resized or before its first observer tick.
    const panel=$('.ff-panel-content'),bounds=panel.getBoundingClientRect();
    visibleLookIds.clear();
    const entries=$$('.ff-look-entry').filter(card=>!card.hidden);
    for(const card of entries){const rect=card.getBoundingClientRect();if(rect.height>0&&rect.bottom>bounds.top&&rect.top<bounds.bottom)visibleLookIds.add(card.dataset.entry);}
    if(!bounds.height)entries.slice(0,6).forEach(card=>visibleLookIds.add(card.dataset.entry));
    scheduleLookPreviews();
  }
  function filterLookCards(){
    const visible=new Set(filteredLooks().map(look=>look.id));
    $$('.ff-look-entry').forEach(card=>{card.hidden=!visible.has(card.dataset.entry);card.querySelector('[data-look]').hidden=card.hidden;});
    $$('[data-look-group]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.lookGroup===lookGroup)));
    $('.ff-look-empty').hidden=visible.size>0;
    action('favorite-filter').setAttribute('aria-pressed',String(favoritesOnly));
    refreshVisibleLooks();
  }
  function updateCatalogueAvailability(){
    for(const button of $$('[data-film]')){button.disabled=!stockAvailable(button.dataset.film);button.title=button.disabled?(catalogueError||'Stock not available in this server runtime.'):'';}
    for(const button of $$('[data-look]')){
      const look=looks.find(look=>look.id===button.dataset.look);button.disabled=!stockAvailable(look.film);
      button.title=button.disabled?(catalogueError||'Required stock not available in this server runtime.'):look.note;
      if(button.disabled){const image=button.querySelector('img'),placeholder=button.querySelector('.ff-thumb-empty');image.hidden=true;placeholder.hidden=false;placeholder.textContent=catalogueReady?'Stock unavailable':'Checking stocks…';}
    }
    const missing=films.filter(([id])=>!stockAvailable(id)).length;
    $('.ff-catalogue-note').textContent=catalogueError||(!catalogueReady?'Checking server stocks…':missing?`${missing} stocks unavailable. Update the server's Fotufilm pack to enable them.`:'');
    $('.ff-catalogue-note').hidden=!$('.ff-catalogue-note').textContent;
    filterLookCards();
  }
  on($('.ff-look-search'),'input',event=>{lookQuery=event.target.value;filterLookCards();});
  on($('.ff-panel-content'),'scroll',()=>{clearTimeout(viewportTimer);viewportTimer=setTimeout(refreshVisibleLooks,90);});
  if(typeof IntersectionObserver!=='undefined'){
    lookObserver=new IntersectionObserver(()=>refreshVisibleLooks(),{root:$('.ff-panel-content')});
    $$('.ff-look-entry').forEach(card=>lookObserver.observe(card));
  }
  if(options.preview?.catalogue){
    options.preview.catalogue().then(value=>{
      if(destroyed)return;
      if(!Array.isArray(value.stocks))throw new Error('Invalid stock catalogue.');
      availableStocks=new Set(value.stocks);renderEngine=value.engine||'';catalogueReady=true;updateCatalogueAvailability();
    }).catch(()=>{if(destroyed)return;catalogueReady=true;availableStocks=new Set();catalogueError='Could not check server stocks. Reopen the editor after updating the node pack.';updateCatalogueAvailability();});
  }
  function updateLive(){
    if(!asset||destroyed)return;
    try{
      if(!live){setStatus('Connecting film preview…');live=options.preview.live({
        onStatus:status=>{if(status.phase==='preparing')setStatus('Preparing film engine…');else if(status.phase==='queued')setStatus('Updating preview…');},
        onFrame:(frame,meta)=>{
          if(destroyed)return;
          const draw=(selector,x)=>{const canvas=$(selector);if(canvas.width!==meta.width)canvas.width=meta.width;if(canvas.height!==meta.height)canvas.height=meta.height;canvas.getContext('2d',{alpha:false}).drawImage(frame,x,0,meta.width,meta.height,0,0,meta.width,meta.height);canvas.hidden=false;};
          draw('.ff-live-after',0);if(meta.compare)draw('.ff-live-before',meta.width);else $('.ff-live-before').hidden=true;
          liveFrame=meta.frame;stillReady=true;showStill(false);action('compare').disabled=false;
          $('.ff-stage-left').textContent=view.comparison==='film'?'Film before color grade':'Connected source';$('.ff-stage-right').textContent={finish:'Finished result',film:'Film before color grade',source:'Connected source'}[view.stage];
          $('.ff-display').textContent=`${asset.info.colorSpace||'Linear source'} → SDR monitor · ${view.exposure===0&&view.mode==='output'&&view.stage==='finish'?'SDR output view':'Inspection view; export unchanged'}`;
          const now=performance.now();if(!liveStatsStart)liveStatsStart=now;liveFrames++;
          if(now-liveStatsStart>1000){deliveredFPS=(liveFrames-1)*1000/(now-liveStatsStart);liveStatsStart=now;liveFrames=1;}
          setStatus(`${meta.width} × ${meta.height} · ${video.paused?(meta.encoder==='png'?'Up to date':'Adjusting'):`${deliveredFPS.toFixed(1)} fps`} · ${meta.interaction?`${Math.round(meta.interaction.editToDraw)} ms response`:`${Math.round(meta.ms.total)} ms processing`}`);
          $('.ff-render-state').title=`${meta.interaction?`Edit to canvas draw ${Math.round(meta.interaction.editToDraw)} ms (browser clock). `:''}Queue ${meta.ms.queue??'?'} ms; worker setup ${meta.ms.setup??'?'} ms; ${meta.encoder} SDR monitor stream. ${meta.memoryInput?'Direct float memory':'Legacy file input'}. Source ${meta.ms.source} ms; film ${meta.ms.film} ms; grade ${meta.ms.grade} ms; display ${meta.ms.display} ms; encode ${meta.ms.encode} ms. Exports use the original float frames.`;
          if(!video.paused&&Math.abs(video.currentTime-meta.frame/fps)>.15)video.currentTime=meta.frame/fps;
          updateTransport();
        },
        onError:error=>{setStatus(`Live preview: ${error.message}`);video.pause();},
        onEnded:()=>{video.pause();updateTransport();},
      });}
      live.update({editedAt:editStarted||performance.now(),interacting,asset:asset.asset,recipe:clone(recipe),view:{...view},edge:previewEdge,
        frame:Math.min(asset.info.frames-1,Math.max(0,liveFrame>=0?liveFrame:Math.round(video.currentTime*fps))),
        playing:!video.paused,compare:comparing,loop:video.loop,rate});
    }catch(error){setStatus(error.message);}
  }
  function schedulePreview(force=false){
    if(!options.preview||!asset||destroyed)return;
    editStarted=performance.now();
    if(options.preview.live){
      scheduleLookPreviews();
      clearTimeout(previewTimer);previewTimer=setTimeout(updateLive,0);return;
    }
    const key=JSON.stringify([asset.asset,recipe,previewEdge,view]);
    if(!force&&key===previewKey)return;
    if(key!==previewKey){clipController?.abort();}
    previewKey=key;if(force&&Math.abs(video.currentTime*fps-stillFrame)>=1){stillReady=false;showStill(false);}clearTimeout(previewTimer);previewController?.abort();previewController=new AbortController();
    const controller=previewController,snapshot=clone(recipe),currentAsset=asset;
    setStatus('Updating film preview…');
    previewTimer=setTimeout(async()=>{
      try{
        const frame=Math.min(currentAsset.info.frames-1,Math.max(0,Math.round(video.currentTime*fps)));
        const still=await options.preview.render(currentAsset.asset,snapshot,{frame,edge:previewEdge,view:{...view},signal:controller.signal});
        if(destroyed||controller.signal.aborted)return;
        const afterImage=$('.ff-after-still'),beforeImage=$('.ff-before-still');
        afterImage.src=still.after;beforeImage.src=still.before;
        await Promise.all([afterImage.decode(),beforeImage.decode()]);
        if(destroyed||controller.signal.aborted)return;
        stillReady=true;stillFrame=frame;showStill(video.paused&&Math.abs(video.currentTime*fps-frame)<1);renderedRecipe=snapshot;
        action('compare').disabled=false;$('.ff-stage-left').textContent=view.comparison==='film'?'Film before color grade':'Connected source';$('.ff-stage-right').textContent={finish:'Finished result',film:'Film before color grade',source:'Connected source'}[view.stage];
        $('.ff-display').textContent=currentAsset.info.hdr?'HDR master → SDR display preview':'SDR source → film preview';
        setStatus(`Frame ready · ${still.seconds}s${still.cached?' · cached':still.filmCacheHits?' · film reused':''}`);
        scheduleLookPreviews();
      }catch(error){if(error.name!=='AbortError')setStatus(`Preview: ${error.message}`);}
    },100);
  }
  async function exportVideo(trial=false){
    if(!asset||!options.preview||exporting){toast('Connect an available source first.');return;}
    $('.ff-download').hidden=true;const target=action(trial?'test-export':'export');exporting=true;action('export').disabled=true;action('test-export').disabled=true;action('cancel-export').hidden=false;const snapshot=clone(recipe);
    exportController=new AbortController();const controller=exportController;
    const start=trial?Math.min(asset.info.frames-1,Math.max(0,liveFrame>=0?liveFrame:Math.round(video.currentTime*fps))):0;
    try{
      options.onSave?.(snapshot,selectedLook,clone(gradeChanges));
      const result=await options.preview.render(asset.asset,snapshot,{mode:'export',format:$('.ff-export-format').value,signal:controller.signal,start,range:trial?'trial':'full',channel:'export',onProgress:state=>target.textContent=`Export ${Math.round(state.progress*100)}%`});
      if(destroyed||controller.signal.aborted)return;
      const link=$('.ff-download');link.href=result.after;link.hidden=false;link.textContent='Download finished video ↗';toast(trial?'Full-resolution test clip ready.':'Full-resolution export ready.');
    }catch(error){if(error.name!=='AbortError')toast(error.message);}
    finally{exporting=false;exportController=null;action('export').disabled=!asset;action('test-export').disabled=!asset;action('cancel-export').hidden=true;target.textContent=trial?'Test 5 seconds':'Export video';}
  }
  for(const [selector,key] of [['.ff-view-mode','mode'],['.ff-view-stage','stage'],['.ff-view-ev','exposure']])on($(selector),'change',event=>{view[key]=key==='exposure'?Math.max(-10,Math.min(10,Number(event.target.value)||0)):event.target.value;schedulePreview(true);});
  on($('.ff-quality'),'change',event=>{previewEdge=Number(event.target.value);schedulePreview(true);});
  const gradeSliders=[['exposure','Exposure',-5,5,.05,' EV'],['temperature','Warmth',-1,1,.01,''],['tint','Tint',-1,1,.01,''],['contrast','Contrast',.25,2,.01,''],['highlights','Highlights',-2,2,.02,''],['shadows','Shadows',-2,2,.02,''],['saturation','Saturation',0,2,.01,''],['vibrance','Vibrance',-1,1,.01,'']];
  const gradeHints={exposure:'Make the image brighter or darker.',temperature:'Shift toward cooler blue or warmer amber.',tint:'Shift between green and magenta.',contrast:'Adjust the separation between dark and bright areas.',highlights:'Adjust bright areas.',shadows:'Adjust dark areas.',saturation:'Adjust overall color intensity.',vibrance:'Adjust color intensity while protecting already saturated colors.'};
  for(const stage of ['finish'])for(const [key,name,min,max,step,unit] of gradeSliders){
    const wrap=document.createElement('div');wrap.className='ff-grade-control';
    const prefix=stage==='balance'?'Input ':'';
    wrap.innerHTML=`<div class="ff-slider"><span>${name}<output></output></span><input type="range" data-grade="${key}" data-grade-stage="${stage}" data-digits="2" data-unit="${unit}" min="${min}" max="${max}" step="${step}" aria-label="${prefix}Grade ${name}" title="${gradeHints[key]}"></div>${iconButton('reset-control',`Reset ${prefix.toLowerCase()}${name.toLowerCase()}`,'undo')}`;
    $(['highlights','shadows','vibrance'].includes(key)?'.ff-grade-extra':'.ff-grade-quick').append(wrap);
    const input=wrap.querySelector('input'),reset=wrap.querySelector('button');
    reset.dataset.gradeReset=key;reset.dataset.gradeStage=stage;
    const apply=value=>{recipe.grading[stage][key]=value;updateRecipeUI();};
    bindNumeric(input,apply);on(input,'input',event=>apply(Number(event.target.value)));
    on(reset,'click',()=>{delete gradeChanges[key];recipe.grading[stage][key]=clone(gradeDefault()[key]);updateRecipeUI();});
  }
  const wheelNames=[['lift','Shadows'],['gamma','Midtones'],['gain','Highlights'],['offset','Overall']];
  for(const stage of ['finish'])for(const [key,name] of wheelNames){
    const wrap=document.createElement('div');wrap.className='ff-wheel-wrap';wrap.dataset.wheel=key;wrap.dataset.gradeStage=stage;
    const prefix=stage==='balance'?'Input ':'';
    wrap.innerHTML=`<span class="ff-wheel-name">${name}</span><div class="ff-wheel" role="slider" tabindex="0" aria-label="${prefix}${name} color wheel" aria-valuemin="-1" aria-valuemax="1" title="Click or drag to tint. Arrow keys fine-tune; Home centers the tint."><i></i></div><span class="ff-wheel-state"></span><label class="ff-wheel-master">Brightness <output></output><input type="range" aria-label="${prefix}${name} brightness" min="${['gamma','gain'].includes(key)?.1:-.3}" max="${['gamma','gain'].includes(key)?2:.3}" step=".005"></label>${button('reset-wheel','Reset','','aria-label="Reset '+prefix.toLowerCase()+name.toLowerCase()+' wheel"')}`;
    $(key==='offset'?'.ff-wheel-overall':'.ff-wheels-primary').append(wrap);const wheel=wrap.querySelector('.ff-wheel'),master=wrap.querySelector('input'),reset=wrap.querySelector('button');
    const fromPoint=(x,y)=>{const length=Math.hypot(x,y);if(length>1){x/=length;y/=length;}const rgb=[x,-.5*x-.866*y,-.5*x+.866*y],vector=recipe.grading[stage][key],mean=vector.reduce((a,b)=>a+b)/3,amount=['gamma','gain'].includes(key)?.35:.12;recipe.grading[stage][key]=rgb.map(v=>Math.max(key==='gamma'?.1:key==='gain'?0:-1,Math.min(key==='gamma'||key==='gain'?4:1,mean+v*amount)));updateRecipeUI();};
    const move=event=>{const box=wheel.getBoundingClientRect();fromPoint((event.clientX-box.left)/box.width*2-1,(event.clientY-box.top)/box.height*2-1);};
    on(wheel,'pointerdown',event=>{event.preventDefault();event.stopPropagation();wheel.setPointerCapture(event.pointerId);move(event);});
    on(wheel,'pointermove',event=>{if(wheel.hasPointerCapture(event.pointerId)){event.stopPropagation();move(event);}});
    on(wheel,'pointerup',event=>{if(wheel.hasPointerCapture(event.pointerId))wheel.releasePointerCapture(event.pointerId);});
    on(wheel,'keydown',event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key))return;event.preventDefault();event.stopPropagation();const dot=wheel.querySelector('i'),x=Number(dot.dataset.x||0),y=Number(dot.dataset.y||0);fromPoint(event.key==='Home'?0:x+(event.key==='ArrowLeft'?-.05:event.key==='ArrowRight'?.05:0),event.key==='Home'?0:y+(event.key==='ArrowUp'?-.05:event.key==='ArrowDown'?.05:0));});
    on(wheel,'dblclick',()=>fromPoint(0,0));
    on(master,'input',()=>{const vector=recipe.grading[stage][key],mean=vector.reduce((a,b)=>a+b)/3;recipe.grading[stage][key]=vector.map(v=>Math.max(key==='gamma'?.1:key==='gain'?0:-1,Math.min(['gamma','gain'].includes(key)?4:1,v-mean+Number(master.value))));updateRecipeUI();});
    on(reset,'click',()=>{delete gradeChanges[key];recipe.grading[stage][key]=clone(gradeDefault()[key]);updateRecipeUI();});
  }
  function updateWheels(){
    for(const wrap of $$('[data-wheel]')){const key=wrap.dataset.wheel,vector=recipe.grading[wrap.dataset.gradeStage][key],mean=vector.reduce((a,b)=>a+b)/3,amount=['gamma','gain'].includes(key)?.35:.12,x=(vector[0]-mean)/amount,y=(vector[2]-vector[1])/(1.732*amount),dot=wrap.querySelector('i'),radius=Math.hypot(x,y),scale=radius>1?1/radius:1;
      dot.dataset.x=x;dot.dataset.y=y;dot.style.left=`${50+x*scale*46}%`;dot.style.top=`${50+y*scale*46}%`;
      wrap.querySelector('input').value=mean;wrap.querySelector('output').textContent=mean.toFixed(2);wrap.querySelector('.ff-wheel-state').textContent=radius<.005?'Neutral tint':'Tinted';
      const wheel=wrap.querySelector('[role=slider]');wheel.setAttribute('aria-valuenow',String(Math.max(-1,Math.min(1,x))));wheel.setAttribute('aria-valuetext',`Red ${vector[0].toFixed(3)}, green ${vector[1].toFixed(3)}, blue ${vector[2].toFixed(3)}. Arrow keys adjust tint; Home centers.`);
      wrap.querySelector('button').disabled=vector.every((v,i)=>Math.abs(v-gradeDefault()[key][i])<1e-6);
    }
  }
  function syncCurrentLookPreview(){
    const thumbnail=$(`[data-look="${selectedLook}"] img`),image=$('.ff-current-preview img');
    const ready=Boolean(thumbnail&&!thumbnail.hidden&&thumbnail.getAttribute('src'));
    image.hidden=!ready;image.nextElementSibling.toggleAttribute('hidden',ready);
    if(ready)image.src=thumbnail.src;else image.removeAttribute('src');
  }
  function updateRecipeUI() {
    if(editorMode==='grade'){
      for(const [key,value] of Object.entries(recipe.grading.finish)){
        if(JSON.stringify(value)===JSON.stringify(previousGrade[key]))continue;
        if(JSON.stringify(value)===JSON.stringify(baseGradeRecipe.grading.finish[key]))delete gradeChanges[key];
        else gradeChanges[key]=clone(value);
      }
      previousGrade=clone(recipe.grading.finish);
    }
    options.onChange?.(clone(recipe),clone(gradeChanges));
    const look = editorMode==='grade'?matchLook(baseGradeRecipe):looks.find(x=>x.id === selectedLook);
    $('.ff-look-title h1').textContent = look?.name || (editorMode==='grade'?'Color Grade':'Custom recipe');
    $('.ff-modified').hidden = !look || sameRecipe(recipe, selectLook(recipe,look.id));
    $('.ff-recipe-summary').textContent = `${filmLabel()} · ${formats.find(x=>x[0]===recipe.format)?.[1] || recipe.format} · ${recipe.medium === 'screen' ? 'Digital' : recipe.medium.replace('vision-', '')}`;
    $$('.ff-look').forEach(el=>el.setAttribute('aria-pressed', String(el.dataset.look === selectedLook)));
    syncCurrentLookPreview();
    for (const [attribute, value] of [['film',recipe.stock],['format',recipe.format],['medium',recipe.medium]]) {
      $$(`[data-${attribute}]`).forEach(el=>el.setAttribute('aria-pressed',String(el.dataset[attribute] === value)));
    }
    $$('input[data-section]').forEach(input=> {input.value=recipe[input.dataset.section][input.dataset.key]; updateSlider(input);});
    $('[data-control="digitalReference"]').value = recipe.digitalReference;
    $('.ff-render-state').textContent = previewStatus || (renderedRecipe ? (sameRecipe(recipe,renderedRecipe)?'Rendered recipe · up to date':'Recipe changed · run workflow to update') : options.onRender ? 'Save your recipe, then run the workflow' : changed() ? 'Recipe edited · demo render unchanged' : rendered ? 'Existing render · interface preview' : 'Source playback');
    action('reset').disabled = !selectedLook || sameRecipe(recipe, selectLook(recipe,selectedLook));
    root.querySelectorAll('[data-grade]').forEach(input=>{input.value=recipe.grading[input.dataset.gradeStage][input.dataset.grade];updateSlider(input);});
    root.querySelectorAll('[data-grade-reset]').forEach(el=>el.disabled=recipe.grading[el.dataset.gradeStage][el.dataset.gradeReset]===gradeDefault()[el.dataset.gradeReset]);
    const inputEdited=JSON.stringify(recipe.grading.balance)!==JSON.stringify(neutralGrade());$('.ff-legacy-balance').hidden=!inputEdited;
    action('undo').disabled=history.length<2&&sameRecipe(recipe,history.at(-1).recipe)&&selectedLook===history.at(-1).lookId;
    clearTimeout(historyTimer);if(!interacting)historyTimer=setTimeout(commitHistory,250);
    editStarted=performance.now();updateWheels();schedulePreview();
  }
  function updateSlider(input) {
    const value = Number(input.value), digits = Number(input.dataset.digits || 0);
    numericControls.get(input)?.sync();
    input.style.setProperty('--fill',`${100*(value-Number(input.min))/(Number(input.max)-Number(input.min))}%`);
  }
  const sliders = [
    ['light','params','ev','Exposure',-3,3,.05,2,' EV'],['light','params','temperature','Temperature',2000,12000,50,0,' K'],
    ['light','params','tint','Tint',-100,100,1,0,''],['light','params','highlights','Highlights',-1,1,.01,2,''],
    ['light','params','shadows','Shadows',-1,1,.01,2,''],['light','params','saturation','Saturation',0,2,.01,2,''],
    ['light','params','vibrance','Vibrance',-1,1,.01,2,''],['light','profile','screenGrade','Print contrast',0,5,.05,2,''],
    ['texture','params','grain','Grain',0,2,.01,2,''],['texture','profile','halation','Halation',-6,6,.1,1,''],
  ];
  for (const [group, section, key, text, min, max, step, digits, unit] of sliders) {
    const label = document.createElement('div'); label.className='ff-slider';
    label.innerHTML = `<span>${text}<output></output></span><input type="range" data-section="${section}" data-key="${key}" data-digits="${digits}" data-unit="${unit}" min="${min}" max="${max}" step="${step}" aria-label="${text}">`;
    $(`.ff-${group}-sliders`).append(label);
    const input=label.querySelector('input');
    const apply=value=>{recipe[section][key]=value;updateRecipeUI();};
    bindNumeric(input,apply);on(input,'input',()=>apply(Number(input.value)));
  }
  on($('[data-control="digitalReference"]'),'change',event=>{recipe.digitalReference=event.target.value;updateRecipeUI();});
  function setTab(next) {
    tab=next; $('.ff-looks-panel').hidden=tab!=='looks'; $('.ff-customize-panel').hidden=tab!=='customize'; $('.ff-grade-panel').hidden=tab!=='grade';
    action('tab-looks').setAttribute('aria-pressed',String(tab==='looks'));action('tab-customize').setAttribute('aria-pressed',String(tab==='customize'));action('tab-grade').setAttribute('aria-pressed',String(tab==='grade'));
    $('.ff-panel-content').scrollTop=0;
    if(tab==='looks')refreshVisibleLooks();else lookPreviews.cancel();
  }
  function setZoom(value) {
    zoom=Math.min(4,Math.max(1,value)); if(zoom===1)pan={x:0,y:0};
    $('.ff-zoom').textContent=`${Math.round(zoom*100)}%`; action('fit').setAttribute('aria-pressed',String(zoom===1));
    action('minus').disabled=zoom===1; action('plus').disabled=zoom===4;
    for (const surface of [video,before,$('.ff-after-still'),$('.ff-before-still'),$('.ff-live-after'),$('.ff-live-before')]) surface.style.transform=`translate(${pan.x}px,${pan.y}px) scale(${zoom})`;
    stage.style.cursor=zoom>1?'grab':'';
  }
  function updateTransport() {
    const duration=Number.isFinite(video.duration)?video.duration:0;
    const visibleTime=live&&liveFrame>=0?liveFrame/fps:video.currentTime;
    $('.ff-time').innerHTML=`${timecode(visibleTime,fps)} <span>/ ${timecode(duration,fps)}</span>`;
    $('.ff-scrubber').max=String(duration||1);$('.ff-scrubber').value=String(visibleTime);
    $('.ff-timeline').style.setProperty('--progress',`${duration?100*visibleTime/duration:0}%`);
    const playState = video.paused ? 'play' : 'pause';
    if(action('play').dataset.state !== playState) {
      action('play').dataset.state=playState;
      action('play').innerHTML=icon(playState);
      action('play').setAttribute('aria-label',video.paused?'Play (Space)':'Pause (Space)');
      action('play').title=video.paused?'Play (Space)':'Pause (Space)';
      action('play').setAttribute('aria-pressed',String(!video.paused));
    }
    if(comparing && before.readyState>=2 && Math.abs(before.currentTime-video.currentTime)>.08)before.currentTime=video.currentTime;
  }
  function tick() {
    if(destroyed)return; updateTransport();
    if(!video.paused) {
      if(video.requestVideoFrameCallback)frameCallback=video.requestVideoFrameCallback(tick);
      else raf=requestAnimationFrame(tick);
    }
  }
  function stopTick() { if(frameCallback && video.cancelVideoFrameCallback)video.cancelVideoFrameCallback(frameCallback);cancelAnimationFrame(raf); }
  async function play() {
    if(!video.src||action('play').disabled)return;
    if(video.paused){try{await video.play();if(comparing){before.currentTime=video.currentTime;await before.play();}}catch{toast('This clip could not play. Try an H.264 MP4 preview.');}}
    else {video.pause();before.pause();}
  }
  function seek(time) {liveFrame=-1;const duration=Number.isFinite(video.duration)?video.duration:0; video.currentTime=Math.min(duration,Math.max(0,time));if(before.readyState>=1)before.currentTime=video.currentTime;updateTransport();if(options.preview?.live)schedulePreview(true);}
  function compare(value) {
    comparing=Boolean(value&&(live||stillReady||(rendered&&activeRenderedSource===sourceMode)));
    $('.ff-before').hidden=!comparing;$('.ff-stage-left').hidden=!comparing;$('.ff-wipe').hidden=!comparing;
    action('compare').setAttribute('aria-pressed',String(comparing));
    if(comparing){before.currentTime=video.currentTime;if(!video.paused)before.play().catch(()=>toast('The reference clip could not play.'));}else before.pause();
    if(live)schedulePreview(true);
  }
  on($('.ff-wipe input'),'input',event=>{stage.style.setProperty('--wipe',`${event.target.value}%`);$('.ff-before').style.clipPath=`inset(0 ${100-Number(event.target.value)}% 0 0)`;});
  function setSource(mode, preserve=true) {
    if(mode!==sourceMode){closeLive();}
    const time=preserve?video.currentTime:0, wasPlaying=!video.paused;
    video.pause(); before.pause(); sourceMode=mode; compare(false);
    const current=sources[mode]||(mode==='hdr'&&hasHDR?sources.original:'');
    const after=mode===activeRenderedSource?rendered:'';
    const pendingHDR=mode==='hdr'&&!after&&!options.preview?.live;video.style.visibility=pendingHDR?'hidden':'';
    $('.ff-empty').hidden=Boolean(current||asset);$('.ff-video-error').hidden=true;
    $('.ff-file-name').textContent=label;$('.ff-file-name').title=label;
    if(current){video.src=after||current;before.src=current;video.load();before.load();}
    else {video.removeAttribute('src');before.removeAttribute('src');video.load();before.load();}
    action('source-original').setAttribute('aria-pressed',String(mode==='original'));action('source-hdr').setAttribute('aria-pressed',String(mode==='hdr'));
    action('source-hdr').disabled=!hasHDR&&!sources.hdr;action('compare').disabled=!after;
    $('.ff-stage-right').textContent=after?'Existing Fotufilm render':mode==='hdr'?'Preparing linear preview…':'Original source';
    $('.ff-display').textContent=mode==='hdr'?'Linear source · SDR display preview':'SDR video preview';
    const restore=()=>{if(!destroyed){seek(time);if(wasPlaying&&!pendingHDR)video.play().catch(()=>{});}video.removeEventListener('loadedmetadata',restore);};
    video.addEventListener('loadedmetadata',restore,{once:true,signal:abort.signal});
    updateRecipeUI();updateTransport();
    for(const name of ['play','back','next','loop','audio','fullscreen'])action(name).disabled=!current||pendingHDR;
    $('.ff-scrubber').disabled=!current;
    if(current&&!pendingHDR)makeThumbnails(current);
    if(asset&&Boolean(asset.info.hdr)!==(mode==='hdr')){asset=null;previewController?.abort();clipController?.abort();lookPreviews.cancel();clearTimeout(previewTimer);stillReady=false;showStill(false);}
    action('export').disabled=!asset||exporting;action('test-export').disabled=!asset||exporting;schedulePreview();
  }
  async function makeThumbnails(url) {
    const token=++thumbnailToken;
    const probe=document.createElement('video'); probe.muted=true;probe.preload='auto';probe.src=url;probe.crossOrigin='anonymous';
    const once=event=>new Promise((resolve,reject)=>{
      const timeout=setTimeout(()=>{cleanup();reject(new Error('Thumbnail timed out'));},12000);
      const done=()=>{cleanup();resolve();},fail=()=>{cleanup();reject(new Error('Thumbnail unavailable'));};
      const cleanup=()=>{clearTimeout(timeout);probe.removeEventListener(event,done);probe.removeEventListener('error',fail);};
      probe.addEventListener(event,done,{once:true});probe.addEventListener('error',fail,{once:true});
    });
    try {
      await once('loadeddata');
      const canvas=document.createElement('canvas');canvas.width=280;canvas.height=Math.round(280*probe.videoHeight/probe.videoWidth);
      const ctx=canvas.getContext('2d');
      for(let i=0;i<12;i++){
        if(destroyed||token!==thumbnailToken)break;
        const time=i*Math.max(0,probe.duration-.08)/11;
        if(Math.abs(probe.currentTime-time)>.001){const done=once('seeked');probe.currentTime=time;await done;}
        ctx.drawImage(probe,0,0,canvas.width,canvas.height);const thumbnail=canvas.toDataURL('image/jpeg',.78);
        if(destroyed||token!==thumbnailToken)break;
        $$('.ff-filmstrip span')[i].style.backgroundImage=`url("${thumbnail}")`;
        if(i===0&&!options.preview)$$('.ff-look-image img').forEach(img=>{img.src=thumbnail;img.hidden=false;img.nextElementSibling.hidden=true;});
      }
    }catch{/* Thumbnails are optional; playback remains available. */}
    finally{probe.removeAttribute('src');probe.load();}
  }
  on(video,'loadedmetadata',()=>{
    $('.ff-file-info').textContent=`${video.videoWidth} × ${video.videoHeight} / ${fps} fps`;
    $$('.ff-ticks span').forEach((el,i)=>el.textContent=timecode(video.duration*i/5,fps).slice(0,5));updateTransport();
  });
  on(video,'play',()=>{showStill(false);stopTick();tick();if(options.preview?.live)schedulePreview(true);});on(video,'pause',()=>{stopTick();before.pause();updateTransport();if(!swappingMedia){showStill(stillReady&&Math.abs(video.currentTime*fps-stillFrame)<1);schedulePreview(true);}});
  on(video,'seeked',()=>{updateTransport();if(video.paused&&!swappingMedia&&!options.preview?.live)schedulePreview(true);});on(video,'timeupdate',updateTransport);
  on(video,'error',()=>{$('.ff-video-error').hidden=false;$('.ff-video-error').textContent='This browser cannot play the clip. Use an H.264 MP4 preview or choose another video.';});
  on($('.ff-scrubber'),'input',event=>seek(Number(event.target.value)));
  on($('.ff-rate select'),'change',event=>{rate=Number(event.target.value);video.playbackRate=rate;before.playbackRate=rate;if(live)schedulePreview(true);});
  on($('.ff-file-input'),'change',async event=>{
    const file=event.target.files[0];if(!file)return;asset=null;hasHDR=false;previewController?.abort();clipController?.abort();lookPreviews.cancel();stillReady=false;showStill(false);const url=URL.createObjectURL(file);ownedURLs.push(url);sources={original:url,hdr:''};rendered='';label=file.name;setSource('original',false);if(options.onUpload){try{await options.onUpload(file);}catch(error){toast(error.message);}}else toast('Local playback only. Connect this clip to the workflow to finish it.');
  });
  on(root,'click',async event=>{
    const target=event.target.closest('button');if(!target||target.disabled)return;
    if(target.dataset.lookGroup){
      lookGroup=target.dataset.lookGroup;
      filterLookCards();return;
    }
    if(target.dataset.favorite){
      const id=target.dataset.favorite;if(favorites.has(id))favorites.delete(id);else favorites.add(id);
      writeFavorites(favoriteStorage,favorites);target.setAttribute('aria-pressed',String(favorites.has(id)));target.textContent=favorites.has(id)?'★':'☆';filterLookCards();return;
    }
    if(target.dataset.look){commitHistory();selectedLook=target.dataset.look;recipe=candidateLook(selectedLook);updateRecipeUI();commitHistory();return;}
    if(target.dataset.film){recipe.stock=target.dataset.film;updateRecipeUI();return;}
    if(target.dataset.format){recipe.format=target.dataset.format;updateRecipeUI();return;}
    if(target.dataset.medium){recipe.medium=target.dataset.medium;updateRecipeUI();return;}
    switch(target.dataset.action){
      case 'favorite-filter':favoritesOnly=!favoritesOnly;filterLookCards();break;
      case 'play':await play();break;
      case 'back':video.pause();seek(video.currentTime-1/fps);break;
      case 'next':video.pause();seek(video.currentTime+1/fps);break;
      case 'loop':video.loop=!video.loop;before.loop=video.loop;target.setAttribute('aria-pressed',String(video.loop));if(live)schedulePreview(true);break;
      case 'audio':video.muted=!video.muted;target.innerHTML=icon(video.muted?'mute':'audio');target.setAttribute('aria-label',video.muted?'Unmute audio':'Mute audio');target.title=video.muted?'Unmute audio':'Mute audio';break;
      case 'compare':compare(!comparing);break;
      case 'source-original':setSource('original');options.onSourceMode?.('original');break;
      case 'source-hdr':setSource('hdr');options.onSourceMode?.('hdr');break;
      case 'fit':setZoom(1);break;
      case 'minus':setZoom(zoom-.25);break;
      case 'plus':setZoom(zoom+.25);break;
      case 'fullscreen':try{if(document.fullscreenElement)await document.exitFullscreen();else await $('.ff-main').requestFullscreen();}catch{toast('Fullscreen is unavailable in this browser.');}break;
      case 'tab-looks':setTab('looks');break;
      case 'tab-customize':setTab('customize');break;
      case 'tab-grade':setTab('grade');break;
      case 'reset-grade':gradeChanges={};recipe.grading.finish=clone(gradeDefault());updateRecipeUI();break;
      case 'reset-input':recipe.grading.balance=neutralGrade();updateRecipeUI();break;
      case 'undo':commitHistory();if(history.length>1){history.pop();const previous=history.at(-1);recipe=clone(previous.recipe);selectedLook=previous.lookId;previewKey='';updateRecipeUI();}break;
      case 'export':await exportVideo();break;
      case 'test-export':await exportVideo(true);break;
      case 'cancel-export':exportController?.abort();break;
      case 'retry-looks':scheduleLookPreviews(true);break;
      case 'reset':if(selectedLook){commitHistory();{const output=recipe.sdr_output;recipe=selectLook(recipe,selectedLook);if(output)recipe.sdr_output=output;}updateRecipeUI();commitHistory();}break;
      case 'open-file':$('.ff-file-input').click();break;
      case 'cancel':recipe=clone(startingRecipe);selectedLook=startingLook;updateRecipeUI();if(options.onClose)options.onClose();else toast('Unsaved recipe changes discarded.');break;
      case 'save':options.onSave?.(clone(recipe),selectedLook,clone(gradeChanges));startingRecipe=clone(recipe);startingLook=selectedLook;updateRecipeUI();if(!options.onSave)toast('Recipe saved for this preview session.');break;
    }
  });
  on(stage,'pointerdown',event=>{if(comparing){moveWipe(event);stage.setPointerCapture(event.pointerId);lastPointer={wipe:true};event.preventDefault();return;}if(zoom===1||event.target.closest('.ff-wipe'))return;lastPointer={x:event.clientX,y:event.clientY,pan:{...pan}};stage.setPointerCapture(event.pointerId);});
  on(stage,'pointermove',event=>{if(!lastPointer)return;if(lastPointer.wipe){moveWipe(event);return;}const maxX=stage.clientWidth*(zoom-1)/2,maxY=stage.clientHeight*(zoom-1)/2;pan={x:Math.max(-maxX,Math.min(maxX,lastPointer.pan.x+event.clientX-lastPointer.x)),y:Math.max(-maxY,Math.min(maxY,lastPointer.pan.y+event.clientY-lastPointer.y))};setZoom(zoom);});
  on(stage,'pointerup',()=>lastPointer=null);on(stage,'pointercancel',()=>lastPointer=null);
  on(root,'keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();options.onClose?.();return;}
    if(event.target.matches('input,select,textarea,button'))return;
    if(event.code==='Space'){event.preventDefault();play();}
    else if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();video.pause();seek(video.currentTime+(event.key==='ArrowRight'?1:-1)/fps);}
    else if(event.key.toLowerCase()==='l')action('loop').click();
  });
  if(editorMode!=='studio'){
    $('.ff-source-switch').hidden=true;
    $('.ff-export-row').hidden=true;$('.ff-trial-row').hidden=true;
  }
  if(editorMode==='film'){
    action('tab-grade').hidden=true;
    $('.ff-customize-panel').append($('.ff-texture-sliders'));
    $('.ff-keep-color').hidden=true;
    $('.ff-intro').textContent='Choose a complete look. Fine-tune its colors in the connected Color Grade node.';
    $('.ff-export-row').hidden=true;$('.ff-trial-row').hidden=true;
  }
  if(editorMode==='grade'){
    action('tab-looks').hidden=true;action('tab-customize').hidden=true;
    action('tab-grade').querySelector('span').textContent='Color';
    $('.ff-texture-sliders').hidden=true;$('.ff-grade-panel .ff-intro').textContent='Adjust the connected look. Reset returns to its default colors.';
    $('.ff-current-label').textContent='Grading this look';$('.ff-current-preview').hidden=true;action('reset').hidden=true;
    action('reset-grade').querySelector('span').textContent='Reset to look colors';
    $('.ff-legacy-balance').hidden=true;
    setTab('grade');
  }
  updateCatalogueAvailability();
  updateRecipeUI();setZoom(1);setSource(sourceMode,false);compare(false);
  $('.ff-prototype').textContent='ComfyUI';
  $('.ff-sidebar-footer p').textContent=editorMode==='film'?'Live film preview. Adjust colors in Color Grade; save using the output nodes.':'Live adjustments. Save to node before queueing the export branch.';
  return {element:root,
    setBaseRecipe(value){baseGradeRecipe=normalizeRecipe(value);recipe=composeGrade(baseGradeRecipe,gradeChanges);previousGrade=clone(recipe.grading.finish);startingRecipe=clone(recipe);history.length=0;history.push(snapshot());updateRecipeUI();},
    getRecipe:()=>clone(recipe),getLookId:()=>selectedLook,getPreviewMetrics:()=>live?.getMetrics?.()||[],pause(){video.pause();before.pause();},
    setAsset(value){if(asset?.asset===value?.asset)return;closeLive();asset=value;$$('.ff-look-image img').forEach(img=>{img.hidden=true;img.nextElementSibling.hidden=false;});syncCurrentLookPreview();hasHDR=hasHDR||Boolean(value?.info?.hdr);fps=value?.info?.fps||fps;previewKey='';previewClipKey='';rendered='';stillReady=false;showStill(false);sourceMode=value?.info?.hdr?'hdr':'original';setSource(sourceMode);},
    updateMedia(media){const newSource=media.source!==sources.original;sources={original:media.source||'',hdr:media.enhanced||''};hasHDR=Boolean(media.hasHDR);if(newSource){closeLive();previewController?.abort();clipController?.abort();lookPreviews.cancel();asset=null;stillReady=false;showStill(false);rendered='';previewKey='';previewClipKey='';}if(media.rendered){rendered=media.rendered;renderedRecipe=media.renderedRecipe||null;}label=media.label||label;setSource(sourceMode==='hdr'&&hasHDR?'hdr':'original');},
    dispose(){destroyed=true;lookObserver?.disconnect();clearTimeout(viewportTimer);lookPreviews.dispose();exportController?.abort();closeLive();previewController?.abort();clipController?.abort();clearTimeout(previewTimer);clearTimeout(historyTimer);thumbnailToken++;stopTick();abort.abort();clearTimeout(toastTimer);video.pause();before.pause();video.removeAttribute('src');before.removeAttribute('src');video.load();before.load();ownedURLs.forEach(URL.revokeObjectURL);root.remove();}};
}
