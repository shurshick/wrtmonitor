document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('terminal-container');
    const overlay = document.getElementById('terminal-overlay');
    const btnConnect = document.getElementById('btn-ssh-connect');
    const btnDisconnect = document.getElementById('btn-ssh-disconnect');
    
    if (!container || !btnConnect) return;
    
    let term = null;
    let fitAddon = null;
    let ws = null;
    
    // We get deviceId from the URL or a global variable usually present in device pages
    const pathParts = window.location.pathname.split('/');
    const deviceId = pathParts[pathParts.length - 1]; // Assuming /devices/{id}
    
    function initTerminal() {
        if (!term) {
            term = new Terminal({
                cursorBlink: true,
                theme: { background: '#1e1e1e' }
            });
            fitAddon = new FitAddon.FitAddon();
            term.loadAddon(fitAddon);
            term.open(container);
            fitAddon.fit();
            
            window.addEventListener('resize', () => {
                fitAddon.fit();
            });
        }
    }

    btnConnect.addEventListener('click', () => {
        initTerminal();
        term.reset();
        term.write('\r\n\x1b[33mConnecting to router terminal...\x1b[0m\r\n');
        
        // Connect WS
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/devices/${deviceId}/ssh/ws`);
        
        ws.onopen = () => {
            overlay.style.display = 'none';
            btnConnect.style.display = 'none';
            btnDisconnect.style.display = 'inline-block';
            term.write('\r\n\x1b[32mConnected.\x1b[0m\r\n');
        };
        
        ws.onmessage = (event) => {
            term.write(event.data);
        };
        
        ws.onclose = () => {
            term.write('\r\n\x1b[31mDisconnected from server.\x1b[0m\r\n');
            btnConnect.style.display = 'inline-block';
            btnDisconnect.style.display = 'none';
            overlay.style.display = 'flex';
        };
        
        term.onData(data => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(data);
            }
        });
    });
    
    btnDisconnect.addEventListener('click', () => {
        if (ws) {
            ws.close();
            ws = null;
        }
    });
});
