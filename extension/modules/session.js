export const SESSION_VERSION = 1;

export function sessionKey(sessionId) {
  return 'analysis:' + sessionId;
}

export async function readSession(search, storage = chrome.storage.session) {
  const id = new URLSearchParams(search).get('session');
  if (!id || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/u.test(id)) return null;
  const key = sessionKey(id);
  const session = (await storage.get(key))[key];
  return session?.version === SESSION_VERSION && session.id === id ? session : null;
}
