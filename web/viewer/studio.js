import { baseRecipe, clone, films, formats, looks, lookRecipe, matchLook, filmName, sameRecipe, timecode } from './model.js';

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
  let recipe = clone(options.recipe || baseRecipe());
  let startingRecipe = clone(recipe);
  let selectedLook = looks.some(look=>look.id===options.lookId) ? options.lookId : matchLook(recipe)?.id || null;
  let startingLook = selectedLook;
  let tab = 'looks', sourceMode = 'original', comparing = false, zoom = 1, rate = 1;
  let sources = {original: options.source || '', hdr: options.enhanced || ''};
  let rendered = options.rendered || '';
  let label = options.label || 'Your video';
  const fps = Math.max(1, options.fps || 24);
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
            ${button('source-hdr', 'Enhanced HDR', '', 'aria-pressed="false" title="Connect an enhanced HDR video to the viewer node."')}
          </div>
        </div>
        <div class="ff-stage" tabindex="0" aria-label="Video preview. Space to play or pause. Arrow keys to step frames.">
          <div class="ff-picture"><video class="ff-main-video" playsinline preload="auto" muted></video>
            <div class="ff-before"><video class="ff-before-video" playsinline preload="auto" muted></video></div>
          </div>
          <div class="ff-stage-label ff-stage-left" hidden>Original</div><div class="ff-stage-label ff-stage-right"></div>
          <label class="ff-wipe" hidden><span class="ff-wipe-line"><span>↔</span></span><input type="range" min="0" max="100" value="50" aria-label="Before and after divider"></label>
          <div class="ff-empty">${icon('film')}<h2>Your footage, in a new light.</h2><p>Connect a video and run this viewer node once.</p>${button('open-file', 'Choose a local preview clip', 'folder')}<small>Local clips are for preview only. They do not change the workflow input.</small></div>
          <div class="ff-video-error" role="alert" hidden></div>
        </div>
        <div class="ff-transport">
          <div class="ff-playback">${iconButton('back', 'Previous frame (Left arrow)', 'back')}${iconButton('play', 'Play (Space)', 'play')}${iconButton('next', 'Next frame (Right arrow)', 'next')}<span class="ff-time">00:00:00 <span>/ 00:00:00</span></span></div>
          <div class="ff-view-actions">${button('compare', 'Before / after', 'compare', 'aria-pressed="false" title="Compare the original with an existing rendered clip."')}${iconButton('loop', 'Loop playback', 'loop')}${iconButton('audio', 'Unmute audio', 'mute')}<label class="ff-rate"><span class="ff-sr-only">Playback speed</span><select aria-label="Playback speed"><option value=".5">0.5×</option><option value="1" selected>1×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></label><span class="ff-divider"></span>${button('fit', 'Fit', '', 'aria-pressed="true"')}${button('minus', '−', '', 'aria-label="Zoom out"')}<span class="ff-zoom">100%</span>${button('plus', '+', '', 'aria-label="Zoom in"')}${iconButton('fullscreen', 'Fullscreen viewer', 'expand')}</div>
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
        <nav class="ff-tabs" aria-label="Recipe editor">${button('tab-looks', 'Looks', '', 'aria-pressed="true"')}${button('tab-customize', 'Customize', '', 'aria-pressed="false"')}</nav>
        <div class="ff-panel-content">
          <section class="ff-looks-panel"><p class="ff-intro">A complete film, color and texture recipe.</p><div class="ff-look-grid">${looks.map(look=>`<button class="ff-look" type="button" data-look="${look.id}" aria-pressed="false"><div class="ff-look-image"><img alt="" hidden/><span class="ff-thumb-empty">First frame</span><span class="ff-look-check">${icon('check')}</span></div><span class="ff-look-name">${look.name}</span><span class="ff-look-note">${look.note}</span></button>`).join('')}</div><p class="ff-thumbnail-note">Source thumbnails for this interface preview.</p></section>
          <section class="ff-customize-panel" hidden>
            <div class="ff-section"><div class="ff-section-heading"><h2>Film</h2><span>The foundation of your look</span></div><div class="ff-films">${films.map(([id,name,note])=>`<button type="button" data-film="${id}" aria-pressed="false"><span>${name}</span><small>${note}</small>${icon('check')}</button>`).join('')}</div>
              <h3>Film size</h3><div class="ff-chips">${formats.map(([id,name])=>`<button type="button" data-format="${id}" aria-pressed="false">${name}</button>`).join('')}</div><p class="ff-help">Changes the scale of grain and halation, not the crop.</p>
              <h3>Print / scan</h3><div class="ff-print">${[['screen','Digital reference'],['vision-2383','Kodak 2383'],['vision-2393','Kodak 2393']].map(([id,name])=>`<button type="button" data-medium="${id}" aria-pressed="false">${name}</button>`).join('')}</div>
              <label class="ff-reference">Screen conversion<select data-control="digitalReference"><option value="graded-print">Graded print</option><option value="reference-exposure">Reference exposure</option></select></label>
            </div>
            <div class="ff-section"><div class="ff-section-heading"><h2>Light & color</h2></div><div class="ff-light-sliders"></div></div>
            <div class="ff-section"><div class="ff-section-heading"><h2>Texture</h2></div><div class="ff-texture-sliders"></div><p class="ff-help">Texture is rendered by Fotufilm on the server.</p></div>
          </section>
        </div>
        <footer class="ff-sidebar-footer">${button('render', 'Render preview', 'play', 'class="ff-render-button" aria-disabled="true" title="GPU preview rendering is the next development phase."')}<p>Playback and recipe editing are ready to review.<br>Live film rendering comes next.</p></footer>
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
    $('.ff-render-state').textContent = changed() ? 'Recipe edited · render preview not connected' : rendered ? 'Existing render · film controls do not update it yet' : 'Source playback · film rendering not connected';
    action('reset').disabled = !selectedLook || sameRecipe(recipe, lookRecipe(selectedLook));
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
    tab=next; $('.ff-looks-panel').hidden=tab!=='looks'; $('.ff-customize-panel').hidden=tab!=='customize';
    action('tab-looks').setAttribute('aria-pressed',String(tab==='looks'));action('tab-customize').setAttribute('aria-pressed',String(tab==='customize'));
    $('.ff-panel-content').scrollTop=0;
  }
  function setZoom(value) {
    zoom=Math.min(4,Math.max(1,value)); if(zoom===1)pan={x:0,y:0};
    $('.ff-zoom').textContent=`${Math.round(zoom*100)}%`; action('fit').setAttribute('aria-pressed',String(zoom===1));
    action('minus').disabled=zoom===1; action('plus').disabled=zoom===4;
    for (const surface of [video,before]) surface.style.transform=`translate(${pan.x}px,${pan.y}px) scale(${zoom})`;
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
    if(!video.src)return;
    if(video.paused){try{await video.play();if(comparing){before.currentTime=video.currentTime;await before.play();}}catch{toast('This clip could not play. Try an H.264 MP4 preview.');}}
    else {video.pause();before.pause();}
  }
  function seek(time) {const duration=Number.isFinite(video.duration)?video.duration:0; video.currentTime=Math.min(duration,Math.max(0,time));if(before.readyState>=1)before.currentTime=video.currentTime;updateTransport();}
  function compare(value) {
    comparing=Boolean(value&&rendered&&sourceMode==='original');
    $('.ff-before').hidden=!comparing;$('.ff-stage-left').hidden=!comparing;$('.ff-wipe').hidden=!comparing;
    action('compare').setAttribute('aria-pressed',String(comparing));
    if(comparing){before.currentTime=video.currentTime;if(!video.paused)before.play().catch(()=>toast('The reference clip could not play.'));}else before.pause();
  }
  on($('.ff-wipe input'),'input',event=>{stage.style.setProperty('--wipe',`${event.target.value}%`);$('.ff-before').style.clipPath=`inset(0 ${100-Number(event.target.value)}% 0 0)`;});
  function setSource(mode, preserve=true) {
    const time=preserve?video.currentTime:0, wasPlaying=!video.paused;
    video.pause(); before.pause(); sourceMode=mode; compare(false);
    const current=sources[mode];
    const after=mode==='original'?rendered:'';
    $('.ff-empty').hidden=Boolean(current);$('.ff-video-error').hidden=true;
    $('.ff-file-name').textContent=label;
    if(current){video.src=after||current;before.src=current;video.load();before.load();}
    else {video.removeAttribute('src');before.removeAttribute('src');video.load();before.load();}
    action('source-original').setAttribute('aria-pressed',String(mode==='original'));action('source-hdr').setAttribute('aria-pressed',String(mode==='hdr'));
    action('source-hdr').disabled=!sources.hdr;action('compare').disabled=!after;
    $('.ff-stage-right').textContent=after?'Existing Fotufilm render':mode==='hdr'?'Enhanced source':'Original source';
    $('.ff-display').textContent=mode==='hdr'?'HDR source · browser video preview, not a calibrated HDR monitor':'SDR video preview';
    const restore=()=>{if(!destroyed){seek(time);if(wasPlaying)video.play().catch(()=>{});}video.removeEventListener('loadedmetadata',restore);};
    video.addEventListener('loadedmetadata',restore,{once:true,signal:abort.signal});
    updateRecipeUI();updateTransport();
    for(const name of ['play','back','next','loop','audio','fullscreen'])action(name).disabled=!current;
    $('.ff-scrubber').disabled=!current;
    if(current)makeThumbnails(current);
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
        if(i===0)$$('.ff-look-image img').forEach(img=>{img.src=thumbnail;img.hidden=false;img.nextElementSibling.hidden=true;});
      }
    }catch{/* Thumbnails are optional; playback remains available. */}
    finally{probe.removeAttribute('src');probe.load();}
  }
  on(video,'loadedmetadata',()=>{
    $('.ff-file-info').textContent=`${video.videoWidth} × ${video.videoHeight} / ${fps} fps`;
    $$('.ff-ticks span').forEach((el,i)=>el.textContent=timecode(video.duration*i/5,fps).slice(0,5));updateTransport();
  });
  on(video,'play',()=>{stopTick();tick();});on(video,'pause',()=>{stopTick();before.pause();updateTransport();});
  on(video,'seeked',updateTransport);on(video,'timeupdate',updateTransport);
  on(video,'error',()=>{$('.ff-video-error').hidden=false;$('.ff-video-error').textContent='This browser cannot play the clip. Use an H.264 MP4 preview or choose another video.';});
  on($('.ff-scrubber'),'input',event=>seek(Number(event.target.value)));
  on($('.ff-rate select'),'change',event=>{rate=Number(event.target.value);video.playbackRate=rate;before.playbackRate=rate;});
  on($('.ff-file-input'),'change',event=>{
    const file=event.target.files[0];if(!file)return;const url=URL.createObjectURL(file);ownedURLs.push(url);sources={original:url,hdr:''};rendered='';label=file.name;setSource('original',false);toast('Local preview only. The workflow input is unchanged.');
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
      case 'source-original':setSource('original');break;
      case 'source-hdr':setSource('hdr');break;
      case 'fit':setZoom(1);break;
      case 'minus':setZoom(zoom-.25);break;
      case 'plus':setZoom(zoom+.25);break;
      case 'fullscreen':try{if(document.fullscreenElement)await document.exitFullscreen();else await $('.ff-main').requestFullscreen();}catch{toast('Fullscreen is unavailable in this browser.');}break;
      case 'tab-looks':setTab('looks');break;
      case 'tab-customize':setTab('customize');break;
      case 'reset':if(selectedLook){recipe=lookRecipe(selectedLook,recipe.seed);updateRecipeUI();}break;
      case 'open-file':$('.ff-file-input').click();break;
      case 'render':toast('This is the interface scaffold. Server preview rendering will be connected after your feedback.');break;
      case 'cancel':if(options.onClose)options.onClose();else {recipe=clone(startingRecipe);selectedLook=startingLook;updateRecipeUI();toast('Unsaved recipe changes discarded.');}break;
      case 'save':options.onSave?.(clone(recipe),selectedLook);startingRecipe=clone(recipe);startingLook=selectedLook;updateRecipeUI();if(!options.onSave)toast('Recipe saved for this preview session.');break;
    }
  });
  on(stage,'pointerdown',event=>{if(zoom===1||event.target.closest('.ff-wipe'))return;lastPointer={x:event.clientX,y:event.clientY,pan:{...pan}};stage.setPointerCapture(event.pointerId);});
  on(stage,'pointermove',event=>{if(!lastPointer)return;const maxX=stage.clientWidth*(zoom-1)/2,maxY=stage.clientHeight*(zoom-1)/2;pan={x:Math.max(-maxX,Math.min(maxX,lastPointer.pan.x+event.clientX-lastPointer.x)),y:Math.max(-maxY,Math.min(maxY,lastPointer.pan.y+event.clientY-lastPointer.y))};setZoom(zoom);});
  on(stage,'pointerup',()=>lastPointer=null);on(stage,'pointercancel',()=>lastPointer=null);
  on(root,'keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();options.onClose?.();return;}
    if(event.target.matches('input,select,textarea,button'))return;
    if(event.code==='Space'){event.preventDefault();play();}
    else if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();video.pause();seek(video.currentTime+(event.key==='ArrowRight'?1:-1)/fps);}
    else if(event.key.toLowerCase()==='l')action('loop').click();
  });
  updateRecipeUI();setZoom(1);setSource('original',false);compare(false);
  return {element:root, getRecipe:()=>clone(recipe), dispose(){destroyed=true;thumbnailToken++;stopTick();abort.abort();clearTimeout(toastTimer);video.pause();before.pause();video.removeAttribute('src');before.removeAttribute('src');video.load();before.load();ownedURLs.forEach(URL.revokeObjectURL);root.remove();}};
}
