document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-terminal-device]');
  const container = document.getElementById('terminal-container');
  const status = document.getElementById('terminal-status');
  const connectButton = document.getElementById('btn-terminal-connect');
  const disconnectButton = document.getElementById('btn-terminal-disconnect');
  if (!root || !container || !status || !connectButton || !disconnectButton) return;

  const deviceId = root.dataset.terminalDevice;
  let terminal;
  let fitAddon;
  let socket;
  let dataSubscription;
  let resizeSubscription;
  let reconnectAllowed = true;

  const setState = (value, label) => {
    root.dataset.terminalState = value;
    status.textContent = label;
    const active = ['queued', 'connecting', 'connected'].includes(value);
    connectButton.hidden = active;
    disconnectButton.hidden = !active;
  };

  const decodeOutput = (encoded) => {
    const raw = window.atob(encoded);
    const bytes = new Uint8Array(raw.length);
    for (let index = 0; index < raw.length; index += 1) bytes[index] = raw.charCodeAt(index);
    return bytes;
  };

  const send = (message) => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
  };

  const fit = () => {
    if (terminal && fitAddon) fitAddon.fit();
  };

  const ensureTerminal = () => {
    if (terminal) return true;
    if (typeof window.Terminal !== 'function' || !window.FitAddon?.FitAddon) {
      setState('failed', 'Локальный компонент терминала не загрузился');
      return false;
    }
    terminal = new window.Terminal({
      cursorBlink: true,
      fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace',
      fontSize: 14,
      minimumContrastRatio: 7,
      scrollback: 5000,
      theme: {
        background: '#07101c',
        foreground: '#d8e7f5',
        cursor: '#35c4df',
        selectionBackground: '#24526b',
      },
    });
    fitAddon = new window.FitAddon.FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(container);
    root.wrtmonitorTerminal = terminal;
    fit();
    dataSubscription = terminal.onData((data) => send({ type: 'input', data }));
    resizeSubscription = terminal.onResize(({ cols, rows }) => {
      send({ type: 'resize', columns: cols, rows });
    });
    return true;
  };

  const disconnect = () => {
    reconnectAllowed = false;
    send({ type: 'close' });
    socket?.close(1000, 'closed by user');
    socket = undefined;
    setState('closed', 'Отключено');
  };

  const connect = () => {
    if (!ensureTerminal()) return;
    reconnectAllowed = true;
    terminal.reset();
    fit();
    terminal.focus();
    setState('connecting', 'Подключение к агенту');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const query = new URLSearchParams({ columns: String(terminal.cols), rows: String(terminal.rows) });
    socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/devices/${deviceId}/terminal/ws?${query}`);
    socket.addEventListener('message', (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch (_) {
        setState('failed', 'Сервер вернул некорректный кадр');
        return;
      }
      if (message.type === 'output' && message.data) {
        terminal.write(decodeOutput(message.data));
      } else if (message.type === 'session') {
        root.dataset.terminalSession = message.session_id || '';
      } else if (message.type === 'status') {
        const labels = {
          queued: 'Команда ожидает агента',
          connecting: 'Агент создаёт PTY',
          connected: 'Подключено',
          closed: 'Сессия завершена',
          failed: message.reason || 'Сессия завершилась с ошибкой',
          expired: 'Сессия просрочена',
        };
        setState(message.status, labels[message.status] || message.status);
        if (message.status === 'connected') terminal.focus();
      } else if (message.type === 'error') {
        setState('failed', message.message || 'Ошибка терминала');
      }
    });
    socket.addEventListener('close', (event) => {
      socket = undefined;
      setState(reconnectAllowed && event.code !== 1000 ? 'failed' : 'closed', reconnectAllowed && event.code !== 1000 ? 'Соединение с сервером потеряно' : 'Отключено');
    });
    socket.addEventListener('error', () => setState('failed', 'WebSocket недоступен'));
  };

  connectButton.addEventListener('click', connect);
  disconnectButton.addEventListener('click', disconnect);
  window.addEventListener('resize', fit);
  window.addEventListener('beforeunload', () => {
    reconnectAllowed = false;
    socket?.close(1000, 'page closed');
    dataSubscription?.dispose();
    resizeSubscription?.dispose();
  });
});
