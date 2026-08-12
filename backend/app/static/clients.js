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
      const presence = row.dataset.clientPresence || 'offline';
      const stateMatches = filter === 'all' || filter === presence;
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
    const form = row.querySelector('.client-policy-form');
    const preset = form?.querySelector('[data-client-preset]');
    const description = form?.querySelector('[data-client-preset-description]');
    preset?.addEventListener('change', () => {
      const option = preset.selectedOptions[0];
      if (!option?.dataset.policy) return;
      const policy = JSON.parse(option.dataset.policy);
      const setValue = (name, value) => {
        const field = form.querySelector(`[name="${name}"]`);
        if (field) field.value = String(value ?? '');
      };
      form.querySelector('[name="blocked"]').checked = Boolean(policy.blocked);
      form.querySelector('[name="schedule_enabled"]').checked = Boolean(policy.schedule.enabled);
      form.querySelectorAll('[name="weekdays"]').forEach((field) => {
        field.checked = policy.schedule.weekdays.includes(field.value);
      });
      setValue('start', policy.schedule.start);
      setValue('stop', policy.schedule.stop);
      setValue('priority', policy.qos.priority);
      setValue('download_kbps', policy.qos.download_kbps);
      setValue('upload_kbps', policy.qos.upload_kbps);
      setValue('dns_provider', policy.dns.provider);
      setValue('profile_id', '');
      if (description) description.textContent = option.dataset.description || '';
    });
  });
})();
