(() => {
  let refreshTimer = 0;
  let refreshInFlight = false;

  const openSections = () => Array.from(
    document.querySelectorAll('[data-package-card] details[open]'),
    (details) => details.querySelector('summary')?.textContent?.trim() || '',
  );

  const showStatus = (message, error = false) => {
    const status = document.querySelector('[data-package-status]');
    if (!status) return;
    status.hidden = false;
    status.textContent = message;
    status.classList.toggle('notice--danger', error);
  };

  const refreshCard = async () => {
    if (refreshInFlight) return;
    const currentCard = document.querySelector('[data-package-card]');
    if (!currentCard) return;
    refreshInFlight = true;
    const expanded = openSections();
    try {
      const response = await fetch(window.location.href, { credentials: 'same-origin' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const copy = new DOMParser().parseFromString(await response.text(), 'text/html');
      const nextCard = copy.querySelector('[data-package-card]');
      if (!nextCard) throw new Error('Package card is missing');
      nextCard.querySelectorAll('details').forEach((details) => {
        const label = details.querySelector('summary')?.textContent?.trim() || '';
        if (expanded.some((value) => value && label.startsWith(value.replace(/\s*\(\d+\)$/, '')))) {
          details.open = true;
        }
      });
      currentCard.replaceWith(nextCard);
    } catch (_) {
      showStatus('Не удалось обновить список пакетов. Обновите страницу вручную.', true);
    } finally {
      refreshInFlight = false;
    }
  };

  const scheduleRefresh = (delay = 250) => {
    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(refreshCard, delay);
  };

  document.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-package-upgrade-form]');
    if (!form) return;
    event.preventDefault();
    const packageName = form.dataset.packageName || 'пакет';
    if (!window.confirm(`Обновить пакет ${packageName}?`)) return;
    const button = form.querySelector('button[type="submit"]');
    if (button) {
      button.disabled = true;
      button.textContent = 'В очереди…';
    }
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      showStatus(`Обновление ${packageName} поставлено в очередь.`);
      scheduleRefresh(800);
    } catch (_) {
      showStatus(`Не удалось поставить обновление ${packageName} в очередь.`, true);
      if (button) {
        button.disabled = false;
        button.textContent = 'Обновить';
      }
    }
  });

  window.addEventListener('wrtmonitor:command', () => scheduleRefresh(350));
  window.addEventListener('wrtmonitor:telemetry', () => scheduleRefresh(250));
})();
