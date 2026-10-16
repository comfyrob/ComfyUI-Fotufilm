import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import fs from 'node:fs';
import {createRequire} from 'node:module';
import {baseRecipe,filmName} from '../web/viewer/model.js';
import {composeGrade,gradeOverrides} from '../web/viewer/stage-recipe.js';
const {JSDOM}=createRequire(import.meta.url)('jsdom');

for (const [filmType,gradeType] of [['FotufilmFilmStudio','FotufilmColorGrade'],['FotufilmFilmEditor','FotufilmGradeEditor']])
test(`${filmType} propagates live film changes and commits both connected nodes for queued export`,()=>{
  const dom=new JSDOM('<body></body>',{url:'https://comfy.test'}),editors=[],nodes=[];let extension,poll;
  for(const key of ['pause','load'])dom.window.HTMLMediaElement.prototype[key]=function(){};
  const app={graph:{change(){},getNodeById:id=>nodes.find(n=>n.id===id)},registerExtension:e=>extension=e};
  const context={app,api:{addEventListener(){},apiURL:x=>x},baseRecipe,filmName,composeGrade,gradeOverrides,
    URL,console,document:dom.window.document,setInterval:fn=>poll=fn,
    createPreviewClient:()=>({register:async()=>({asset:'one',info:{}}),dispose(){}}),
    createStudio:options=>{
      let recipe=options.recipe;
      const editor={options,element:dom.window.document.createElement('div'),getRecipe:()=>recipe,getLookId:()=>null,dispose(){},updateMedia(){},setAsset(){},
        setBaseRecipe:base=>{recipe=composeGrade(base,gradeOverrides(options.baseRecipe||baseRecipe(),recipe));options.baseRecipe=base;options.onChange(recipe);},
        edit:value=>{recipe=value;options.onChange(recipe);},save:()=>options.onSave(recipe,null)};
      editors.push(editor);return editor;
    }};
  let code=fs.readFileSync(new URL('../web/fotufilm_studio.js',import.meta.url),'utf8');
  code=code.replace(/^import .*;\n/gm,'').replaceAll('import.meta.url',JSON.stringify(new URL('../web/fotufilm_studio.js',import.meta.url).href));
  vm.runInNewContext(code,context);
  function node(id,type,parent){
    const n={id,comfyClass:type,graph:app.graph,properties:{fotufilm_studio_expanded:true},widgets:[{name:'recipe_json',value:JSON.stringify(baseRecipe())},{name:'adjustments_json',value:'{}'}],inputs:[{name:'recipe_json'}],getInputNode:()=>parent,setSize(){},setDirtyCanvas(){},addDOMWidget:()=>({})};
    nodes.push(n);extension.nodeCreated(n);extension.loadedGraphNode(n);return n;
  }
  const film=node(1,filmType),grade=node(2,gradeType,film);
  const f=editors[0],g=editors[1];
  const adjusted=g.getRecipe();adjusted.grading.finish.exposure=.5;g.edit(adjusted);
  const newLook=baseRecipe();newLook.stock='portra400';newLook.grading.finish.saturation=.8;f.edit(newLook);
  assert.equal(g.getRecipe().stock,'portra400');assert.equal(g.getRecipe().grading.finish.exposure,.5);
  assert.equal(g.getRecipe().grading.finish.saturation,.8);
  g.save();
  assert.equal(JSON.parse(film.widgets[0].value).stock,'portra400');
  assert.deepEqual(JSON.parse(grade.widgets[1].value),{exposure:.5});
  assert.equal(composeGrade(JSON.parse(film.widgets[0].value),JSON.parse(grade.widgets[1].value)).grading.finish.saturation,.8);
  poll();
});
