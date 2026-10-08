import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';
import { createStudio } from './viewer/studio.js';
import { baseRecipe, filmName } from './viewer/model.js';

const BASE = new URL('.', import.meta.url);
const stylesheet = document.createElement('link');
stylesheet.rel = 'stylesheet';stylesheet.href = new URL('./viewer/studio.css', BASE).href;
document.head.append(stylesheet);
const previews = new WeakMap();
let active = null;

function viewURL(file) {
  if(!file?.filename || !['temp','input','output'].includes(file.type))return '';
  const params=new URLSearchParams({filename:file.filename,subfolder:file.subfolder||'',type:file.type});
  return api.apiURL(`/view?${params}`);
}
function readRecipe(node) {
  const raw=node.widgets?.find(w=>w.name==='recipe_json')?.value;
  try {const recipe=JSON.parse(raw);if(recipe.version===2 && recipe.params && recipe.profile)return recipe;} catch {}
  return baseRecipe();
}
function openStudio(node) {
  if(active)active.close();
  const openingFocus=document.activeElement;
  const dialog=document.createElement('dialog');dialog.className='ff-dialog';dialog.setAttribute('aria-label','Fotufilm Studio');
  const media=previews.get(node)||{};
  const demo=Boolean(node.properties?.fotufilm_interface_demo);
  const fps=node.widgets?.find(w=>w.name==='fps')?.value || media.fps || 24;
  let closed=false;
  const close=()=>{if(closed)return;closed=true;studio.dispose();dialog.close();dialog.remove();active=null;openingFocus?.focus?.();};
  const studio=createStudio({
    source:viewURL(media.source)||(demo?new URL('viewer/demo/source.mp4',BASE).href:''),
    rendered:viewURL(media.rendered)||(demo?new URL('viewer/demo/rendered.mp4',BASE).href:''),
    enhanced:viewURL(media.enhanced), recipe:readRecipe(node), lookId:node.properties?.fotufilm_studio_look, fps,
    label:demo?'Courtyard study.mp4':media.source?.label||'Workflow video', onClose:close,
    onSave(recipe,lookId){
      const widget=node.widgets?.find(w=>w.name==='recipe_json');
      if(widget){widget.value=JSON.stringify(recipe);widget.callback?.(widget.value);}
      node.properties ||= {};
      node.properties.fotufilm_studio_label=filmName(recipe.stock);
      node.properties.fotufilm_studio_look=lookId;
      node._fotufilmCaption && (node._fotufilmCaption.textContent=`${filmName(recipe.stock)} · recipe saved`);
      node.setDirtyCanvas?.(true,true);app.graph?.change?.();close();
    },
  });
  dialog.append(studio.element);document.body.append(dialog);
  dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
  dialog.showModal();studio.element.querySelector('[data-action="play"]')?.focus();
  active={node,close};
}

app.registerExtension({
  name:'comfyrob.fotufilm.studio',
  async beforeRegisterNodeDef(nodeType,nodeData){
    if(nodeData.name!=='FotufilmStudio')return;
    const created=nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated=function(){
      const result=created?.apply(this,arguments);
      const recipe=this.widgets?.find(w=>w.name==='recipe_json');
      if(recipe){recipe.type='hidden';recipe.computeSize=()=>[0,-4];if(recipe.inputEl)recipe.inputEl.style.display='none';}
      const monitor=document.createElement('div');monitor.className='ff-node-monitor';
      const video=document.createElement('video');video.controls=true;video.playsInline=true;video.muted=true;video.loop=true;video.preload='metadata';
      const caption=document.createElement('div');caption.className='ff-node-caption';caption.textContent='Run once to preview the connected video';
      const open=document.createElement('button');open.type='button';open.textContent='Open studio';open.onclick=()=>{video.pause();openStudio(this);};
      monitor.append(video,caption,open);
      for(const name of ['pointerdown','wheel','keydown'])monitor.addEventListener(name,event=>event.stopPropagation());
      this._fotufilmVideo=video;this._fotufilmCaption=caption;
      this.addDOMWidget('fotufilm_studio_preview','fotufilm-preview',monitor,{serialize:false,hideOnZoom:false,getMinHeight:()=>225,getHeight:()=>225});
      this.setSize([370,360]);
      return result;
    };
    const executed=nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted=function(output){
      executed?.apply(this,arguments);
      const media=output.fotufilm_studio?.[0];if(!media)return;
      previews.set(this,media);this._fotufilmVideo.src=viewURL(media.rendered||media.source);
      this._fotufilmCaption.textContent=`${filmName(readRecipe(this).stock)} · ready to preview`;
    };
    const removed=nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved=function(){
      if(active?.node===this)active.close();this._fotufilmVideo?.pause();previews.delete(this);return removed?.apply(this,arguments);
    };
  },
  loadedGraphNode(node){
    if(node.comfyClass!=='FotufilmStudio')return;
    if(node.properties?.fotufilm_interface_demo && node._fotufilmVideo){
      node._fotufilmVideo.src=new URL('viewer/demo/source.mp4',BASE).href;
      node._fotufilmCaption.textContent='Interface preview · no generation required';
    }
  },
  commands:[{id:'fotufilm.openStudio',label:'Fotufilm: open selected studio',function(){
    const selected=Object.values(app.canvas?.selected_nodes||{}).find(n=>n.comfyClass==='FotufilmStudio');
    if(selected)openStudio(selected);
    else app.extensionManager.toast.add({severity:'info',summary:'Select a Fotufilm Studio node',detail:'Add it from Film Finish in the node menu.',life:4000});
  }}],
  getNodeMenuItems(node){return node.comfyClass==='FotufilmStudio'?[{content:'Open Fotufilm studio',callback:()=>openStudio(node)}]:[];},
});
