(() => {
  const journal = document.querySelector('[data-command-journal]');
  if (!journal) return;

  let revision = 0;
  let controller;
  let pending;
  let pointerDown = false;
  let navigating = false;
  let refreshQueued = false;
  const applyPending = () => {
    if (!pending || pointerDown || (!pending.navigation && journal.querySelector('[data-command-page]:hover'))) return;
    const update = pending;
    pending = null;
    if (update.revision === revision && update.url === window.location.href) {
      journal.replaceChildren(...update.journal.childNodes);
    }
  };
  const refresh = async (url, navigation = false) => {
    if (!navigation && navigating) {
      refreshQueued = true;
      return;
    }
    controller?.abort();
    controller = new AbortController();
    const current = ++revision;
    pending = null;
    navigating = navigation;
    if (navigation) journal.classList.add('is-loading');
    try {
      const response = await fetch(url, { credentials: 'same-origin', signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const documentCopy = new DOMParser().parseFromString(await response.text(), 'text/html');
      const nextJournal = documentCopy.querySelector('[data-command-journal]');
      if (!nextJournal) throw new Error('Command journal is missing');
      if (current !== revision || url !== window.location.href) return;
      pending = { revision: current, url, journal: nextJournal, navigation };
      applyPending();
    } catch (error) {
      if (error.name !== 'AbortError' && navigation && current === revision) window.location.reload();
    } finally {
      if (current === revision) {
        navigating = false;
        journal.classList.remove('is-loading');
        if (refreshQueued) {
          refreshQueued = false;
          refresh(window.location.href);
        }
      }
    }
  };

  journal.addEventListener('pointerdown', () => { pointerDown = true; });
  window.addEventListener('pointerup', () => {
    pointerDown = false;
    window.setTimeout(applyPending, 0);
  });
  window.addEventListener('pointercancel', () => { pointerDown = false; applyPending(); });
  journal.addEventListener('pointerout', () => window.setTimeout(applyPending, 0));
  window.addEventListener('wrtmonitor:journal-refresh', () => refresh(window.location.href));
  window.addEventListener('popstate', () => refresh(window.location.href, true));

  journal.addEventListener('click', (event) => {
    const link = event.target.closest('[data-command-page]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const targetUrl = link.href;
    window.history.replaceState({}, '', targetUrl);
    refresh(targetUrl, true);
  });
  journal.dataset.paginationReady = 'true';
})();
