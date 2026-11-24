export function createFormState(initial = {}) {
  let draft = { title: initial.title ?? '', text: initial.text ?? '', image: initial.image ?? null };
  const listeners = new Set();

  return {
    get() { return { ...draft }; },
    set(patch) {
      const next = { ...draft };
      for (const field of Object.keys(draft)) {
        if (Object.hasOwn(patch, field)) next[field] = patch[field];
      }
      if (Object.keys(draft).every(field => draft[field] === next[field])) return;
      draft = next;
      for (const listener of listeners) listener({ ...draft });
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
