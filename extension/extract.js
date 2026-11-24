// Chrome serializes this function into the tab's isolated world.
export function extractArticle() {
  const EXCLUDED = 'nav, aside, footer, script, style, template, noscript, [hidden], [aria-hidden="true"], [role="navigation"], [role="complementary"]';
  function visible(element) {
    if (element.closest(EXCLUDED) || !element.getClientRects().length
        || getComputedStyle(element).visibility !== 'visible') return false;
    for (let current = element; current; current = current.parentElement) {
      if (getComputedStyle(current).contentVisibility === 'hidden') return false;
    }
    return true;
  }

  const article = [...document.querySelectorAll('article, [itemprop="articleBody"]')].find(visible);
  const main = article ? null : [...document.querySelectorAll('main, [role="main"]')].find(visible);
  const scope = article ?? main ?? document.body;

  function cleanText(element) {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (node.nodeType === Node.TEXT_NODE) {
          return getComputedStyle(node.parentElement).visibility === 'visible'
            ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
        }
        const style = getComputedStyle(node);
        if (node.matches(EXCLUDED) || style.display === 'none' || style.contentVisibility === 'hidden') {
          return NodeFilter.FILTER_REJECT;
        }
        if (node.matches('br') && style.visibility === 'visible') return NodeFilter.FILTER_ACCEPT;
        return NodeFilter.FILTER_SKIP;
      },
    });
    const text = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      text.push(node.nodeType === Node.TEXT_NODE ? node.data : ' ');
    }
    return text.join('').replace(/\s+/gu, ' ').trim();
  }

  const metaTitle = document.querySelector('meta[property="og:title"]')?.content;
  const heading = article?.querySelector('h1') ?? document.querySelector('h1');
  const title = (metaTitle?.trim() || (heading && visible(heading) && cleanText(heading))
    || document.title.trim()).slice(0, 4096);
  const blocks = [...(scope?.querySelectorAll('p, h2, h3, blockquote') ?? [])];
  const paragraphs = [];
  let textLength = 0;
  for (const block of blocks) {
    if (!visible(block) || (block.matches('blockquote') && block.querySelector('p'))) continue;
    const text = cleanText(block);
    if (!text) continue;
    paragraphs.push(text.slice(0, 100002 - textLength));
    textLength += paragraphs.at(-1).length + 2;
    if (textLength >= 100002) break;
  }
  const text = paragraphs.join('\n\n');
  const candidates = new Map();

  function addImage(value, label) {
    if (!value?.trim() || candidates.size >= 12) return;
    try {
      const url = new URL(value, document.baseURI);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return;
      if (url.href.length <= 2048 && !candidates.has(url.href)) {
        candidates.set(url.href, { url: url.href, label: label?.trim().slice(0, 160) || '' });
      }
    } catch {
      // Invalid URLs are ignored.
    }
  }

  for (const meta of document.querySelectorAll('meta[property="og:image"], meta[name="twitter:image"]')) {
    addImage(meta.content, 'Ảnh đại diện của trang');
  }
  for (const image of scope?.querySelectorAll('img') ?? []) {
    if (visible(image) && !((image.naturalWidth || image.width) < 32 && (image.naturalHeight || image.height) < 32
        && image.complete && image.naturalWidth > 0)) {
      addImage(image.currentSrc || image.getAttribute('data-src') || image.getAttribute('src'), image.alt);
    }
    if (candidates.size === 12) break;
  }

  return {
    url: location.href,
    title,
    text,
    candidateImages: [...candidates.values()],
    extraction: text ? 'dom' : 'empty',
  };
}
