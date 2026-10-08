import { createStudio } from './studio.js';

const target = document.getElementById('fotufilm-preview');
if (target) {
  const demo = new URLSearchParams(location.search).has('demo');
  const studio = createStudio({
    source: demo ? new URL('./demo/source.mp4',import.meta.url).href : '',
    rendered: demo ? new URL('./demo/rendered.mp4',import.meta.url).href : '',
    label: demo ? 'Courtyard study.mp4' : 'Preview clip', fps:24,
  });
  target.append(studio.element);
  window.addEventListener('pagehide',()=>studio.dispose(),{once:true});
}
