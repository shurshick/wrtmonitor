(() => {
  const source = document.getElementById('wifi-radio-data');
  const form = document.querySelector('[data-wifi-radio-form]');
  if (!source || !form) return;

  const radios = JSON.parse(source.textContent || '[]');
  const select = form.querySelector('[data-wifi-radio-select]');
  const channel = form.querySelector('[data-wifi-field="channel"]');
  const htmode = form.querySelector('[data-wifi-field="htmode"]');
  const country = form.querySelector('[data-wifi-field="country"]');
  const txpower = form.querySelector('[data-wifi-field="txpower"]');
  const current = form.querySelector('[data-wifi-radio-current]');
  const channelsByBand = {
    '2g': ['auto', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13'],
    '5g': ['auto', '36', '40', '44', '48', '52', '56', '60', '64', '100', '104', '108', '112', '116', '120', '124', '128', '132', '136', '140', '144', '149', '153', '157', '161', '165'],
    '6g': ['auto', '1', '5', '9', '13', '17', '21', '25', '29', '33', '37', '41', '45', '49', '53', '57', '61', '65', '69', '73', '77', '81', '85', '89', '93', '97', '101', '105', '109', '113', '117', '121', '125', '129', '133', '137', '141', '145', '149', '153', '157', '161', '165', '169', '173', '177', '181', '185', '189', '193', '197', '201', '205', '209', '213', '217', '221', '225', '229', '233'],
  };

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
    const band = String(radio.band || '').toLowerCase();
    const options = channelsByBand[band] || ['auto'];
    channel.replaceChildren(...options.map((value) => new Option(value === 'auto' ? 'Автоматически' : value, value)));
    setSelectValue(channel, radio.channel || 'auto');
    setSelectValue(htmode, radio.htmode || '');
    setSelectValue(country, radio.country || '');
    txpower.value = radio.txpower == null ? '' : radio.txpower;
    current.textContent = `${radio.name || radio.id} · ${radio.band || 'Wi-Fi'} · канал ${radio.channel || 'авто'} · ${radio.htmode || 'авто'}`;
  };

  select.addEventListener('change', renderRadio);
  renderRadio();
})();
