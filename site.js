/* Shared header for every page. Edit THIS file to change the app's title, subtitle, page titles or menu.
   Each page just has <header id="site-header"></header>, loads site.css + site.js, and calls
   SiteHeader.render('<page id>'). To add a page, add an entry to SITE.pages. */
const SITE = {
  title: 'Metal Buy-Day Tracker',
  subtitle: 'from Metal Stores',
  pages: [
    { id: 'overview', label: 'Overview', href: 'index.html',  pageTitle: 'Metal Buy-Day Tracker' },
    { id: 'stores',   label: 'By store', href: 'stores.html', pageTitle: 'Metal Prices by Store' }
  ]
};

const SiteHeader = {
  render(activeId) {
    const host = document.getElementById('site-header');
    const page = SITE.pages.find(p => p.id === activeId) || SITE.pages[0];
    document.title = page.pageTitle;

    const h1 = document.createElement('h1');
    h1.append(SITE.title);
    if (SITE.subtitle) {
      const sub = document.createElement('span');
      sub.className = 'muted';
      sub.textContent = ' ' + SITE.subtitle;
      h1.appendChild(sub);
    }
    const nav = document.createElement('nav');
    SITE.pages.forEach(p => {
      const a = document.createElement('a');
      a.href = p.href; a.textContent = p.label; a.dataset.page = p.id;
      if (p.id === page.id) a.className = 'on';
      nav.appendChild(a);
    });
    host.replaceChildren(h1, nav);
  },

  /* Keep the chosen metal (gold / silver) when moving between pages. */
  setMetal(metal) {
    document.querySelectorAll('#site-header nav a').forEach(a => {
      const p = SITE.pages.find(x => x.id === a.dataset.page);
      if (p) a.href = p.href + '?metal=' + encodeURIComponent(metal);
    });
  }
};
