import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';
import { createStudio } from './viewer/studio.js';
import { baseRecipe, filmName } from './viewer/model.js';
import { createPreviewClient } from './viewer/preview-client.js';

const BASE = new URL('.', import.meta.url);
const stylesheet = document.createElement('link');
stylesheet.rel='stylesheet';stylesheet.href=new URL('viewer/studio.css',BASE).href;document.head.append(stylesheet);
const states=new Map();
const returns=new Map();
let active=null;
const knownOutputs=new Map();
function locatorId(node){return node.graph===app.graph?String(node.id):`${node.graph?.id}:${node.id}`;}
function inputNode(node,name){
  const slot=node.inputs?.findIndex(x=>x.name===name);if(slot==null||slot<0)return null;
  let source=node.getInputNode?.(slot),link=node.getInputLink?.(slot);const visited=new Set();
  while(source?.isSubgraphNode?.()){
    if(!link||visited.has(source))return null;visited.add(source);
    const resolved=source.resolveSubgraphOutputLink?.(link.origin_slot);if(!resolved)return null;
    source=resolved.outputNode;link=resolved.link;
  }
  return source;
}
function fileWidget(node){
  const raw=node?.widgets?.find(w=>w.name==='file'||w.name==='video')?.value;
  if(typeof raw!=='string'||!raw||raw==='Loading...')return null;
  const match=raw.match(/^(.*?)(?:\s*\[(input|output|temp)\])?$/),path=match[1].replaceAll('\\','/'),index=path.lastIndexOf('/');
  return {filename:path.slice(index+1),subfolder:index<0?'':path.slice(0,index),type:match[2]||'input',label:path.slice(index+1)};
}
function outputFile(node,master=false){
  if(!node)return null;
  const output=knownOutputs.get(locatorId(node))||app.nodeOutputs?.[locatorId(node)];
  return [...(output?.files||[]),...(output?.gifs||[]),...(output?.images||[])].find(f=>master?f.filename?.endsWith('.ffhdr.zip'):/\.(mp4|webm|mov|m4v)$/i.test(f.filename||''));
}
async function registerSource(node,mode){
  const state=states.get(node);if(!state||state.demo)return;
  const file=mode==='hdr'?state.media?.master:state.media?.source;
  if(!file)return;
  const key=JSON.stringify(file);state.sourceMode=mode;
  if(state.assetKeys[mode]===key&&state.assets[mode]){
    state.editor?.setAsset(state.assets[mode]);if(active?.node===node)active.editor.setAsset(state.assets[mode]);return;
  }
  state.assetKeys[mode]=key;
  try{
    const asset=await state.preview.register(file);
    if(state.assetKeys[mode]!==key||!states.has(node))return;
    state.assets[mode]=asset;
    if(asset.playback&&!state.media?.source){setMedia(node,{...state.media,source:asset.playback});}
    if(state.sourceMode===mode){state.editor?.setAsset(asset);if(active?.node===node)active.editor.setAsset(asset);}
    state.caption.textContent=asset.info.hdr?'HDR master ready · Gear + Fotufilm':'Source ready · automatic film preview';
  }catch(error){state.assetKeys[mode]=null;state.caption.textContent=error.message;}
}
function discoverSource(node){
  const state=states.get(node);if(!state||state.demo)return;
  const upstream=inputNode(node,'video');
  const source=(upstream?.comfyClass==='LoadVideo'?fileWidget(upstream):outputFile(upstream));
  const key=JSON.stringify(source);
  if(source&&key!==state.discoveredKey){
    if(state.discoveredKey){state.masterKey=JSON.stringify(outputFile(inputNode(node,'master'),true));}
    state.discoveredKey=key;state.assets={};state.assetKeys={};state.sourceMode='original';state.media=null;
    setMedia(node,{source});registerSource(node,'original');
  }
  const masterNode=inputNode(node,'master');
  const master=masterNode?.comfyClass==='FotufilmLoadHDRMaster'?fileWidget(masterNode):outputFile(masterNode,true);
  if(master&&JSON.stringify(master)!==state.masterKey){
    state.masterKey=JSON.stringify(master);state.media={...state.media,master};const options=mediaOptions(node);state.editor?.updateMedia(options);if(active?.node===node)active.editor.updateMedia(options);registerSource(node,'hdr');
  }
}
function viewURL(file){
  if(!file?.filename||!['temp','input','output'].includes(file.type))return '';
  return api.apiURL(`/view?${new URLSearchParams({filename:file.filename,subfolder:file.subfolder||'',type:file.type})}`);
}
function readRecipe(node){
  try{const recipe=JSON.parse(node.widgets?.find(w=>w.name==='recipe_json')?.value);if(recipe.version===2&&recipe.params&&recipe.profile)return recipe;}catch{}
  return baseRecipe();
}
function saveRecipe(node,recipe,lookId){
  const widget=node.widgets?.find(w=>w.name==='recipe_json');
  if(widget){widget.value=JSON.stringify(recipe);widget.callback?.(widget.value);}
  node.properties||={};node.properties.fotufilm_studio_look=lookId;
  const state=states.get(node);if(state)state.caption.textContent=`${filmName(recipe.stock)} · recipe saved`;
  node.setDirtyCanvas?.(true,true);app.graph?.change?.();
}
function mediaOptions(node){
  const media=states.get(node)?.media||{},demo=Boolean(node.properties?.fotufilm_interface_demo);
  return {source:viewURL(media.source)||(demo?new URL('viewer/demo/source.mp4',BASE).href:''),
    rendered:viewURL(media.rendered)||(demo?new URL('viewer/demo/rendered.mp4',BASE).href:''),enhanced:viewURL(media.enhanced),
    hasHDR:Boolean(media.master),renderedRecipe:media.rendered_recipe,recipe:readRecipe(node),lookId:node.properties?.fotufilm_studio_look,
    fps:media.fps||node.widgets?.find(w=>w.name==='fps')?.value||24,
    asset:states.get(node)?.assets?.[states.get(node)?.sourceMode],
    label:demo?'Courtyard study.mp4':media.source?.label||'Workflow video'};
}
function makeEditor(node,onClose,initial={}){
  const state=states.get(node);
  return createStudio({...mediaOptions(node),...initial,onClose,onSave:(recipe,look)=>saveRecipe(node,recipe,look),
    preview:state.demo?null:state.preview,
    onSourceMode:mode=>{if(state.sourceMode!==mode)registerSource(node,mode);},
    onUpload:async file=>{
      const upstream=inputNode(node,'video');if(upstream?.comfyClass!=='LoadVideo')throw new Error('Connect Load Video to Studio to replace its input.');
      const form=new FormData();form.append('image',file);form.append('type','input');form.append('overwrite','false');
      const response=await api.fetchApi('/upload/image',{method:'POST',body:form});if(!response.ok)throw new Error('Video upload failed.');
      const info=await response.json(),widget=upstream.widgets?.find(w=>w.name==='file');if(!widget)throw new Error('Load Video file widget unavailable.');
      widget.value=[info.subfolder,info.name].filter(Boolean).join('/');widget.callback?.(widget.value);upstream.setDirtyCanvas?.(true,true);discoverSource(node);
    },
    onRender:node.properties?.fotufilm_interface_demo?null:async(recipe,look)=>{
      saveRecipe(node,recipe,look);
      // Explicit user action: run the connected graph on this ComfyUI server.
      await app.queuePrompt(0,1);
    }});
}
function openStudio(node){
  active?.close();const state=states.get(node);state?.video.pause();
  const initial=state?.editor?{recipe:state.editor.getRecipe(),lookId:state.editor.getLookId()}:{};
  state?.editor?.dispose();if(state)state.editor=null;
  const focus=document.activeElement,dialog=document.createElement('dialog');dialog.className='ff-dialog';dialog.setAttribute('aria-label','Fotufilm Studio');
  let closed=false;
  const close=()=>{if(closed)return;closed=true;editor.dispose();dialog.close();dialog.remove();active=null;if(state?.expanded)expandStudio(node,true,false);focus?.focus?.();};
  const editor=makeEditor(node,close,initial);dialog.append(editor.element);document.body.append(dialog);dialog.addEventListener('cancel',event=>{event.preventDefault();close();});dialog.showModal();
  active={node,editor,close};
}
function expandStudio(node,expanded,resize=true){
  const state=states.get(node);if(!state)return;
  state.editor?.dispose();state.editor=null;state.video.pause();state.expanded=expanded;
  node.properties||={};node.properties.fotufilm_studio_expanded=expanded;
  state.monitor.classList.toggle('ff-node-expanded',expanded);state.compact.hidden=expanded;
  state.monitor.style.height=expanded?'645px':'250px';
  state.monitor.style.maxHeight=state.monitor.style.height;
  state.expand.textContent=expanded?'Collapse editor':'Edit in node';state.expand.setAttribute('aria-expanded',String(expanded));
  if(expanded){state.editor=makeEditor(node,()=>expandStudio(node,false));state.host.append(state.editor.element);}
  state.host.hidden=!expanded;
  if(resize)node.setSize(expanded?[1100,850]:[390,420]);
  node.setDirtyCanvas?.(true,true);
}
function setMedia(node,media){
  const state=states.get(node);if(!state)return;
  const old=state.media;
  const sameSource=old?.source?.filename===media.source?.filename&&old?.source?.type===media.source?.type&&old?.source?.subfolder===media.source?.subfolder;
  state.media={...(sameSource?old:{}),...media,...returns.get(media.token)};
  const current=state.media,url=viewURL(current.rendered||current.source);
  if(url&&state.video.getAttribute('src')!==url)state.video.src=url;
  state.caption.textContent=current.rendered?'Render returned · ready to review':'Source ready · choose your film recipe';
  if(old?.rendered?.filename!==current.rendered?.filename||old?.source?.filename!==current.source?.filename){
    const options=mediaOptions(node);state.editor?.updateMedia(options);if(active?.node===node)active.editor.updateMedia(options);
  }
}
function handleOutput(node,output){
  if(node)knownOutputs.set(locatorId(node),output);
  const media=output?.fotufilm_studio?.[0];if(media&&node)setMedia(node,media);
  if(media?.master&&node)registerSource(node,'hdr');
  const review=output?.fotufilm_review?.[0];
  if(review){returns.set(review.token,review);if(returns.size>100)returns.delete(returns.keys().next().value);for(const [target,state] of states)if(state.media?.token===review.token)setMedia(target,state.media);}
}
function executionNode(path){
  let graph=app.graph,node;for(const part of String(path).split(':')){node=graph?.getNodeById(part);graph=node?.subgraph;}return node;
}
api.addEventListener('executed',event=>handleOutput(executionNode(event.detail.node),event.detail.output));
// The core video editor resolves an upstream file widget / cached output rather
// than executing its producer. Recheck lightweight values while Studio exists.
setInterval(()=>{for(const [node] of states)discoverSource(node);},750);
app.registerExtension({
  name:'comfyrob.fotufilm.studio',
  nodeCreated(node){
    if(node.comfyClass!=='FotufilmStudio'||states.has(node))return;
    const recipe=node.widgets?.find(w=>w.name==='recipe_json');if(recipe)recipe.hidden=true;
    const monitor=document.createElement('div');monitor.className='ff-node-monitor';
    const compact=document.createElement('div');compact.className='ff-node-compact';
    const video=document.createElement('video');video.controls=true;video.playsInline=true;video.muted=true;video.loop=true;video.preload='metadata';
    const caption=document.createElement('div');caption.className='ff-node-caption';caption.textContent='Connect Load Video or a completed HDR master';compact.append(video,caption);
    const toolbar=document.createElement('div');toolbar.className='ff-node-toolbar';
    const expand=document.createElement('button');expand.type='button';expand.textContent='Edit in node';expand.setAttribute('aria-expanded','false');
    const open=document.createElement('button');open.type='button';open.textContent='Open studio ↗';open.onclick=()=>openStudio(node);
    const host=document.createElement('div');host.className='ff-node-editor';host.hidden=true;toolbar.append(expand,open);monitor.append(compact,toolbar,host);
    for(const name of ['pointerdown','pointermove','pointerup','mousedown','mousemove','mouseup','dblclick','wheel','keydown','click'])monitor.addEventListener(name,event=>event.stopPropagation());
    const state={monitor,compact,video,caption,host,expand,expanded:false,editor:null,media:null,assets:{},assetKeys:{},sourceMode:'original',preview:createPreviewClient(api),demo:false};states.set(node,state);
    expand.onclick=()=>expandStudio(node,!state.expanded);
    const widget=node.addDOMWidget('fotufilm_studio_preview','fotufilm-preview',monitor,{serialize:false,hideOnZoom:false,
      getMinHeight:()=>state.expanded?620:250,getHeight:()=>state.expanded?645:250});
    widget.onRemove=()=>{if(active?.node===node)active.close();state.editor?.dispose();state.preview.dispose();video.pause();video.removeAttribute('src');video.load();states.delete(node);};
    node.setSize([390,420]);
  },
  loadedGraphNode(node){
    const state=states.get(node);if(!state)return;
    state.demo=Boolean(node.properties?.fotufilm_interface_demo);
    if(state.demo){state.video.src=new URL('viewer/demo/source.mp4',BASE).href;state.caption.textContent='Interface preview · no generation required';}
    if(node.properties?.fotufilm_studio_expanded)expandStudio(node,true,false);
    discoverSource(node);
  },
  onNodeOutputsUpdated(outputs){
    for(const [id,output] of Object.entries(outputs))knownOutputs.set(id,output);
    // History uses graph-scoped locator IDs; execution events use path IDs.
    for(const [node] of states){const id=node.graph===app.graph?String(node.id):`${node.graph?.id}:${node.id}`;handleOutput(node,outputs[id]);}
    for(const output of Object.values(outputs))if(output?.fotufilm_review)handleOutput(null,output);
  },
  commands:[{id:'fotufilm.openStudio',label:'Fotufilm: open selected studio',function(){
    const node=Object.values(app.canvas?.selected_nodes||{}).find(n=>n.comfyClass==='FotufilmStudio');
    if(node)openStudio(node);else app.extensionManager.toast.add({severity:'info',summary:'Select a Fotufilm Studio node',life:4000});
  }}],
  getNodeMenuItems(node){return node.comfyClass==='FotufilmStudio'?[{content:'Open Fotufilm studio',callback:()=>openStudio(node)},{content:'Expand film editor in node',callback:()=>expandStudio(node,true)}]:[];},
});
