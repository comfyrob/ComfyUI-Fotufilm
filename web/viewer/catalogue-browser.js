import {looks, lookGroups, filmName, stockMetadata} from './model.js';

const FAVORITES_KEY = 'fotufilm.favorite-looks.v1';
export function readFavorites(storage) {
  try {
    const value = JSON.parse(storage.getItem(FAVORITES_KEY) || '[]');
    return new Set(Array.isArray(value) ? value.filter(id => looks.some(look => look.id === id)) : []);
  } catch { return new Set(); }
}
export function writeFavorites(storage, favorites) {
  try { storage.setItem(FAVORITES_KEY, JSON.stringify([...favorites])); } catch { /* Session-only when storage is unavailable. */ }
}
export function filterLooks({group = 'all', query = '', favorites = new Set(), favoritesOnly = false} = {}) {
  const ids = new Set((lookGroups.find(entry => entry[0] === group) || lookGroups[0])[2]);
  const words = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return looks.filter(look => {
    const family = lookGroups.slice(1).find(entry => entry[2].includes(look.id))?.[1] || '';
    const text = `${look.name} ${look.note} ${filmName(look.film)} ${family} ${stockMetadata[look.film]?.kind || ''}`.toLocaleLowerCase();
    return ids.has(look.id) && (!favoritesOnly || favorites.has(look.id)) && words.every(word => text.includes(word));
  });
}

/** Only cards in the scroll viewport (plus the pinned selection) need native work. */
export function previewLooks(entries, visibleIds, selectedId, isAvailable) {
  const ids = new Set(visibleIds);
  const selected = looks.find(look => look.id === selectedId);
  return [...(selected ? [selected] : []), ...entries.filter(look => ids.has(look.id) && look !== selected)]
    .filter(look => isAvailable(look.film));
}
