import { useEffect } from 'react';

const ORIGIN = 'https://itrbharo.duckdns.org';

interface SeoOptions {
  /** Page title. " | ITR Bharo" is appended unless the title already carries the brand. */
  title: string;
  description: string;
  /** Path only, e.g. "/login". Combined with the canonical origin. */
  path: string;
  /** Keep authenticated / thin pages out of the index. */
  noindex?: boolean;
}

function setMeta(selector: string, attr: 'name' | 'property', key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(selector);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

/**
 * Keeps the document head in step with the active route.
 *
 * The app is a client-rendered SPA, so every route is served the same static
 * index.html. Without this, Google would index each URL with the homepage's
 * title and description, which reads as duplicate content. Googlebot renders
 * JavaScript, so updating the head after mount is picked up on the render pass.
 */
export function useSeo({ title, description, path, noindex = false }: SeoOptions): void {
  useEffect(() => {
    const fullTitle = title.includes('ITR Bharo') ? title : `${title} | ITR Bharo`;
    const url = `${ORIGIN}${path}`;

    document.title = fullTitle;

    setMeta('meta[name="description"]', 'name', 'description', description);
    setMeta('meta[property="og:title"]', 'property', 'og:title', fullTitle);
    setMeta('meta[property="og:description"]', 'property', 'og:description', description);
    setMeta('meta[property="og:url"]', 'property', 'og:url', url);
    setMeta('meta[name="twitter:title"]', 'name', 'twitter:title', fullTitle);
    setMeta('meta[name="twitter:description"]', 'name', 'twitter:description', description);

    setMeta(
      'meta[name="robots"]',
      'name',
      'robots',
      noindex ? 'noindex, nofollow' : 'index, follow',
    );

    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement('link');
      canonical.rel = 'canonical';
      document.head.appendChild(canonical);
    }
    canonical.href = url;
  }, [title, description, path, noindex]);
}
