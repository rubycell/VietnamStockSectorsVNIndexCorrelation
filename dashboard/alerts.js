/* Alerts Tab - View alert history */

registerTab('alerts', async function initAlertsTab() {
    const container = document.getElementById('tab-alerts');
    showLoading(container);

    try {
        const alerts = await apiFetch('/api/alerts');
        renderAlerts(container, alerts);
    } catch (error) {
        showError(container, `Failed to load alerts: ${error.message}`);
    }
});

function renderAlerts(container, alerts) {
    container.innerHTML = `
        <div class="panel-card">
            <div class="toolbar">
                <h2>Alert History</h2>
                <div class="toolbar-group">
                    <input type="text" class="inline-input" id="alertTickerFilter" placeholder="Filter by ticker..." style="width: 160px;">
                    <button class="btn btn-primary" id="refreshAlerts">Refresh</button>
                </div>
            </div>
            <div id="alertsTableContainer">
                ${alertsTable(alerts)}
            </div>
        </div>
    `;

    document.getElementById('alertTickerFilter').addEventListener('input', async (e) => {
        const ticker = e.target.value.trim().toUpperCase();
        const tableContainer = document.getElementById('alertsTableContainer');
        try {
            const url = ticker ? `/api/alerts?ticker=${encodeURIComponent(ticker)}` : '/api/alerts';
            const filtered = await apiFetch(url);
            tableContainer.innerHTML = alertsTable(filtered);
        } catch (error) {
            showError(tableContainer, `Filter failed: ${error.message}`);
        }
    });

    document.getElementById('refreshAlerts').addEventListener('click', async () => {
        showLoading(container);
        try {
            const freshAlerts = await apiFetch('/api/alerts');
            renderAlerts(container, freshAlerts);
        } catch (error) {
            showError(container, `Failed to refresh: ${error.message}`);
        }
    });
}

function alertsTable(alerts) {
    if (!alerts || alerts.length === 0) {
        return '<div class="empty-state"><p>No alerts recorded yet.</p></div>';
    }

    return `
        <div style="overflow-x: auto;">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Ticker</th>
                        <th>Rule</th>
                        <th>Severity</th>
                        <th>Message</th>
                        <th>Telegram</th>
                        <th>WhatsApp</th>
                    </tr>
                </thead>
                <tbody>
                    ${alerts.map(a => `
                        <tr>
                            <td style="white-space: nowrap; font-size: 12px;">${formatAlertDate(a.created_at)}</td>
                            <td><strong>${a.ticker}</strong></td>
                            <td>${a.rule_id}</td>
                            <td>${severityBadge(a.severity)}</td>
                            <td>${a.message}</td>
                            <td>${a.sent_telegram ? '&#10004;' : '-'}</td>
                            <td>${a.sent_whatsapp ? '&#10004;' : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function formatAlertDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('en-GB', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}
