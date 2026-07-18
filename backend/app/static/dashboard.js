(() => {
  const monitor = document.querySelector('[data-live-monitor]');
  const canvas = document.getElementById('traffic-chart');
  const source = document.getElementById('dashboard-history');
  if (!monitor || !canvas || !source) return;

  let points = JSON.parse(source.textContent || '[]');
  let rangeName = 'live';
  const context = canvas.getContext('2d');
  const empty = monitor.querySelector('[data-chart-empty]');

  const formatRate = (value) => {
    const rate = Number(value) || 0;
    if (rate >= 1_000_000_000) return `${(rate / 1_000_000_000).toFixed(2)} Гбит/с`;
    if (rate >= 1_000_000) return `${(rate / 1_000_000).toFixed(2)} Мбит/с`;
    if (rate >= 1_000) return `${(rate / 1_000).toFixed(1)} кбит/с`;
    return `${Math.round(rate)} бит/с`;
  };

  const visiblePoints = () => points;

  const drawLine = (items, key, color, width, height, padding, maximum) => {
    context.beginPath();
    items.forEach((point, index) => {
      const x = padding + (index / Math.max(1, items.length - 1)) * (width - padding * 2);
      const y = height - padding - ((Number(point[key]) || 0) / maximum) * (height - padding * 2);
      if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
    });
    context.strokeStyle = color;
    context.lineWidth = 2;
    context.lineJoin = 'round';
    context.lineCap = 'round';
    context.stroke();
  };

  const renderChart = () => {
    const items = visiblePoints();
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    const width = Math.max(320, Math.round(rect.width));
    const height = Math.max(170, Math.round(rect.height));
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    empty.hidden = items.length >= 2;
    if (items.length < 2) return;

    const padding = 16;
    const maximum = Math.max(1, ...items.flatMap((point) => [Number(point.rx_bps) || 0, Number(point.tx_bps) || 0]));
    context.strokeStyle = 'rgba(133, 157, 184, .16)';
    context.lineWidth = 1;
    for (let row = 0; row < 4; row += 1) {
      const y = padding + row * ((height - padding * 2) / 3);
      context.beginPath();
      context.moveTo(padding, y);
      context.lineTo(width - padding, y);
      context.stroke();
    }
    drawLine(items, 'rx_bps', '#42d3e8', width, height, padding, maximum);
    drawLine(items, 'tx_bps', '#63df9b', width, height, padding, maximum);
  };

  const renderValues = () => {
    const last = points[points.length - 1];
    if (!last) return;
    document.querySelector('[data-live-rx]').textContent = formatRate(last.rx_bps);
    document.querySelector('[data-live-tx]').textContent = formatRate(last.tx_bps);
    document.querySelector('[data-live-load]').textContent = Number(last.load_1m || 0).toFixed(2);
    document.querySelector('[data-live-memory]').textContent = `${Math.round(last.memory_percent || 0)}%`;
    document.querySelector('[data-live-clients]').textContent = last.client_count || 0;
    document.querySelector('[data-live-samples]').textContent = `${visiblePoints().length} точек`;
    const gauge = document.querySelector('.resource-gauge');
    if (gauge) gauge.style.setProperty('--value', Math.min(100, last.memory_percent || 0));
    const loadGauge = document.querySelector('.resource-gauge--load');
    if (loadGauge) loadGauge.style.setProperty('--value', Math.min(100, (last.load_1m || 0) * 25));
  };

  const render = () => { renderValues(); renderChart(); };
  const loadRange = async () => {
    const response = await fetch(`${monitor.dataset.endpoint}?range=${encodeURIComponent(rangeName)}`, { credentials: 'same-origin' });
    if (!response.ok) return;
    const data = await response.json();
    points = data.points || [];
    render();
  };

  document.querySelectorAll('[data-chart-range]').forEach((button) => {
    button.addEventListener('click', async () => {
      rangeName = button.dataset.chartRange || 'live';
      document.querySelectorAll('[data-chart-range]').forEach((item) => item.classList.toggle('is-active', item === button));
      try { await loadRange(); } catch (_) { /* Keep the last valid range. */ }
    });
  });

  const poll = async () => {
    if (!document.hidden && rangeName === 'live') {
      try {
        await loadRange();
        const updated = document.querySelector('[data-live-updated]');
        if (updated && points.length) updated.textContent = 'только что';
      } catch (_) {
        // The last valid snapshot remains visible while the connection recovers.
      }
    }
    window.setTimeout(poll, 5000);
  };

  new ResizeObserver(renderChart).observe(canvas);
  render();
  window.setTimeout(poll, 5000);
})();
