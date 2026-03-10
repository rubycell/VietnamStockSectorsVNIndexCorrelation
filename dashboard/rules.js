/* Rules Tab - Evaluate and display trading rules */

registerTab('rules', function initRulesTab() {
    const container = document.getElementById('tab-rules');

    container.innerHTML = `
        <div class="panel-card">
            <div class="toolbar">
                <h2>Trading Rules</h2>
                <button class="btn btn-primary" id="evaluateRules">Evaluate Rules</button>
            </div>
            <div id="rulesResult">
                <div class="empty-state"><p>Click "Evaluate Rules" to check all 9 trading rules against your holdings.</p></div>
            </div>
        </div>
        <div class="panel-card">
            <h2>Rule Reference</h2>
            <div style="overflow-x: auto;">
                <table class="data-table">
                    <thead>
                        <tr><th>#</th><th>Rule</th><th>Severity</th><th>Alert</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>1</td><td>Buy (new position) recommendation</td><td>${severityBadge('INFO')}</td><td>Dashboard</td></tr>
                        <tr><td>2</td><td>FUD detected - watch for opportunity</td><td>${severityBadge('WARNING')}</td><td>Telegram</td></tr>
                        <tr><td>3</td><td>Averaging down recommendation</td><td>${severityBadge('INFO')}</td><td>Dashboard</td></tr>
                        <tr><td>4</td><td>Below swing low - SELL signal</td><td>${severityBadge('CRITICAL')}</td><td>All</td></tr>
                        <tr><td>5</td><td>Break-even or take-profit signal</td><td>${severityBadge('INFO')}</td><td>Dashboard</td></tr>
                        <tr><td>6</td><td>FUD + holding position alert</td><td>${severityBadge('WARNING')}</td><td>Telegram</td></tr>
                        <tr><td>7</td><td>Stop-loss level approach</td><td>${severityBadge('WARNING')}</td><td>Telegram</td></tr>
                        <tr><td>8</td><td>Important price level proximity</td><td>${severityBadge('INFO')}</td><td>Dashboard</td></tr>
                        <tr><td>9</td><td>Stop-loss position #2+ - mandatory</td><td>${severityBadge('CRITICAL')}</td><td>All</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;

    document.getElementById('evaluateRules').addEventListener('click', evaluateRules);
}

async function evaluateRules() {
    const resultContainer = document.getElementById('rulesResult');
    showLoading(resultContainer);

    try {
        const data = await apiFetch('/api/rules/evaluate', { method: 'POST' });
        renderRulesResult(resultContainer, data);
    } catch (error) {
        showError(resultContainer, `Failed to evaluate rules: ${error.message}`);
    }
}

function renderRulesResult(container, data) {
    const { triggered, holdings_checked, fud_status } = data;

    const fudHtml = fud_status ? `
        <div style="margin-bottom: 16px; padding: 12px; background: ${fud_status.is_fud ? '#450a0a' : '#052e16'}; border-radius: 8px; font-size: 13px;">
            <strong>FUD Status:</strong> ${fud_status.is_fud ? `Active (${fud_status.severity})` : 'No FUD detected'}
            &nbsp;|&nbsp; Holdings checked: ${holdings_checked}
        </div>
    ` : '';

    if (!triggered || triggered.length === 0) {
        container.innerHTML = fudHtml + '<div class="empty-state"><p>No rules triggered. All clear.</p></div>';
        return;
    }

    container.innerHTML = `
        ${fudHtml}
        <div style="overflow-x: auto;">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Rule</th>
                        <th>Ticker</th>
                        <th>Severity</th>
                        <th>Message</th>
                        <th>Alert</th>
                    </tr>
                </thead>
                <tbody>
                    ${triggered.map(r => `
                        <tr>
                            <td>#${r.rule_number}</td>
                            <td><strong>${r.ticker}</strong></td>
                            <td>${severityBadge(r.severity)}</td>
                            <td>${r.message}</td>
                            <td>${r.alert ? 'Yes' : 'Dashboard only'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}
