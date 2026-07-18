(() => {
  const list = document.querySelector('[data-client-list]');
  if (!list) return;

  const rows = [...list.querySelectorAll('.client-list-row')];
  const buttons = [...document.querySelectorAll('[data-client-filter]')];
  const search = document.querySelector('[data-client-search]');
  const empty = list.querySelector('[data-client-empty]');
  let filter = 'all';

  const applyFilter = () => {
    const query = (search?.value || '').trim().toLocaleLowerCase('ru');
    let visible = 0;
    rows.forEach((row) => {
      const online = row.dataset.clientOnline === 'true';
      const stateMatches = filter === 'all' || (filter === 'online' && online) || (filter === 'offline' && !online);
      const searchMatches = !query || (row.dataset.clientSearchValue || '').includes(query);
      row.hidden = !(stateMatches && searchMatches);
      if (!row.hidden) visible += 1;
    });
    if (empty) empty.hidden = visible !== 0;
  };

  buttons.forEach((button) => {
    button.addEventListener('click', () => {
      filter = button.dataset.clientFilter || 'all';
      buttons.forEach((item) => {
        const active = item === button;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      applyFilter();
    });
  });
  search?.addEventListener('input', applyFilter);

  rows.forEach((row) => {
    row.addEventListener('toggle', () => {
      if (!row.open) return;
      rows.forEach((item) => {
        if (item !== row) item.open = false;
      });
    });
  });
})();
