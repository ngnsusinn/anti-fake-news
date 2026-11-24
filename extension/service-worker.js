import { extractArticle } from './extract.js';
import { SESSION_VERSION, sessionKey } from './modules/session.js';

function sourceUrl(value) {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    url.username = '';
    url.password = '';
    return url.href;
  } catch {
    return null;
  }
}

async function openAnalysis(tab) {
  const id = crypto.randomUUID();
  const key = sessionKey(id);
  const url = sourceUrl(tab.url);
  const session = {
    version: SESSION_VERSION,
    id,
    tabId: tab.id ?? null,
    url,
    title: '',
    text: '',
    candidateImages: [],
    extraction: 'unavailable',
  };

  if (url && Number.isInteger(tab.id)) {
    try {
      const [injection] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extractArticle,
      });
      const article = injection?.result;
      if (article && sourceUrl(article.url) === url) {
        const { title, text, candidateImages, extraction } = article;
        Object.assign(session, { title, text, candidateImages, extraction });
      }
    } catch {
      // Restricted pages and closed or navigated tabs use manual entry.
    }
  }

  let stored = false;
  try {
    await chrome.storage.session.set({ [key]: session });
    stored = true;
  } catch {
    // The analysis page can continue with manual entry if storage is unavailable.
  }
  const page = new URL(chrome.runtime.getURL('analyze.html'));
  if (stored) page.searchParams.set('session', id);
  try {
    const analysisTab = await chrome.tabs.create({ url: page.href });
    if (!stored) return;
    if (!Number.isInteger(analysisTab.id)) {
      await chrome.storage.session.remove(key);
      return;
    }
    // Keep ownership in session storage so removal works after worker suspension.
    await chrome.storage.session.set({ ['analysis-tab:' + analysisTab.id]: key });
    try {
      await chrome.tabs.get(analysisTab.id);
    } catch {
      await removeAnalysis(analysisTab.id);
    }
  } catch {
    if (stored) await chrome.storage.session.remove(key);
  }
}

async function removeAnalysis(tabId) {
  const ownerKey = 'analysis-tab:' + tabId;
  const key = (await chrome.storage.session.get(ownerKey))[ownerKey];
  if (key) await chrome.storage.session.remove([ownerKey, key]);
}

chrome.action.onClicked.addListener(tab => openAnalysis(tab).catch(() => {}));
chrome.tabs.onRemoved.addListener(tabId => removeAnalysis(tabId).catch(() => {}));
