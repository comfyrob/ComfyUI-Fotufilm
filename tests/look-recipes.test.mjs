import assert from 'node:assert/strict';
import test from 'node:test';
import {looks, lookGroups, lookRecipe, selectLook, baseRecipe} from '../web/viewer/model.js';

test('editing a look never changes its defaults or a separate editor',()=>{
  for(const look of looks){
    const original=lookRecipe(look.id);
    const edited=selectLook(baseRecipe(),look.id);
    edited.grading.finish.lift[0]=.99;
    edited.grading.finish.gamma[1]=1.5;
    edited.params.grain=0;
    assert.deepEqual(lookRecipe(look.id),original,look.id);
  }
});

test('every look can be found in exactly one named family',()=>{
  const ids=looks.map(look=>look.id),grouped=lookGroups.slice(1).flatMap(group=>group[2]);
  assert.equal(new Set(ids).size,ids.length);
  assert.deepEqual([...grouped].sort(),[...ids].sort());
});
