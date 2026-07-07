"""JavaScript snippets used by the BofA Private Bank scraper.

These are kept in a separate module to keep the main scraper file within pylint
module-size limits while preserving the exact browser-evaluation behavior.
"""

LISTING_TILES_EVAL_JS = """
() => {
    const results = [];
    const tiles = Array.from(document.querySelectorAll('a.tile__link'));

    tiles.forEach(tile => {
        const url = tile.href;
        // Avoid non-article links or external redirects
        if (!url || !url.includes('/articles/')) return;

        // Title: normally in an h3
        const h3 = tile.querySelector('h3');
        const title = h3 ? h3.innerText.trim() : '';

        // Blurb: normally in a p
        const p = tile.querySelector('p');
        const blurb = p ? p.innerText.trim() : '';

        // Date: Try to find a date pattern in the tile text
        // e.g. "February 23, 2026"
        const text = tile.innerText || '';
        const dateMatch = text.match(
            /\\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\\w]*\\s+\\d{1,2},\\s+\\d{4}\\b/
        );
        const date = dateMatch ? dateMatch[0] : null;

        results.push({ url, title, blurb, date });
    });

    // De-duplicate by URL
    const seen = new Set();
    return results.filter(r => {
        if (seen.has(r.url)) return false;
        seen.add(r.url);
        return true;
    });
}
"""

ARTICLE_CONTENT_EVAL_JS = """
() => {
    const data = {};

    // Title — BofA nav has an h1 containing "Menu"; skip headings
    // inside <nav> or <header>. Prefer the first h1 in <main>.
    const mainEl = document.querySelector('main') ||
                   document.querySelector('[role="main"]');
    const mainH1 = mainEl
        ? mainEl.querySelector('h1')
        : null;

    if (mainH1) {
        data.title = mainH1.innerText.trim();
    } else {
        // Fall back to document.title (e.g. "Capital Market Outlook")
        data.title = document.title
            .split('|')[0]   // strip site name suffix if present
            .replace(/\\s+/g, ' ')
            .trim();
    }

    // Meta description / summary
    const metaDesc =
        document.querySelector('meta[name="description"]') ||
        document.querySelector('meta[property="og:description"]');
    data.summary = metaDesc ? metaDesc.content.trim() : '';

    // Published date from meta tags (BofA may omit these)
    const metaDate =
        document.querySelector('meta[property="article:published_time"]') ||
        document.querySelector('meta[name="date"]') ||
        document.querySelector('time[datetime]');
    data.published_date = metaDate
        ? (metaDate.content || metaDate.getAttribute('datetime') || null)
        : null;

    // PDF link — only search inside the main article body so
    // footer and privacy links are ignored.
    const pdfAnchor = (mainEl || document).querySelector(
        'a[href*=".pdf"], a[href*="/content/dam/"]'
    );
    data.pdf_url = pdfAnchor ? pdfAnchor.href : null;

    // Body text — prefer <main>, strip boilerplate
    const bodyContainer =
        document.querySelector('main') ||
        document.querySelector('article') ||
        document.querySelector('[role="main"]') ||
        document.body;

    const clone = bodyContainer.cloneNode(true);
    clone.querySelectorAll(
        'script, style, nav, footer, header, ' +
        '.site-footer, .site-header, .breadcrumb, ' +
        '.related-insights, .cta-section'
    ).forEach(el => el.remove());

    data.content = clone.innerText.trim();
    data.word_count = data.content
        ? data.content.split(/\\s+/).length
        : 0;

    // Author — BofA CMO articles have no individual byline
    const metaAuthor = document.querySelector('meta[name="author"]');
    data.author = metaAuthor ? metaAuthor.content.trim() : null;

    return data;
}
"""
