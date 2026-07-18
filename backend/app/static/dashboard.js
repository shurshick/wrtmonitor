(() => {
  const monitor = document.querySelector('[data-live-monitor]');
  const canvas = document.getElementById('traffic-chart');
  const source = document.getElementById('dashboard-history');
  if (!monitor || !canvas || !source) return;

  let points = JSON.parse(source.textContent || '[]');
  let rangeName = 'live';
  let loadedRange = 'live';
  let chartMetric = 'traffic';
  let requestSerial = 0;
  const context = canvas.getContext('2d');
  const empty = monitor.querySelector('[data-chart-empty]');
  const state = monitor.querySelector('[data-chart-state]');
  const yAxis = [...monitor.querySelectorAll('[data-chart-y]')];
  const xAxis = [...monitor.querySelectorAll('[data-chart-x]')];
  const legend = monitor.querySelector('[data-chart-legend]');
  const rangeLabels = { live: '2 часа', '24h': '24 часа', '7d': '7 дней', '30d': '30 дней' };

  const formatRate = (value, compact = false) => {
    const rate = Number(value) || 0;
    if (rate >= 1_000_000_000) return `${(rate / 1_000_000_000).toFixed(compact ? 1 : 2)} ${compact ? 'Г' : 'Гбит/с'}`;
    if (rate >= 1_000_000) return `${(rate / 1_000_000).toFixed(compact ? 1 : 2)} ${compact ? 'М' : 'Мбит/с'}`;
    if (rate >= 1_000) return `${(rate / 1_000).toFixed(compact ? 0 : 1)} ${compact ? 'к' : 'кбит/с'}`;
    return `${Math.round(rate)}${compact ? '' : ' бит/с'}`;
  };

  const niceMaximum = (value) => {
    if (!Number.isFinite(value) || value <= 0) return 1;
    const exponent = Math.floor(Math.log10(value));
    const magnitude = 10 ** exponent;
    const fraction = value / magnitude;
    const rounded = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
    return rounded * magnitude;
  };

  const metricSeries = () => {
    if (chartMetric === 'load') return [{ label: 'Нагрузка', key: 'load_1m', color: '#f2ae4a' }];
    if (chartMetric === 'memory') return [{ label: 'Память', key: 'memory_percent', color: '#63df9b' }];
    if (chartMetric === 'clients') return [{ label: 'Клиенты', key: 'client_count', color: '#42d3e8' }];
    return [
      { label: 'Приём', key: 'rx_bps', color: '#42d3e8' },
      { label: 'Передача', key: 'tx_bps', color: '#63df9b' },
    ];
  };

  const formatMetric = (value, compact = false) => {
    const numeric = Number(value) || 0;
    if (chartMetric === 'traffic') return formatRate(numeric, compact);
    if (chartMetric === 'memory') return `${Math.round(numeric)}%`;
    if (chartMetric === 'clients') return `${Math.round(numeric)}`;
    return numeric.toFixed(compact ? 1 : 2);
  };

  const formatTime = (value, range = loadedRange) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    if (range === 'live' || range === '24h') {
      return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
  };

  const formatCoverageTime = (value) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  };

  const drawLine = (items, key, color, width, height, maximum) => {
    context.beginPath();
    items.forEach((point, index) => {
      const x = (index / Math.max(1, items.length - 1)) * width;
      const y = height - ((Number(point[key]) || 0) / maximum) * height;
      if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
    });
    context.strokeStyle = color;
    context.lineWidth = 2;
    context.lineJoin = 'round';
    context.lineCap = 'round';
    context.stroke();
  };

  const renderChart = () => {
    const items = points;
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    const width = Math.max(240, Math.round(rect.width));
    const height = Math.max(150, Math.round(rect.height));
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    empty.hidden = items.length >= 2;
    if (items.length < 2) return;

    const series = metricSeries();
    const observedMaximum = Math.max(0, ...items.flatMap((point) => series.map((item) => Number(point[item.key]) || 0)));
    const maximum = chartMetric === 'memory' ? 100 : niceMaximum(observedMaximum);
    context.strokeStyle = 'rgba(133, 157, 184, .18)';
    context.lineWidth = 1;
    for (let row = 0; row < 4; row += 1) {
      const y = row * (height / 3);
      context.beginPath(); context.moveTo(0, y); context.lineTo(width, y); context.stroke();
    }
    for (let column = 0; column < 3; column += 1) {
      const x = column * (width / 2);
      context.beginPath(); context.moveTo(x, 0); context.lineTo(x, height); context.stroke();
    }
    series.forEach((item) => drawLine(items, item.key, item.color, width, height, maximum));

    yAxis.forEach((label, index) => { label.textContent = formatMetric(maximum * (3 - index) / 3, true); });
    const timePoints = [items[0], items[Math.floor(items.length / 2)], items[items.length - 1]];
    xAxis.forEach((label, index) => { label.textContent = formatTime(timePoints[index]?.created_at); });
    legend.replaceChildren(...series.map((item) => {
      const row = document.createElement('span');
      const marker = document.createElement('i');
      const value = document.createElement('strong');
      marker.style.setProperty('--series-color', item.color);
      row.append(marker, `${item.label}: `);
      value.textContent = formatMetric(items[items.length - 1]?.[item.key] || 0);
      row.append(value);
      return row;
    }));
  };

  const renderValues = () => {
    const last = points[points.length - 1];
    if (!last) return;
    document.querySelector('[data-live-rx]').textContent = formatRate(last.rx_bps);
    document.querySelector('[data-live-tx]').textContent = formatRate(last.tx_bps);
    document.querySelector('[data-live-load]').textContent = Number(last.load_1m || 0).toFixed(2);
    document.querySelector('[data-live-memory]').textContent = `${Math.round(last.memory_percent || 0)}%`;
    document.querySelector('[data-live-clients]').textContent = last.client_count || 0;
    document.querySelector('[data-live-samples]').textContent = `${points.length} точек`;
    const coverage = document.querySelector('[data-chart-coverage]');
    if (coverage) {
      coverage.textContent = `${rangeLabels[loadedRange]} · ${formatCoverageTime(points[0]?.created_at)} — ${formatCoverageTime(last.created_at)}`;
    }
    const gauge = document.querySelector('.resource-gauge');
    if (gauge) gauge.style.setProperty('--value', Math.min(100, last.memory_percent || 0));
    const loadGauge = document.querySelector('.resource-gauge--load');
    if (loadGauge) loadGauge.style.setProperty('--value', Math.min(100, (last.load_1m || 0) * 25));
  };

  const render = () => { renderValues(); renderChart(); };

  const loadRange = async (requestedRange) => {
    const serial = ++requestSerial;
    monitor.classList.add('is-chart-loading');
    monitor.setAttribute('aria-busy', 'true');
    if (state) state.textContent = `Загрузка: ${rangeLabels[requestedRange]}`;
    try {
      const response = await fetch(`${monitor.dataset.endpoint}?range=${encodeURIComponent(requestedRange)}`, { credentials: 'same-origin' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (serial !== requestSerial) return;
      points = data.points || [];
      loadedRange = requestedRange;
      monitor.dataset.loadedRange = requestedRange;
      if (state) state.textContent = `Загружено: ${rangeLabels[loadedRange]}`;
      render();
    } catch (error) {
      if (serial === requestSerial && state) state.textContent = `Не удалось загрузить ${rangeLabels[requestedRange]}`;
      throw error;
    } finally {
      if (serial === requestSerial) {
        monitor.classList.remove('is-chart-loading');
        monitor.removeAttribute('aria-busy');
      }
    }
  };

  monitor.querySelectorAll('[data-chart-range]').forEach((button) => {
    button.addEventListener('click', async () => {
      rangeName = button.dataset.chartRange || 'live';
      monitor.querySelectorAll('[data-chart-range]').forEach((item) => item.classList.toggle('is-active', item === button));
      try { await loadRange(rangeName); } catch (_) { /* Keep the last valid range and explain the error. */ }
    });
  });

  monitor.querySelectorAll('[data-chart-metric]').forEach((button) => {
    button.addEventListener('click', () => {
      chartMetric = button.dataset.chartMetric || 'traffic';
      monitor.querySelectorAll('[data-chart-metric]').forEach((item) => item.classList.toggle('is-active', item === button));
      renderChart();
    });
  });

  const poll = async () => {
    if (!document.hidden && rangeName === 'live') {
      try {
        await loadRange('live');
        const updated = document.querySelector('[data-live-updated]');
        if (updated && points.length) updated.textContent = 'только что';
      } catch (_) {
        // The last valid snapshot remains visible while the connection recovers.
      }
    }
    window.setTimeout(poll, 5000);
  };

  monitor.dataset.loadedRange = loadedRange;
  if (state) state.textContent = `Загружено: ${rangeLabels[loadedRange]}`;
  new ResizeObserver(renderChart).observe(canvas);
  render();
  window.setTimeout(poll, 5000);
})();
