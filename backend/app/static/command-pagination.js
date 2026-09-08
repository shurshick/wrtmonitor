(() => {
  const journal = document.querySelector('[data-command-journal]');
  if (!journal) return;

  journal.addEventListener('click', async (event) => {
    const link = event.target.closest('[data-command-page]');
    if (!link) return;
    event.preventDefault();
    const targetUrl = link.href;
    window.history.replaceState({}, '', targetUrl);
    journal.classList.add('is-loading');
    try {
      const response = await fetch(targetUrl, { credentials: 'same-origin' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const documentCopy = new DOMParser().parseFromString(await response.text(), 'text/html');
      const nextJournal = documentCopy.querySelector('[data-command-journal]');
      if (!nextJournal) throw new Error('Command journal is missing');
      journal.replaceChildren(...nextJournal.childNodes);
    } catch (_) {
      window.location.reload();
    } finally {
      journal.classList.remove('is-loading');
    }
  });
})();
