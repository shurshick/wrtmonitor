(() => {
  const root = document.querySelector('[data-device-events]');
  if (!root || !window.EventSource) return;

  let journalTimer = 0;
  const refreshJournal = () => {
    const journal = document.querySelector('[data-command-journal]');
    if (!journal) return;
    window.clearTimeout(journalTimer);
    journalTimer = window.setTimeout(async () => {
      try {
        const response = await fetch(window.location.href, { credentials: 'same-origin' });
        if (!response.ok) return;
        const documentCopy = new DOMParser().parseFromString(await response.text(), 'text/html');
        const nextJournal = documentCopy.querySelector('[data-command-journal]');
        if (nextJournal) journal.replaceChildren(...nextJournal.childNodes);
      } catch (_) {
        // Periodic and manual refresh remain available while SSE reconnects.
      }
    }, 120);
  };

  const source = new EventSource(root.dataset.deviceEvents, { withCredentials: true });
  ['snapshot', 'telemetry.updated', 'resync_required'].forEach((name) => {
    source.addEventListener(name, (event) => {
      window.dispatchEvent(new CustomEvent('wrtmonitor:telemetry', { detail: event.data }));
    });
  });
  ['command.queued', 'command.status'].forEach((name) => {
    source.addEventListener(name, (event) => {
      refreshJournal();
      window.dispatchEvent(new CustomEvent('wrtmonitor:command', { detail: event.data }));
    });
  });
  source.onerror = () => root.dataset.realtimeState = 'reconnecting';
  source.onopen = () => root.dataset.realtimeState = 'connected';
  window.addEventListener('beforeunload', () => source.close(), { once: true });
})();
