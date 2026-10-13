/** One thumbnail batch per source/recipe set, independent of playback updates. */
export function createLookPreviews({render, show, status, delay = 120, cache = new Map()}) {
  let key = '', timer = 0, controller = null, disposed = false, latest = null;
  const ready = cache;
  async function run() {
    timer = 0;
    if (!latest || disposed) return;
    const batch = latest, current = new AbortController();
    controller = current;
    let failures = 0;
    for (const item of batch.items) {
      if (current.signal.aborted || disposed) return;
      const itemKey = JSON.stringify([batch.asset, item.recipe]);
      try {
        status(item.id, 'loading');
        const url = ready.get(itemKey) || (await render(batch.asset, item.recipe, {
          frame: 0, edge: 384, channel: 'looks', signal: current.signal,
        })).after;
        if (current.signal.aborted || disposed) return;
        await show(item.id, url, current.signal);
        if (current.signal.aborted || disposed) return;
        ready.set(itemKey, url);
        while (ready.size > 48) ready.delete(ready.keys().next().value);
        status(item.id, 'ready');
      } catch (error) {
        if (current.signal.aborted || disposed) return;
        // A superseded server job or failed image is retryable, not a silent exit.
        ready.delete(itemKey); failures++;
        status(item.id, 'error');
      }
    }
    if (controller === current) { controller = null; status(null, failures ? 'error' : 'ready'); }
  }
  return {
    update(asset, items, force = false) {
      if (disposed) return;
      const nextKey = JSON.stringify([asset, items]);
      if (!force && key === nextKey) return;
      controller?.abort(); clearTimeout(timer); key = nextKey;
      latest = {asset, items};
      status(null, 'loading');
      timer = setTimeout(run, delay);
    },
    cancel() { controller?.abort(); clearTimeout(timer); timer = 0; key = ''; },
    dispose() { disposed = true; this.cancel(); },
  };
}
