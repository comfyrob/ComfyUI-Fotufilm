// Keep graph/API recipes identical to the Studio defaults.
import {readFile, writeFile} from 'node:fs/promises';
import {looks, lookGroups, lookRecipe} from '../web/viewer/model.js';
const path = new URL('../examples/studio-looks.json', import.meta.url);
const catalogue = looks.map(look=>({id:look.id,name:look.name,description:look.note,
  family:lookGroups.slice(1).find(group=>group[2].includes(look.id))[1],recipe:lookRecipe(look.id)}));
const text = JSON.stringify(catalogue,null,2)+'\n';
if(process.argv.includes('--check')){
  if(await readFile(path,'utf8')!==text)throw new Error('Run node scripts/export_looks.mjs to refresh graph recipes.');
}else await writeFile(path,text);
