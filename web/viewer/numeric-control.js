/** Exact recipe values, with an uncommitted text buffer while typing. */
export function attachNumericControl(range, {on, commit}) {
  const output = range.closest('.ff-slider').querySelector('output');
  const editor = document.createElement('input');
  editor.type = 'number'; editor.className = 'ff-number';
  for (const key of ['min','max','step']) editor[key] = range[key];
  editor.setAttribute('aria-label', `${range.getAttribute('aria-label')} value${range.dataset.unit || ''}`);
  const unit = document.createElement('span'); unit.className = 'ff-unit';
  unit.textContent = range.dataset.unit || '';
  output.replaceChildren(editor, unit);
  const sync = () => {editor.value = Number(range.value).toFixed(Number(range.dataset.digits || 0));};
  const apply = () => {
    const number = editor.value.trim() === '' ? NaN : Number(editor.value);
    if (!Number.isFinite(number)) {sync(); return;}
    const min = Number(range.min), max = Number(range.max), step = Number(range.step);
    const value = Number(Math.max(min, Math.min(max, min + Math.round((number-min)/step)*step)).toFixed(8));
    if (value !== Number(range.value)) commit(value);
    sync();
  };
  on(editor, 'blur', apply);
  on(editor, 'keydown', event => {
    // Escape cancels the field, never the entire ComfyUI dialog.
    if (event.key === 'Escape') {event.preventDefault();event.stopPropagation();sync();editor.blur();}
    else if (event.key === 'Enter') {event.preventDefault();event.stopPropagation();apply();editor.blur();}
    else if (['ArrowUp','ArrowDown'].includes(event.key)) {
      event.preventDefault();event.stopPropagation();
      const base = Number.isFinite(editor.valueAsNumber) ? editor.valueAsNumber : Number(range.value);
      editor.value = String(base + (event.key === 'ArrowUp' ? 1 : -1)*Number(range.step)*(event.shiftKey ? 10 : 1));
      apply();
    }
  });
  sync();
  return {sync: () => {if (document.activeElement !== editor) sync();}};
}
