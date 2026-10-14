import {clone,normalizeRecipe} from './model.js';

export function composeGrade(base, adjustments={}) {
  const recipe=normalizeRecipe(base);
  for(const [key,value] of Object.entries(adjustments)) {
    if(!(key in recipe.grading.finish))throw new Error(`Unknown grade control: ${key}`);
    recipe.grading.finish[key]=clone(value);
  }
  return recipe;
}
export function gradeOverrides(base,current) {
  const defaults=normalizeRecipe(base).grading.finish;
  return Object.fromEntries(Object.entries(current.grading.finish).filter(([k,v])=>JSON.stringify(v)!==JSON.stringify(defaults[k])).map(([k,v])=>[k,clone(v)]));
}
