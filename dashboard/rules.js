/* Rules Tab - Evaluate and display trading rules */

registerTab('rules', function initRulesTab() {
    const container = document.getElementById('tab-rules');

    container.innerHTML = `
        <div class="panel-card">
            <div class="toolbar">
                <h2>Trading Rules</h2>
                <button class="btn btn-primary" id="evaluateRules">Re-evaluate</button>
            </div>
            <div id="rulesResult">
                <div class="empty-state"><p>Loading rules evaluation...</p></div>
            </div>
        </div>
        <div class="panel-card">
            <h2>Rule Reference</h2>
            <div style="overflow-x: auto;">
                <table class="data-table">
                    <thead>
                        <tr><th>#</th><th>ID</th><th>Rule</th><th>Condition</th><th>Severity</th><th>Alert</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>1</td>
                            <td><code>no_prediction</code></td>
                            <td>No prediction</td>
                            <td>Dashboard disclaimer — never triggers</td>
                            <td>${severityBadge('INFO')}</td>
                            <td>Dashboard</td>
                        </tr>
                        <tr>
                            <td>2</td>
                            <td><code>fud_reduce_size</code></td>
                            <td>FUD — reduce size</td>
                            <td>FUD detected in market → reduce planned action size</td>
                            <td>${severityBadge('WARNING')}</td>
                            <td>Discord</td>
                        </tr>
                        <tr>
                            <td>3</td>
                            <td><code>no_fomo_swap</code></td>
                            <td>No FOMO swap</td>
                            <td>Dashboard reminder — never triggers</td>
                            <td>${severityBadge('INFO')}</td>
                            <td>Dashboard</td>
                        </tr>
                        <tr>
                            <td>4</td>
                            <td><code>below_swing_low_sell</code></td>
                            <td>Below swing low — SELL</td>
                            <td>Price closed below active confirmed swing low → consider selling</td>
                            <td>${severityBadge('CRITICAL')}</td>
                            <td>All</td>
                        </tr>
                        <tr>
                            <td>5</td>
                            <td><code>stick_to_strategy</code></td>
                            <td>Stick to strategy</td>
                            <td>Dashboard label — never triggers</td>
                            <td>${severityBadge('INFO')}</td>
                            <td>Dashboard</td>
                        </tr>
                        <tr>
                            <td>6</td>
                            <td><code>fud_reduce_further</code></td>
                            <td>FUD escalating — reduce further</td>
                            <td>FUD severity increased since last check → reduce further</td>
                            <td>${severityBadge('WARNING')}</td>
                            <td>Discord</td>
                        </tr>
                        <tr>
                            <td>7</td>
                            <td><code>ptp_to_swing_low</code></td>
                            <td>Partial take-profit to swing low</td>
                            <td>Position #2+ in profit → partial take-profit to pull BE to swing low</td>
                            <td>${severityBadge('INFO')}</td>
                            <td>Discord</td>
                        </tr>
                        <tr>
                            <td>8</td>
                            <td><code>high_entry_sell_levels</code></td>
                            <td>Entry far above swing low</td>
                            <td>Position #1: sell 50% at target level (2×entry − swing_low) to pull BE to swing low</td>
                            <td>${severityBadge('INFO')}</td>
                            <td>Discord</td>
                        </tr>
                        <tr>
                            <td>9</td>
                            <td><code>stoploss_all_pos2</code></td>
                            <td>Stop-loss position #2+</td>
                            <td>Position #2+ below active swing low → stop-loss all, keep max 200 shares</td>
                            <td>${severityBadge('CRITICAL')}</td>
                            <td>All</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;

    document.getElementById('evaluateRules').addEventListener('click', evaluateRules);

    // Auto-evaluate on tab open
    evaluateRules();
});

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
            &nbsp;|&nbsp; Rules triggered: ${triggered ? triggered.length : 0}
        </div>
    ` : '';

    if (!triggered || triggered.length === 0) {
        container.innerHTML = fudHtml + '<div class="empty-state"><p>All clear — no rules triggered.</p></div>';
        return;
    }

    // Group by severity for summary
    const critical = triggered.filter(r => r.severity === 'critical');
    const warning = triggered.filter(r => r.severity === 'warning');
    const info = triggered.filter(r => r.severity === 'info');

    const summaryHtml = `
        <div style="margin-bottom: 12px; display: flex; gap: 12px; flex-wrap: wrap;">
            ${critical.length ? `<span style="padding: 4px 10px; background: #450a0a; border: 1px solid #dc2626; border-radius: 6px; font-size: 12px;">CRITICAL: ${critical.length}</span>` : ''}
            ${warning.length ? `<span style="padding: 4px 10px; background: #422006; border: 1px solid #d97706; border-radius: 6px; font-size: 12px;">WARNING: ${warning.length}</span>` : ''}
            ${info.length ? `<span style="padding: 4px 10px; background: #052e16; border: 1px solid #16a34a; border-radius: 6px; font-size: 12px;">INFO: ${info.length}</span>` : ''}
        </div>
    `;

    container.innerHTML = `
        ${fudHtml}
        ${summaryHtml}
        <div style="overflow-x: auto;">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Rule</th>
                        <th>Ticker</th>
                        <th>Severity</th>
                        <th>Message</th>
                    </tr>
                </thead>
                <tbody>
                    ${triggered.map(r => `
                        <tr>
                            <td>#${r.rule_number}</td>
                            <td><strong>${r.ticker}</strong></td>
                            <td>${severityBadge(r.severity)}</td>
                            <td>${r.message}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}
