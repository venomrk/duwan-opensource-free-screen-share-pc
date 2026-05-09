document.addEventListener('DOMContentLoaded', () => {
    // ── DOM refs ──
    const deviceList = document.getElementById('device-list');
    const refreshBtn = document.getElementById('refresh-btn');
    const refreshWifiBtn = document.getElementById('refresh-wifi-btn');
    const actionPanel = document.getElementById('device-controls');
    const noDeviceMsg = document.getElementById('no-device-msg');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const statusMsg = document.getElementById('status-msg');
    const ctrlName = document.getElementById('ctrl-device-name');
    const ctrlId = document.getElementById('ctrl-device-id');
    const ctrlBadge = document.getElementById('ctrl-conn-badge');
    const ctrlDetails = document.getElementById('ctrl-details');

    // WiFi
    const wifiConnectBtn = document.getElementById('wifi-connect-btn');
    const wifiPairBtn = document.getElementById('wifi-pair-btn');
    const wifiSwitchBtn = document.getElementById('wifi-switch-btn');

    let selected = null;

    // ── Tab switching ──
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        });
    });

    document.querySelectorAll('.wifi-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.wifi-tab').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.wifi-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('wifi-' + btn.dataset.wifi).classList.add('active');
        });
    });

    // ── Fetch devices ──
    async function fetchDevices() {
        try {
            const r = await fetch('/api/devices');
            const data = await r.json();
            renderDevices(data.devices);
        } catch (e) {
            deviceList.innerHTML = '<div class="empty-devices">Backend unreachable</div>';
        }
    }

    function renderDevices(devices) {
        if (!devices || devices.length === 0) {
            deviceList.innerHTML = '<div class="empty-devices">No devices found.<br>Connect via USB or WiFi.</div>';
            return;
        }
        deviceList.innerHTML = '';
        devices.forEach(d => {
            const isActive = selected && selected.id === d.id;
            const div = document.createElement('div');
            div.className = 'device-item' + (isActive ? ' active' : '');
            const isWifi = d.connection === 'wireless';
            div.innerHTML = `
                <div class="dev-icon ${isWifi ? 'wireless' : 'usb'}">${isWifi ? '📶' : '🔌'}</div>
                <div class="dev-info">
                    <h4>${d.model || 'Device'}</h4>
                    <p>${d.id}</p>
                </div>
                <div class="dev-status" style="background:${d.status === 'device' ? 'var(--success)' : 'var(--danger)'}"></div>
            `;
            div.addEventListener('click', () => selectDevice(d));
            deviceList.appendChild(div);
        });
    }

    // ── Select device ──
    async function selectDevice(d) {
        selected = d;
        document.querySelectorAll('.device-item').forEach(el => el.classList.remove('active'));
        event.currentTarget.classList.add('active');

        noDeviceMsg.classList.add('hidden');
        actionPanel.classList.remove('hidden');

        ctrlName.textContent = d.model || 'Device';
        ctrlId.textContent = d.id;
        const isWifi = d.connection === 'wireless';
        ctrlBadge.textContent = isWifi ? 'WiFi' : 'USB';
        ctrlBadge.className = 'conn-badge ' + (isWifi ? 'wifi' : 'usb');

        // Show/hide stop vs start
        if (d.mirroring) {
            startBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
        } else {
            startBtn.classList.remove('hidden');
            stopBtn.classList.add('hidden');
        }

        // Fetch extended details
        try {
            const r = await fetch('/api/device/' + encodeURIComponent(d.id) + '/details');
            const info = await r.json();
            ctrlDetails.innerHTML = `
                <span>📱 ${info.brand} ${info.model}</span>
                <span>🤖 Android ${info.android}</span>
                <span>📐 ${info.resolution}</span>
                <span>🔋 ${info.battery}%</span>
            `;
        } catch (e) {
            ctrlDetails.innerHTML = '<span>Could not fetch details</span>';
        }

        statusMsg.textContent = '';
        statusMsg.className = 'status-msg';
    }

    // ── Start mirroring ──
    startBtn.addEventListener('click', async () => {
        if (!selected) return;
        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';

        const body = {
            device_id: selected.id,
            max_fps: document.getElementById('opt-fps').value,
            max_size: document.getElementById('opt-res').value,
            bitrate: document.getElementById('opt-bitrate').value,
            audio: document.getElementById('opt-audio').checked,
            control: document.getElementById('opt-control').checked,
            stay_awake: document.getElementById('opt-awake').checked,
            borderless: document.getElementById('opt-borderless').checked,
            always_on_top: document.getElementById('opt-ontop').checked,
            fullscreen: document.getElementById('opt-fullscreen').checked,
        };

        try {
            const r = await fetch('/api/start', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
            const res = await r.json();
            if (res.success) {
                showStatus('Mirroring started!', 'ok');
                startBtn.classList.add('hidden');
                stopBtn.classList.remove('hidden');
                selected.mirroring = true;
            } else {
                showStatus('Error: ' + res.error, 'err');
            }
        } catch (e) {
            showStatus('Failed to reach backend', 'err');
        }
        startBtn.disabled = false;
        startBtn.textContent = '▶ Start Mirroring';
    });

    // ── Stop mirroring ──
    stopBtn.addEventListener('click', async () => {
        if (!selected) return;
        try {
            await fetch('/api/stop', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ device_id: selected.id }) });
            showStatus('Mirroring stopped.', 'ok');
            stopBtn.classList.add('hidden');
            startBtn.classList.remove('hidden');
            selected.mirroring = false;
        } catch (e) {
            showStatus('Error stopping', 'err');
        }
    });

    // ── WiFi connect ──
    wifiConnectBtn.addEventListener('click', async () => {
        const ip = document.getElementById('wifi-ip').value.trim();
        const port = document.getElementById('wifi-port').value.trim();
        if (!ip) return showStatus('Enter phone IP', 'err');
        wifiConnectBtn.disabled = true;
        wifiConnectBtn.textContent = 'Connecting...';
        try {
            const r = await fetch('/api/wireless/connect', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ ip, port }) });
            const res = await r.json();
            showStatus(res.message || (res.success ? 'Connected!' : 'Failed'), res.success ? 'ok' : 'err');
            if (res.success) fetchDevices();
        } catch (e) { showStatus('Network error', 'err'); }
        wifiConnectBtn.disabled = false;
        wifiConnectBtn.textContent = 'Connect';
    });

    // ── WiFi pair ──
    wifiPairBtn.addEventListener('click', async () => {
        const ip = document.getElementById('pair-ip').value.trim();
        const port = document.getElementById('pair-port').value.trim();
        const code = document.getElementById('pair-code').value.trim();
        if (!ip || !port || !code) return showStatus('Fill all pairing fields', 'err');
        wifiPairBtn.disabled = true;
        wifiPairBtn.textContent = 'Pairing...';
        try {
            const r = await fetch('/api/wireless/pair', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ ip, port, code }) });
            const res = await r.json();
            showStatus(res.message || (res.success ? 'Paired!' : 'Failed'), res.success ? 'ok' : 'err');
        } catch (e) { showStatus('Network error', 'err'); }
        wifiPairBtn.disabled = false;
        wifiPairBtn.textContent = 'Pair Device';
    });

    // ── USB → WiFi switch ──
    wifiSwitchBtn.addEventListener('click', async () => {
        if (!selected) return showStatus('Select a USB device first', 'err');
        wifiSwitchBtn.disabled = true;
        wifiSwitchBtn.textContent = 'Switching...';
        try {
            const r = await fetch('/api/wireless/setup', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ device_id: selected.id }) });
            const res = await r.json();
            if (res.success && res.device_ip) {
                showStatus('Switched! Now connect to ' + res.device_ip + ':5555', 'ok');
                document.getElementById('wifi-ip').value = res.device_ip;
            } else {
                showStatus(res.message || 'Switch failed', 'err');
            }
        } catch (e) { showStatus('Error', 'err'); }
        wifiSwitchBtn.disabled = false;
        wifiSwitchBtn.textContent = 'Switch to WiFi';
    });

    function showStatus(msg, type) {
        statusMsg.textContent = msg;
        statusMsg.className = 'status-msg ' + type;
    }

    // ── Refresh buttons ──
    refreshBtn.addEventListener('click', fetchDevices);
    refreshWifiBtn.addEventListener('click', fetchDevices);

    // ── Initial load ──
    fetchDevices();
});
