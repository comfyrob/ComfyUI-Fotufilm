export const ENGINE = 'f602857a031a6a9c9b0966284ff989eb3046c323';
export const films = [
  ['vision250d', 'Vision3 250D', 'Daylight negative'],
  ['vision500t', 'Vision3 500T', 'Tungsten negative'],
  ['portra400', 'Portra 400', 'Soft portrait color'],
  ['gold200', 'Gold 200', 'Warm everyday color'],
  ['cinestill800t', 'CineStill 800T', 'Night and mixed light'],
  ['ektachromee100', 'Ektachrome E100', 'Direct-view slide film'],
  ['trix400', 'Tri-X 400', 'Black and white'],
];
export const formats = [['super8', 'Super 8'], ['16mm', '16mm'], ['super35', 'Super 35'], ['35mm', '35mm'], ['120', 'Medium']];
export function neutralGrade(){return {exposure:0,temperature:0,tint:0,contrast:1,pivot:.18,shadows:0,highlights:0,saturation:1,vibrance:0,lift:[0,0,0],gamma:[1,1,1],gain:[1,1,1],offset:[0,0,0]};}
export function normalizeRecipe(recipe){return {...clone(recipe),grading:{balance:{...neutralGrade(),...recipe.grading?.balance},finish:{...neutralGrade(),...recipe.grading?.finish}}};}
export function baseRecipe() {
  return { version: 2, engine: ENGINE, stock: 'vision250d', format: 'super35', medium: 'screen', digitalReference: 'graded-print', seed: 1,
    params: { ev: 0, temperature: 6504, tint: 0, highlights: 0, shadows: 0, saturation: 1, vibrance: 0, grain: .55, gradeShadowsWarmth: 0, gradeHighlightsWarmth: 0 },
    profile: { halation: 0, screenGrade: 2, screenExposure: 0 },grading:{balance:neutralGrade(),finish:neutralGrade()} };
}
export const looks = [
  { id: 'clean', name: 'Clean cinema', note: 'Quiet color, fine texture', film: 'vision250d', params: {} },
  { id: 'warm', name: 'Warm portrait', note: 'Soft light, warm skin', film: 'portra400', params: {temperature: 7000, grain: .65}, profile: {screenGrade: 1.7} },
  { id: 'night', name: 'Night lights', note: 'Tungsten, luminous highlights', film: 'vision500t', params: {temperature: 5900, saturation: .95}, profile: {halation: .6} },
  { id: 'eight', name: 'Super 8 diary', note: 'Warm color, visible grain', film: 'gold200', format: 'super8', params: {temperature: 7100, saturation: .9, grain: .85}, profile: {screenGrade: 1.65, halation: -.5} },
  { id: 'slide', name: 'Daylight slide', note: 'Ektachrome, open highlights', film: 'ektachromee100', reference: 'reference-exposure', params: {} },
  { id: 'silver', name: 'Silver screen', note: 'Silver grain, bold contrast', film: 'trix400', format: '16mm', params: {grain: .8}, profile: {screenGrade: 2.5} },
  { id: 'golden', name: 'Golden hour', note: 'Sunlit warmth, soft contrast', film: 'gold200', params: {temperature: 7400, gradeHighlightsWarmth: .2, grain: .65}, profile: {screenGrade: 1.8} },
  { id: 'print', name: 'Cinema print', note: '250D negative, 2383 print', film: 'vision250d', medium: 'vision-2383', params: {saturation: 1.05, grain: .6} },
  { id: 'pastel', name: 'Pastel portrait', note: 'Gentle contrast, soft color', film:'portra400',params:{grain:.35},grading:{finish:{contrast:.87,saturation:.9}} },
  { id: 'neon', name: 'Neon nights', note: 'Cool shadows, luminous color', film:'cinestill800t',profile:{halation:.7},grading:{finish:{lift:[-.008,0,.014],saturation:1.12}} },
  { id: 'editorial', name: 'Cool editorial', note: 'Clean detail, restrained color',film:'vision250d',params:{grain:.35},grading:{finish:{temperature:-.08,contrast:1.08,saturation:.85}} },
  { id: 'noir',name:'Midnight noir',note:'Deep blacks, silver texture',film:'trix400',profile:{screenGrade:2.5},grading:{finish:{contrast:1.12,shadows:-.15}} },
];
export function lookRecipe(id, seed = 1) {
  const look = looks.find(x => x.id === id) || looks[0];
  const recipe = baseRecipe();
  return { ...recipe, seed, stock: look.film, format: look.format || recipe.format, medium: look.medium || recipe.medium,
    digitalReference: look.reference || recipe.digitalReference, params: {...recipe.params, ...look.params}, profile: {...recipe.profile, ...look.profile},
    grading:{balance:{...neutralGrade(),...look.grading?.balance},finish:{...neutralGrade(),...look.grading?.finish}} };
}
export const clone = value => JSON.parse(JSON.stringify(value));
export const filmName = id => films.find(f => f[0] === id)?.[1] || id;
export function sameRecipe(a, b) {
  const normalize = value => JSON.stringify([value.stock, value.format, value.medium, value.digitalReference,
    ...Object.keys(baseRecipe().params).map(k => value.params[k]), ...Object.keys(baseRecipe().profile).map(k => value.profile[k]),
    ...['balance','finish'].flatMap(stage=>Object.keys(neutralGrade()).map(k=>value.grading?.[stage]?.[k]??neutralGrade()[k]))]);
  return normalize(a) === normalize(b);
}
export function matchLook(recipe) { return looks.find(look => sameRecipe(lookRecipe(look.id), recipe)); }
export function timecode(seconds, fps = 24) {
  const time = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
  const whole = Math.floor(time + .00001);
  const frame = Math.min(Math.ceil(fps)-1, Math.max(0, Math.floor((time-whole)*fps+.001)));
  return `${String(Math.floor(whole / 60)).padStart(2, '0')}:${String(whole % 60).padStart(2, '0')}:${String(frame).padStart(2, '0')}`;
}
