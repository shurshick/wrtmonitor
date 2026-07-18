(() => {
  const journal = document.querySelector('[data-command-journal]');
  if (!journal) return;

  journal.addEventListener('click', async (event) => {
    const link = event.target.closest('[data-command-page]');
    if (!link) return;
    event.preventDefault();
    journal.classList.add('is-loading');
    try {
      const response = await fetch(link.href, { credentials: 'same-origin' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const documentCopy = new DOMParser().parseFromString(await response.text(), 'text/html');
      const nextJournal = documentCopy.querySelector('[data-command-journal]');
      if (!nextJournal) throw new Error('Command journal is missing');
      journal.replaceChildren(...nextJournal.childNodes);
      window.history.replaceState({}, '', link.href);
    } catch (_) {
      window.location.assign(link.href);
    } finally {
      journal.classList.remove('is-loading');
    }
  });
})();
