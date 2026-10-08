import { baseRecipe, clone, films, formats, looks, lookRecipe, matchLook, filmName, sameRecipe, timecode, neutralGrade, normalizeRecipe } from './model.js';

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
  const abort = new AbortController();
  const on = (element, event, callback) => element.addEventListener(event, callback, { signal: abort.signal });
  const root = document.createElement('section');
  root.className = 'ff-studio';
  root.setAttribute('aria-label', 'Fotufilm studio');
  let recipe = normalizeRecipe(options.recipe || baseRecipe());
  let startingRecipe = clone(recipe);
  let selectedLook = looks.some(look=>look.id===options.lookId) ? options.lookId : matchLook(recipe)?.id || null;
  let startingLook = selectedLook;
  let tab = 'looks', sourceMode = options.asset?.info?.hdr ? 'hdr' : 'original', comparing = false, zoom = 1, rate = 1;
  let sources = {original: options.source || '', hdr: options.enhanced || ''};
  let rendered = options.rendered || '';
  let renderedRecipe = options.renderedRecipe || null;
  let label = options.label || 'Your video';
  let fps = Math.max(1, options.fps || 24);
  let asset=options.asset||null, previewController=null, previewTimer=0, previewKey='', previewStatus='', previewEdge=960, gradeStage='balance', stillReady=false;
  let activeRenderedSource=sourceMode, previewClipKey='', pendingClipKey='', lookController=null, clipController=null, stillFrame=-1, swappingMedia=false;
  let hasHDR=Boolean(options.hasHDR||asset?.info?.hdr), lookTimer=0, exporting=false;
  const history=[clone(recipe)]; let historyTimer=0;
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
            <img class="ff-after-still" alt="Fotufilm preview" hidden/><div class="ff-before"><video class="ff-before-video" playsinline preload="auto" muted></video><img class="ff-before-still" alt="Source before finishing" hidden/></div>
          </div>
          <div class="ff-stage-label ff-stage-left" hidden>Original</div><div class="ff-stage-label ff-stage-right"></div>
          <label class="ff-wipe" hidden><span class="ff-wipe-line"><span>↔</span></span><input type="range" min="0" max="100" value="50" aria-label="Before and after divider"></label>
          <div class="ff-empty">${icon('film')}<h2>Your footage, in a new light.</h2><p>Connect a loaded video. Existing files appear without running the graph.</p>${button('open-file', 'Open video', 'folder')}<small>HDR finishing starts when the connected float master is available.</small></div>
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
        <div class="ff-monitor-status"><span class="ff-display">SDR video preview</span><span class="ff-render-state">Source playback</span></div>
      </main>
      <aside class="ff-sidebar" aria-label="Film recipe">
        <div class="ff-current"><span>Current look</span><div class="ff-look-title"><h1></h1><span class="ff-modified" hidden>Modified</span>${iconButton('reset', 'Reset this look', 'undo')}</div><p class="ff-recipe-summary"></p></div>
        <nav class="ff-tabs" aria-label="Recipe editor">${button('tab-looks', 'Looks', '', 'aria-pressed="true"')}${button('tab-customize', 'Film', '', 'aria-pressed="false"')}${button('tab-grade','Grade','','aria-pressed="false"')}</nav>
        <div class="ff-panel-content">
          <section class="ff-looks-panel"><p class="ff-intro">A complete film, color and texture recipe.</p><div class="ff-look-grid">${looks.map(look=>`<button class="ff-look" type="button" data-look="${look.id}" aria-pressed="false"><div class="ff-look-image"><img alt="" hidden/><span class="ff-thumb-empty">First frame</span><span class="ff-look-check">${icon('check')}</span></div><span class="ff-look-name">${look.name}</span><span class="ff-look-note">${look.note}</span></button>`).join('')}</div><p class="ff-thumbnail-note">Looks preview the first frame of your active source.</p></section>
          <section class="ff-customize-panel" hidden>
            <div class="ff-section"><div class="ff-section-heading"><h2>Film</h2><span>The foundation of your look</span></div><div class="ff-films">${films.map(([id,name,note])=>`<button type="button" data-film="${id}" aria-pressed="false"><span>${name}</span><small>${note}</small>${icon('check')}</button>`).join('')}</div>
              <h3>Film size</h3><div class="ff-chips">${formats.map(([id,name])=>`<button type="button" data-format="${id}" aria-pressed="false">${name}</button>`).join('')}</div><p class="ff-help">Changes the scale of grain and halation, not the crop.</p>
              <h3>Print / scan</h3><div class="ff-print">${[['screen','Digital reference'],['vision-2383','Kodak 2383'],['vision-2393','Kodak 2393']].map(([id,name])=>`<button type="button" data-medium="${id}" aria-pressed="false">${name}</button>`).join('')}</div>
              <label class="ff-reference">Screen conversion<select data-control="digitalReference"><option value="graded-print">Graded print</option><option value="reference-exposure">Reference exposure</option></select></label>
            </div>
            <details class="ff-section"><summary>Film exposure & print response</summary><div class="ff-light-sliders"></div></details>
            <div class="ff-section"><div class="ff-section-heading"><h2>Texture</h2></div><div class="ff-texture-sliders"></div><p class="ff-help">Texture is rendered by Fotufilm on the server.</p></div>
          </section>
          <section class="ff-grade-panel" hidden><div class="ff-grade-stage" role="group" aria-label="Grading stage">${button('grade-balance','Balance input','','aria-pressed="true"')}${button('grade-finish','Finish look','','aria-pressed="false"')}</div><p class="ff-help ff-grade-help">Gear grading before Fotufilm. Changes the light exposing the film.</p><div class="ff-grade-sliders"></div><details><summary>Color wheels</summary><div class="ff-wheels"></div></details>${button('reset-grade','Reset this grade')}<details class="ff-scopes"><summary>Preview histogram</summary><canvas width="256" height="88" aria-label="SDR display histogram"></canvas><p class="ff-help">SDR display values after finishing. Not an HDR luminance scope.</p></details></section>
        </div>
        <footer class="ff-sidebar-footer"><div class="ff-preview-settings"><label>Preview <select class="ff-quality" aria-label="Preview quality"><option value="960">960px · Smooth</option><option value="1440">1440px · Detailed</option></select></label>${button('undo','Undo','undo')}</div>${button('render', 'Run connected workflow', 'play', 'class="ff-render-button"')}<div class="ff-export-row"><select class="ff-export-format" aria-label="Export format"><option value="mp4">MP4 · SDR</option><option value="prores422hq">ProRes 422 HQ · SDR</option><option value="hlg">HEVC · HDR HLG</option></select>${button('export','Export video')}</div><a class="ff-download" hidden download>Download finished video ↗</a><p>Automatic previews use native Fotufilm and Gear grading.</p></footer>
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
  function updateScope(image){
    const canvas=document.createElement('canvas');canvas.width=256;canvas.height=144;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,256,144);
    const pixels=ctx.getImageData(0,0,256,144).data,hist=new Uint32Array(256);
    for(let i=0;i<pixels.length;i+=4)hist[Math.round(.2126*pixels[i]+.7152*pixels[i+1]+.0722*pixels[i+2])]++;
    const target=$('.ff-scopes canvas'),draw=target.getContext('2d'),peak=Math.max(...hist,1);draw.clearRect(0,0,256,88);draw.fillStyle='#b6dfcf';
    for(let i=0;i<256;i++){const h=88*Math.sqrt(hist[i]/peak);draw.fillRect(i,88-h,1,h);}
  }
  function schedulePreview(force=false){
    if(!options.preview||!asset||destroyed)return;
    const key=JSON.stringify([asset.asset,recipe,previewEdge]);
    if(!force&&key===previewKey)return;
    if(key!==previewKey){clipController?.abort();lookController?.abort();clearTimeout(lookTimer);clearTimeout(historyTimer);historyTimer=setTimeout(()=>{if(!history.length||!sameRecipe(history.at(-1),recipe)){history.push(clone(recipe));if(history.length>30)history.shift();action('undo').disabled=history.length<2;}},250);}
    previewKey=key;if(force&&Math.abs(video.currentTime*fps-stillFrame)>=1){stillReady=false;showStill(false);}clearTimeout(previewTimer);previewController?.abort();previewController=new AbortController();
    const controller=previewController,snapshot=clone(recipe),currentAsset=asset;
    setStatus('Updating film preview…');
    previewTimer=setTimeout(async()=>{
      try{
        const frame=Math.min(currentAsset.info.frames-1,Math.max(0,Math.round(video.currentTime*fps)));
        const still=await options.preview.render(currentAsset.asset,snapshot,{frame,edge:previewEdge,signal:controller.signal});
        if(destroyed||controller.signal.aborted)return;
        const afterImage=$('.ff-after-still'),beforeImage=$('.ff-before-still');
        afterImage.src=still.after;beforeImage.src=still.before;
        await Promise.all([afterImage.decode(),beforeImage.decode()]);
        if(destroyed||controller.signal.aborted)return;
        stillReady=true;stillFrame=frame;showStill(video.paused&&Math.abs(video.currentTime*fps-frame)<1);updateScope(afterImage);renderedRecipe=snapshot;
        action('compare').disabled=false;$('.ff-stage-left').textContent='Before grade & film';$('.ff-stage-right').textContent='After · Gear + Fotufilm';
        $('.ff-display').textContent=currentAsset.info.hdr?'HDR master → SDR display preview':'SDR source → film preview';
        setStatus(`Frame ready · ${still.seconds}s${still.cached?' · cached':still.filmCacheHits?' · film reused':''}`);
        if(previewClipKey!==key&&(pendingClipKey!==key||clipController?.signal.aborted))updatePlayback(key,currentAsset,snapshot);
      }catch(error){if(error.name!=='AbortError')setStatus(`Preview: ${error.message}`);}
    },100);
  }
  async function updatePlayback(key,currentAsset,snapshot){
    clipController?.abort();clipController=new AbortController();const controller=clipController,clipSignal=controller.signal,edge=previewEdge;
    pendingClipKey=key;
    try{
      // Let the current frame settle before spending work on every frame of the clip.
      await new Promise(resolve=>setTimeout(resolve,400));
      if(destroyed||clipSignal.aborted)return;
      setStatus('Frame ready · updating playback…');
      const clip=await options.preview.render(currentAsset.asset,snapshot,{mode:'clip',edge,signal:clipSignal,channel:'playback',onProgress:state=>{if(!clipSignal.aborted)setStatus(`Updating playback · ${Math.round(state.progress*100)}%`);}});
      if(destroyed||clipSignal.aborted)return;
      const time=video.currentTime,playing=!video.paused,wasComparing=comparing;
      rendered=clip.after;activeRenderedSource=sourceMode;previewClipKey=key;
      swappingMedia=true;
      const restore=()=>{video.currentTime=Math.min(time,Math.max(0,video.duration-.001));before.currentTime=video.currentTime;if(playing)video.play().catch(()=>{});compare(wasComparing);swappingMedia=false;video.style.visibility='';for(const name of ['play','back','next','loop','audio','fullscreen'])action(name).disabled=false;};
      video.addEventListener('loadedmetadata',restore,{once:true,signal:abort.signal});
      video.src=clip.after;before.src=clip.before;video.load();before.load();
      makeThumbnails(clip.after);lookTimer=setTimeout(scheduleLookPreviews,1500);
      setStatus(`Preview ready · ${clip.width||currentAsset.info.width}px · ${clip.frames} frames${clip.frames<currentAsset.info.frames?' · first 20s':''}`);
    }catch(error){if(error.name!=='AbortError'&&!clipSignal.aborted)setStatus(`Playback: ${error.message}`);}
    finally{if(clipController===controller)pendingClipKey='';}
  }
  async function scheduleLookPreviews(){
    if(!options.preview||!asset||destroyed)return;
    lookController?.abort();lookController=new AbortController();const controller=lookController,current=asset;
    // Sequential thumbnails keep video rendering responsive and memory bounded.
    for(const look of looks){
      if($(`[data-look="${look.id}"] img`).dataset.asset===current.asset)continue;
      if(controller.signal.aborted||destroyed)return;
      try{
        const result=await options.preview.render(current.asset,lookRecipe(look.id,recipe.seed),{frame:0,edge:280,signal:controller.signal,channel:'looks'});
        if(controller.signal.aborted)return;
        const image=$(`[data-look="${look.id}"] img`);image.src=result.after;image.dataset.asset=current.asset;image.hidden=false;image.nextElementSibling.hidden=true;
      }catch(error){if(error.name==='AbortError')return;$('.ff-thumbnail-note').textContent='Look previews unavailable: '+error.message;return;}
    }
    $('.ff-thumbnail-note').textContent=current.info.hdr?'Rendered from your HDR master.':'Rendered from the first frame of your video.';
  }
  async function exportVideo(){
    if(!asset||!options.preview){toast('Connect an available source first.');return;}
    $('.ff-download').hidden=true;const target=action('export');exporting=true;target.disabled=true;const snapshot=clone(recipe);
    try{
      options.onSave?.(snapshot,selectedLook);
      const result=await options.preview.render(asset.asset,snapshot,{mode:'export',format:$('.ff-export-format').value,signal:abort.signal,channel:'export',onProgress:state=>target.textContent=`Export ${Math.round(state.progress*100)}%`});
      const link=$('.ff-download');link.href=result.after;link.hidden=false;link.textContent='Download finished video ↗';toast('Full-resolution export ready.');
    }catch(error){if(error.name!=='AbortError')toast(error.message);}
    finally{exporting=false;target.disabled=!asset;target.textContent='Export video';}
  }
  on($('.ff-quality'),'change',event=>{previewEdge=Number(event.target.value);schedulePreview(true);});
  const gradeSliders=[['exposure','Exposure',-5,5,.05,' EV'],['temperature','Warmth',-1,1,.01,''],['tint','Tint',-1,1,.01,''],['contrast','Contrast',.25,2,.01,''],['highlights','Highlights',-2,2,.02,''],['shadows','Shadows',-2,2,.02,''],['saturation','Saturation',0,2,.01,''],['vibrance','Vibrance',-1,1,.01,'']];
  for(const [key,name,min,max,step,unit] of gradeSliders){
    const label=document.createElement('label');label.className='ff-slider';label.innerHTML=`<span>${name}<output></output></span><input type="range" data-grade="${key}" data-digits="2" data-unit="${unit}" min="${min}" max="${max}" step="${step}" aria-label="Grade ${name}">`;$('.ff-grade-sliders').append(label);
    on(label.querySelector('input'),'input',event=>{recipe.grading[gradeStage][key]=Number(event.target.value);updateRecipeUI();});
  }
  const wheelNames=[['lift','Shadows'],['gamma','Midtones'],['gain','Highlights'],['offset','Offset']];
  for(const [key,name] of wheelNames){
    const wrap=document.createElement('div');wrap.className='ff-wheel-wrap';wrap.dataset.wheel=key;
    wrap.innerHTML=`<span>${name}</span><div class="ff-wheel" role="slider" tabindex="0" aria-label="${name} color wheel" aria-valuemin="-1" aria-valuemax="1"><i></i></div><label class="ff-wheel-master">Master <input type="range" aria-label="${name} master" min="${['gamma','gain'].includes(key)?.1:-.3}" max="${['gamma','gain'].includes(key)?2:.3}" step=".005"></label>`;
    $('.ff-wheels').append(wrap);const wheel=wrap.querySelector('.ff-wheel'),master=wrap.querySelector('input');
    const fromPoint=(x,y)=>{const length=Math.hypot(x,y);if(length>1){x/=length;y/=length;}const rgb=[x,-.5*x-.866*y,-.5*x+.866*y],mean=Number(master.value),amount=['gamma','gain'].includes(key)?.35:.12;recipe.grading[gradeStage][key]=rgb.map(v=>Math.max(key==='gamma'?.1:key==='gain'?0:-1,Math.min(key==='gamma'||key==='gain'?4:1,mean+v*amount)));updateRecipeUI();};
    const move=event=>{const box=wheel.getBoundingClientRect();fromPoint((event.clientX-box.left)/box.width*2-1,(event.clientY-box.top)/box.height*2-1);};
    on(wheel,'pointerdown',event=>{event.preventDefault();event.stopPropagation();wheel.setPointerCapture(event.pointerId);move(event);});
    on(wheel,'pointermove',event=>{if(wheel.hasPointerCapture(event.pointerId)){event.stopPropagation();move(event);}});
    on(wheel,'pointerup',event=>{if(wheel.hasPointerCapture(event.pointerId))wheel.releasePointerCapture(event.pointerId);});
    on(wheel,'keydown',event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key))return;event.preventDefault();event.stopPropagation();const dot=wheel.querySelector('i'),x=Number(dot.dataset.x||0),y=Number(dot.dataset.y||0);fromPoint(event.key==='Home'?0:x+(event.key==='ArrowLeft'?-.05:event.key==='ArrowRight'?.05:0),event.key==='Home'?0:y+(event.key==='ArrowUp'?-.05:event.key==='ArrowDown'?.05:0));});
    on(master,'input',()=>{const vector=recipe.grading[gradeStage][key],mean=vector.reduce((a,b)=>a+b)/3;recipe.grading[gradeStage][key]=vector.map(v=>Math.max(key==='gamma'?.1:key==='gain'?0:-1,Math.min(['gamma','gain'].includes(key)?4:1,v-mean+Number(master.value))));updateRecipeUI();});
  }
  function updateWheels(){
    for(const [key] of wheelNames){const wrap=$(`[data-wheel="${key}"]`);if(!wrap)continue;const vector=recipe.grading[gradeStage][key],mean=vector.reduce((a,b)=>a+b)/3,amount=['gamma','gain'].includes(key)?.35:.12,x=(vector[0]-mean)/amount,y=(vector[2]-vector[1])/(1.732*amount),dot=wrap.querySelector('i');dot.dataset.x=x;dot.dataset.y=y;dot.style.left=`${50+Math.max(-1,Math.min(1,x))*46}%`;dot.style.top=`${50+Math.max(-1,Math.min(1,y))*46}%`;wrap.querySelector('input').value=mean;wrap.querySelector('[role=slider]').setAttribute('aria-valuetext',vector.map(v=>v.toFixed(3)).join(', '));}
  }
  function updateRecipeUI() {
    const look = looks.find(x=>x.id === selectedLook);
    $('.ff-look-title h1').textContent = look?.name || 'Custom recipe';
    $('.ff-modified').hidden = !look || sameRecipe(recipe, lookRecipe(look.id));
    $('.ff-recipe-summary').textContent = `${filmLabel()} · ${formats.find(x=>x[0]===recipe.format)?.[1] || recipe.format} · ${recipe.medium === 'screen' ? 'Digital' : recipe.medium.replace('vision-', '')}`;
    $$('.ff-look').forEach(el=>el.setAttribute('aria-pressed', String(el.dataset.look === selectedLook)));
    for (const [attribute, value] of [['film',recipe.stock],['format',recipe.format],['medium',recipe.medium]]) {
      $$(`[data-${attribute}]`).forEach(el=>el.setAttribute('aria-pressed',String(el.dataset[attribute] === value)));
    }
    $$('input[data-section]').forEach(input=> {input.value=recipe[input.dataset.section][input.dataset.key]; updateSlider(input);});
    $('[data-control="digitalReference"]').value = recipe.digitalReference;
    $('.ff-render-state').textContent = previewStatus || (renderedRecipe ? (sameRecipe(recipe,renderedRecipe)?'Rendered recipe · up to date':'Recipe changed · run workflow to update') : options.onRender ? 'Save your recipe, then run the workflow' : changed() ? 'Recipe edited · demo render unchanged' : rendered ? 'Existing render · interface preview' : 'Source playback');
    action('reset').disabled = !selectedLook || sameRecipe(recipe, lookRecipe(selectedLook));
    root.querySelectorAll('[data-grade]').forEach(input=>{input.value=recipe.grading[gradeStage][input.dataset.grade];updateSlider(input);});
    action('undo').disabled=history.length<2;updateWheels(); schedulePreview();
  }
  function updateSlider(input) {
    const value = Number(input.value), digits = Number(input.dataset.digits || 0);
    input.closest('.ff-slider').querySelector('output').textContent = `${value.toFixed(digits)}${input.dataset.unit || ''}`;
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
    const label = document.createElement('label'); label.className='ff-slider';
    label.innerHTML = `<span>${text}<output></output></span><input type="range" data-section="${section}" data-key="${key}" data-digits="${digits}" data-unit="${unit}" min="${min}" max="${max}" step="${step}" aria-label="${text}">`;
    $(`.ff-${group}-sliders`).append(label);
    const input=label.querySelector('input');
    on(input,'input',()=>{recipe[section][key]=Number(input.value);updateRecipeUI();});
  }
  on($('[data-control="digitalReference"]'),'change',event=>{recipe.digitalReference=event.target.value;updateRecipeUI();});
  function setTab(next) {
    tab=next; $('.ff-looks-panel').hidden=tab!=='looks'; $('.ff-customize-panel').hidden=tab!=='customize'; $('.ff-grade-panel').hidden=tab!=='grade';
    action('tab-looks').setAttribute('aria-pressed',String(tab==='looks'));action('tab-customize').setAttribute('aria-pressed',String(tab==='customize'));action('tab-grade').setAttribute('aria-pressed',String(tab==='grade'));
    $('.ff-panel-content').scrollTop=0;
  }
  function setZoom(value) {
    zoom=Math.min(4,Math.max(1,value)); if(zoom===1)pan={x:0,y:0};
    $('.ff-zoom').textContent=`${Math.round(zoom*100)}%`; action('fit').setAttribute('aria-pressed',String(zoom===1));
    action('minus').disabled=zoom===1; action('plus').disabled=zoom===4;
    for (const surface of [video,before,$('.ff-after-still'),$('.ff-before-still')]) surface.style.transform=`translate(${pan.x}px,${pan.y}px) scale(${zoom})`;
    stage.style.cursor=zoom>1?'grab':'';
  }
  function updateTransport() {
    const duration=Number.isFinite(video.duration)?video.duration:0;
    $('.ff-time').innerHTML=`${timecode(video.currentTime,fps)} <span>/ ${timecode(duration,fps)}</span>`;
    $('.ff-scrubber').max=String(duration||1);$('.ff-scrubber').value=String(video.currentTime);
    $('.ff-timeline').style.setProperty('--progress',`${duration?100*video.currentTime/duration:0}%`);
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
  function seek(time) {const duration=Number.isFinite(video.duration)?video.duration:0; video.currentTime=Math.min(duration,Math.max(0,time));if(before.readyState>=1)before.currentTime=video.currentTime;updateTransport();}
  function compare(value) {
    comparing=Boolean(value&&(stillReady||(rendered&&activeRenderedSource===sourceMode)));
    $('.ff-before').hidden=!comparing;$('.ff-stage-left').hidden=!comparing;$('.ff-wipe').hidden=!comparing;
    action('compare').setAttribute('aria-pressed',String(comparing));
    if(comparing){before.currentTime=video.currentTime;if(!video.paused)before.play().catch(()=>toast('The reference clip could not play.'));}else before.pause();
  }
  on($('.ff-wipe input'),'input',event=>{stage.style.setProperty('--wipe',`${event.target.value}%`);$('.ff-before').style.clipPath=`inset(0 ${100-Number(event.target.value)}% 0 0)`;});
  function setSource(mode, preserve=true) {
    const time=preserve?video.currentTime:0, wasPlaying=!video.paused;
    video.pause(); before.pause(); sourceMode=mode; compare(false);
    const current=sources[mode]||(mode==='hdr'&&hasHDR?sources.original:'');
    const after=mode===activeRenderedSource?rendered:'';
    const pendingHDR=mode==='hdr'&&!after;video.style.visibility=pendingHDR?'hidden':'';
    $('.ff-empty').hidden=Boolean(current||asset);$('.ff-video-error').hidden=true;
    $('.ff-file-name').textContent=label;
    if(current){video.src=after||current;before.src=current;video.load();before.load();}
    else {video.removeAttribute('src');before.removeAttribute('src');video.load();before.load();}
    action('source-original').setAttribute('aria-pressed',String(mode==='original'));action('source-hdr').setAttribute('aria-pressed',String(mode==='hdr'));
    action('source-hdr').disabled=!hasHDR&&!sources.hdr;action('compare').disabled=!after;
    $('.ff-stage-right').textContent=after?'Existing Fotufilm render':mode==='hdr'?'Preparing HDR preview…':'Original source';
    $('.ff-display').textContent=mode==='hdr'?'HDR source · browser video preview, not a calibrated HDR monitor':'SDR video preview';
    const restore=()=>{if(!destroyed){seek(time);if(wasPlaying&&!pendingHDR)video.play().catch(()=>{});}video.removeEventListener('loadedmetadata',restore);};
    video.addEventListener('loadedmetadata',restore,{once:true,signal:abort.signal});
    updateRecipeUI();updateTransport();
    for(const name of ['play','back','next','loop','audio','fullscreen'])action(name).disabled=!current||pendingHDR;
    $('.ff-scrubber').disabled=!current;
    if(current&&!pendingHDR)makeThumbnails(current);
    if(asset&&Boolean(asset.info.hdr)!==(mode==='hdr')){asset=null;previewController?.abort();clipController?.abort();lookController?.abort();clearTimeout(previewTimer);stillReady=false;showStill(false);}
    action('export').disabled=!asset||exporting;schedulePreview();
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
  on(video,'play',()=>{showStill(false);stopTick();tick();});on(video,'pause',()=>{stopTick();before.pause();updateTransport();if(!swappingMedia){showStill(stillReady&&Math.abs(video.currentTime*fps-stillFrame)<1);schedulePreview(true);}});
  on(video,'seeked',()=>{updateTransport();if(video.paused&&!swappingMedia)schedulePreview(true);});on(video,'timeupdate',updateTransport);
  on(video,'error',()=>{$('.ff-video-error').hidden=false;$('.ff-video-error').textContent='This browser cannot play the clip. Use an H.264 MP4 preview or choose another video.';});
  on($('.ff-scrubber'),'input',event=>seek(Number(event.target.value)));
  on($('.ff-rate select'),'change',event=>{rate=Number(event.target.value);video.playbackRate=rate;before.playbackRate=rate;});
  on($('.ff-file-input'),'change',async event=>{
    const file=event.target.files[0];if(!file)return;asset=null;hasHDR=false;previewController?.abort();clipController?.abort();lookController?.abort();stillReady=false;showStill(false);const url=URL.createObjectURL(file);ownedURLs.push(url);sources={original:url,hdr:''};rendered='';label=file.name;setSource('original',false);if(options.onUpload){try{await options.onUpload(file);}catch(error){toast(error.message);}}else toast('Local playback only. Connect this clip to the workflow to finish it.');
  });
  on(root,'click',async event=>{
    const target=event.target.closest('button');if(!target||target.disabled)return;
    if(target.dataset.look){selectedLook=target.dataset.look;recipe=lookRecipe(selectedLook,recipe.seed);updateRecipeUI();return;}
    if(target.dataset.film){recipe.stock=target.dataset.film;updateRecipeUI();return;}
    if(target.dataset.format){recipe.format=target.dataset.format;updateRecipeUI();return;}
    if(target.dataset.medium){recipe.medium=target.dataset.medium;updateRecipeUI();return;}
    switch(target.dataset.action){
      case 'play':await play();break;
      case 'back':video.pause();seek(video.currentTime-1/fps);break;
      case 'next':video.pause();seek(video.currentTime+1/fps);break;
      case 'loop':video.loop=!video.loop;before.loop=video.loop;target.setAttribute('aria-pressed',String(video.loop));break;
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
      case 'grade-balance':case 'grade-finish':gradeStage=target.dataset.action.slice(6);action('grade-balance').setAttribute('aria-pressed',String(gradeStage==='balance'));action('grade-finish').setAttribute('aria-pressed',String(gradeStage==='finish'));$('.ff-grade-help').textContent=gradeStage==='balance'?'Gear grading before Fotufilm. Changes the light exposing the film.':'Gear grading after Fotufilm. Refines the developed look.';updateRecipeUI();break;
      case 'reset-grade':recipe.grading[gradeStage]=neutralGrade();updateRecipeUI();break;
      case 'undo':if(history.length>1){clearTimeout(historyTimer);history.pop();recipe=clone(history.at(-1));previewKey='';updateRecipeUI();}break;
      case 'export':await exportVideo();break;
      case 'reset':if(selectedLook){recipe=lookRecipe(selectedLook,recipe.seed);updateRecipeUI();}break;
      case 'open-file':$('.ff-file-input').click();break;
      case 'render':
        if(!options.onRender){toast('Interface preview only. Connect Develop and Return to Studio in your workflow to render.');break;}
        target.disabled=true;
        try{await options.onRender(clone(recipe),selectedLook);startingRecipe=clone(recipe);startingLook=selectedLook;toast('Workflow queued. The server will return its finished preview here.');}
        catch(error){toast(`Could not queue workflow: ${error.message}`);}
        finally{target.disabled=false;updateRecipeUI();}break;
      case 'cancel':if(options.onClose)options.onClose();else {recipe=clone(startingRecipe);selectedLook=startingLook;updateRecipeUI();toast('Unsaved recipe changes discarded.');}break;
      case 'save':options.onSave?.(clone(recipe),selectedLook);startingRecipe=clone(recipe);startingLook=selectedLook;updateRecipeUI();if(!options.onSave)toast('Recipe saved for this preview session.');break;
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
  updateRecipeUI();setZoom(1);setSource(sourceMode,false);compare(false);
  if(options.onRender){
    $('.ff-prototype').textContent='Workflow studio';action('render').removeAttribute('aria-disabled');
    action('render').title='Save this recipe and run the connected workflow on your ComfyUI server. Uncached upstream stages run too.';
    action('render').querySelector('span').textContent='Run workflow';
    $('.ff-sidebar-footer p').textContent=options.preview?'Edits preview automatically. Export uses full-resolution source.':'Renders on your ComfyUI server. The finished preview returns here.';
  }
  return {element:root,getRecipe:()=>clone(recipe),getLookId:()=>selectedLook,pause(){video.pause();before.pause();},
    setAsset(value){if(asset?.asset===value?.asset)return;asset=value;$$('.ff-look-image img').forEach(img=>{if(img.dataset.asset!==value?.asset){img.hidden=true;img.nextElementSibling.hidden=false;}});hasHDR=hasHDR||Boolean(value?.info?.hdr);fps=value?.info?.fps||fps;previewKey='';previewClipKey='';rendered='';stillReady=false;showStill(false);sourceMode=value?.info?.hdr?'hdr':'original';setSource(sourceMode);},
    updateMedia(media){const newSource=media.source!==sources.original;sources={original:media.source||'',hdr:media.enhanced||''};hasHDR=Boolean(media.hasHDR);if(newSource){previewController?.abort();clipController?.abort();lookController?.abort();asset=null;stillReady=false;showStill(false);rendered='';previewKey='';previewClipKey='';}if(media.rendered){rendered=media.rendered;renderedRecipe=media.renderedRecipe||null;}label=media.label||label;setSource(sourceMode==='hdr'&&hasHDR?'hdr':'original');},
    dispose(){destroyed=true;previewController?.abort();clipController?.abort();lookController?.abort();clearTimeout(lookTimer);clearTimeout(previewTimer);clearTimeout(historyTimer);thumbnailToken++;stopTick();abort.abort();clearTimeout(toastTimer);video.pause();before.pause();video.removeAttribute('src');before.removeAttribute('src');video.load();before.load();ownedURLs.forEach(URL.revokeObjectURL);root.remove();}};
}
