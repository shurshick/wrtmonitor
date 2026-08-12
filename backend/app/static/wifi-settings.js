(() => {
  document.querySelectorAll('[data-wifi-qr]').forEach((button) => {
    button.addEventListener('click', async () => {
      const original = button.textContent;
      button.disabled = true;
      button.textContent = 'Получение…';
      const body = new FormData();
      body.set('iface', button.dataset.iface || '');
      body.set('csrf_token', button.dataset.csrf || '');
      try {
        const response = await fetch(`/devices/${button.dataset.deviceId}/wifi-qr.svg`, {
          method: 'POST', body, credentials: 'same-origin', cache: 'no-store',
        });
        if (!response.ok) throw new Error(await response.text());
        const url = URL.createObjectURL(await response.blob());
        const dialog = document.createElement('dialog');
        dialog.className = 'wifi-qr-dialog';
        dialog.innerHTML = `<div class="wifi-qr-dialog__content"><h2>Подключение к Wi-Fi</h2><img alt="QR-код Wi-Fi"><p>Отсканируйте камерой телефона. Пароль не сохраняется на сервере.</p><button type="button">Закрыть</button></div>`;
        dialog.querySelector('img').src = url;
        dialog.querySelector('button').addEventListener('click', () => dialog.close());
        dialog.addEventListener('close', () => { URL.revokeObjectURL(url); dialog.remove(); });
        document.body.append(dialog);
        dialog.showModal();
      } catch (_) {
        window.alert('Не удалось получить QR-код с роутера. Обновите данные и повторите попытку.');
      } finally {
        button.disabled = false;
        button.textContent = original;
      }
    });
  });

  const source = document.getElementById('wifi-radio-data');
  const form = document.querySelector('[data-wifi-radio-form]');
  if (!source || !form) return;

  const radios = JSON.parse(source.textContent || '[]');
  const select = form.querySelector('[data-wifi-radio-select]');
  const enabled = form.querySelector('[data-wifi-field="enabled"]');
  const channel = form.querySelector('[data-wifi-field="channel"]');
  const htmode = form.querySelector('[data-wifi-field="htmode"]');
  const country = form.querySelector('[data-wifi-field="country"]');
  const txpower = form.querySelector('[data-wifi-field="txpower"]');
  const current = form.querySelector('[data-wifi-radio-current]');

  const setSelectValue = (element, value) => {
    if (!element) return;
    const normalized = value == null ? '' : String(value);
    if (normalized && !Array.from(element.options).some((item) => item.value === normalized)) {
      element.add(new Option(`${normalized} (текущее)`, normalized));
    }
    element.value = normalized;
  };

  const renderRadio = () => {
    const radio = radios.find((item) => String(item.id) === select.value) || radios[0];
    if (!radio) return;
    const options = Array.isArray(radio.supported_channels) && radio.supported_channels.length
      ? radio.supported_channels.map(String)
      : [String(radio.channel || 'auto')];
    channel.replaceChildren(...options.map((value) => new Option(value === 'auto' ? 'Автоматически' : value, value)));
    setSelectValue(channel, radio.channel || 'auto');
    setSelectValue(enabled, radio.configured_enabled === false ? 'false' : 'true');
    setSelectValue(htmode, radio.htmode || '');
    setSelectValue(country, radio.country || '');
    txpower.value = radio.txpower == null ? '' : radio.txpower;
    const runtime = radio.runtime && radio.runtime.state ? radio.runtime.state : 'нет runtime';
    current.textContent = `${radio.name || radio.id} · ${radio.band || 'Wi-Fi'} · ${runtime} · канал ${radio.channel || 'авто'} · ${radio.htmode || 'авто'}`;
  };

  select.addEventListener('change', renderRadio);
  renderRadio();
})();
