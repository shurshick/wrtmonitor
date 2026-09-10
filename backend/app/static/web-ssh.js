document.addEventListener('DOMContentLoaded', () => {
  const terminalTheme = Object.freeze({
    background: '#07101c',
    foreground: '#eef4f9',
    cursor: '#62d4e6',
    cursorAccent: '#07101c',
    selectionBackground: '#24526b',
    black: '#71869a',
    red: '#ff858b',
    green: '#62d991',
    yellow: '#f1bd62',
    blue: '#72aef8',
    magenta: '#d6a8ff',
    cyan: '#62d4e6',
    white: '#eef4f9',
    brightBlack: '#9babb9',
    brightRed: '#ffb1b5',
    brightGreen: '#91e8b4',
    brightYellow: '#f8d79b',
    brightBlue: '#a8cdff',
    brightMagenta: '#e5c9ff',
    brightCyan: '#a5edf6',
    brightWhite: '#ffffff',
  });
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
  let themeObserver;
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

  const applyTerminalTheme = () => {
    if (!terminal) return;
    terminal.options.theme = { ...terminalTheme };
    terminal.options.minimumContrastRatio = 7;
    terminal.refresh(0, terminal.rows - 1);
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
      theme: { ...terminalTheme },
    });
    fitAddon = new window.FitAddon.FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(container);
    root.wrtmonitorTerminal = terminal;
    applyTerminalTheme();
    themeObserver = new MutationObserver(applyTerminalTheme);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
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
    themeObserver?.disconnect();
  });
});
