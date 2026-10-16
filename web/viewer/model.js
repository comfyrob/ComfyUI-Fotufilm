import {ENGINE, films, looks, lookGroups} from './catalogue.js';
export {ENGINE, films, looks, lookGroups, stockMetadata, CATALOGUE_VERSION} from './catalogue.js';
export const formats = [['super8', 'Super 8'], ['16mm', '16mm'], ['super35', 'Super 35'], ['35mm', '35mm'], ['120', 'Medium']];
export function neutralGrade(){return {exposure:0,temperature:0,tint:0,contrast:1,pivot:.18,shadows:0,highlights:0,saturation:1,vibrance:0,lift:[0,0,0],gamma:[1,1,1],gain:[1,1,1],offset:[0,0,0]};}
export function normalizeRecipe(recipe){return {...clone(recipe),grading:{balance:{...neutralGrade(),...recipe.grading?.balance},finish:{...neutralGrade(),...recipe.grading?.finish}}};}
export function baseRecipe() {
  return { version: 2, engine: ENGINE, stock: 'vision250d', format: 'super35', medium: 'screen', digitalReference: 'graded-print', seed: 1,
    params: { ev: 0, temperature: 6504, tint: 0, highlights: 0, shadows: 0, saturation: 1, vibrance: 0, grain: .55, gradeShadowsWarmth: 0, gradeHighlightsWarmth: 0 },
    profile: { halation: 0, screenGrade: 2, screenExposure: 0 },grading:{balance:neutralGrade(),finish:neutralGrade()} };
}
export function looksInGroup(id) {
  const ids = (lookGroups.find(group=>group[0]===id) || lookGroups[0])[2];
  return looks.filter(look=>ids.includes(look.id));
}
export function lookRecipe(id, seed = 1) {
  const look = looks.find(x => x.id === id) || looks[0];
  const recipe = baseRecipe();
  return { ...recipe, seed, stock: look.film, format: look.format || recipe.format, medium: look.medium || recipe.medium,
    digitalReference: look.reference || recipe.digitalReference, params: {...recipe.params, ...look.params}, profile: {...recipe.profile, ...look.profile},
    grading:{balance:{...neutralGrade(),...clone(look.grading?.balance || {})},finish:{...neutralGrade(),...clone(look.grading?.finish || {})}} };
}
// Source correction belongs to the clip. The optional finish override replaces
// the entire after-film grade; it does not add/multiply preset wheel vectors.
export function selectLook(current, id, keepFinish = false) {
  const next = lookRecipe(id, current.seed);
  if(current.sdr_output)next.sdr_output=current.sdr_output;
  next.grading.balance = clone(current.grading.balance);
  if (keepFinish) next.grading.finish = clone(current.grading.finish);
  return next;
}
export const clone = value => JSON.parse(JSON.stringify(value));
export const filmName = id => films.find(f => f[0] === id)?.[1] || id;
export function sameRecipe(a, b) {
  const normalize = value => JSON.stringify([value.stock, value.format, value.medium, value.digitalReference, value.sdr_output||'legacy',
    ...Object.keys(baseRecipe().params).map(k => value.params[k]), ...Object.keys(baseRecipe().profile).map(k => value.profile[k]),
    ...['balance','finish'].flatMap(stage=>Object.keys(neutralGrade()).map(k=>value.grading?.[stage]?.[k]??neutralGrade()[k]))]);
  return normalize(a) === normalize(b);
}
export function matchLook(recipe) { return looks.find(look => sameRecipe(selectLook(normalizeRecipe(recipe),look.id), recipe)); }
export function timecode(seconds, fps = 24) {
  const time = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
  const whole = Math.floor(time + .00001);
  const frame = Math.min(Math.ceil(fps)-1, Math.max(0, Math.floor((time-whole)*fps+.001)));
  return `${String(Math.floor(whole / 60)).padStart(2, '0')}:${String(whole % 60).padStart(2, '0')}:${String(frame).padStart(2, '0')}`;
}
