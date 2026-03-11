/* Portfolio Tab - Shows holdings with P&L */

registerTab('portfolio', async function initPortfolioTab() {
    const container = document.getElementById('tab-portfolio');
    showLoading(container);

    try {
        const data = await apiFetch('/api/portfolio');
        renderPortfolio(container, data);
    } catch (error) {
        showError(container, `Failed to load portfolio: ${error.message}`);
    }
});

function renderPortfolio(container, data) {
    const { holdings, total_cost, total_realized_pnl, total_unrealized_pnl, total_holdings } = data;

    if (!holdings || holdings.length === 0) {
        showEmpty(container, 'No holdings found. Upload trade data first.');
        return;
    }

    container.innerHTML = `
        <div class="panel-card">
            <div class="toolbar">
                <h2>Portfolio Holdings</h2>
                <button class="btn btn-primary" id="refreshPortfolio">Refresh</button>
            </div>
            <div style="overflow-x: auto;">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th class="text-right">Shares</th>
                            <th class="text-right">VWAP Cost</th>
                            <th class="text-right">Total Cost</th>
                            <th class="text-right">Current Price</th>
                            <th class="text-right">Unrealized P&L</th>
                            <th class="text-right">Realized P&L</th>
                            <th class="text-right">Position #</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${holdings.map(h => `
                            <tr class="clickable-row" data-ticker="${h.ticker}" style="cursor:pointer">
                                <td><strong>${h.ticker}</strong></td>
                                <td class="text-right">${formatNumber(h.total_shares)}</td>
                                <td class="text-right">${formatNumber(h.vwap_cost)}</td>
                                <td class="text-right">${formatNumber(h.total_cost)}</td>
                                <td class="text-right">${h.current_price ? formatNumber(h.current_price) : '-'}</td>
                                <td class="text-right ${pnlClass(h.unrealized_pnl)}">${formatNumber(h.unrealized_pnl)}</td>
                                <td class="text-right ${pnlClass(h.realized_pnl)}">${formatNumber(h.realized_pnl)}</td>
                                <td class="text-right">${h.position_number || '-'}</td>
                            </tr>
                        `).join('')}
                        <tr class="totals-row">
                            <td><strong>Total</strong></td>
                            <td class="text-right">${total_holdings}</td>
                            <td></td>
                            <td class="text-right">${formatNumber(total_cost)}</td>
                            <td></td>
                            <td class="text-right ${pnlClass(total_unrealized_pnl)}">${formatNumber(total_unrealized_pnl)}</td>
                            <td class="text-right ${pnlClass(total_realized_pnl)}">${formatNumber(total_realized_pnl)}</td>
                            <td></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;

    document.getElementById('refreshPortfolio').addEventListener('click', async () => {
        showLoading(container);
        try {
            const freshData = await apiFetch('/api/portfolio');
            renderPortfolio(container, freshData);
        } catch (error) {
            showError(container, `Failed to refresh: ${error.message}`);
        }
    });

    // Click-to-detail on ticker rows
    container.querySelectorAll('.clickable-row').forEach(row => {
        row.addEventListener('click', async () => {
            const ticker = row.dataset.ticker;
            // Remove any existing detail panel
            const existing = container.querySelector('.ticker-detail');
            if (existing) existing.remove();
            // Highlight selected row
            container.querySelectorAll('.clickable-row').forEach(r => r.classList.remove('selected-row'));
            row.classList.add('selected-row');
            // Show loading indicator
            const detailPanel = document.createElement('div');
            detailPanel.className = 'ticker-detail panel-card';
            detailPanel.style.marginTop = '16px';
            detailPanel.innerHTML = '<p>Loading details...</p>';
            container.appendChild(detailPanel);
            try {
                const detail = await apiFetch(`/api/portfolio/${ticker}`);
                renderTickerDetail(detailPanel, detail);
            } catch (error) {
                detailPanel.innerHTML = `<p class="error-text">Failed to load details: ${error.message}</p>`;
            }
        });
    });
}

function renderTickerDetail(panel, detail) {
    const activePositions = detail.positions.filter(p => p.status === 'active');
    const closedPositions = detail.positions.filter(p => p.status === 'closed');

    panel.innerHTML = `
        <div class="toolbar">
            <h3>${detail.ticker} — Position Detail</h3>
            <button class="btn" id="closeDetail">Close</button>
        </div>
        <div style="display:flex; gap:24px; flex-wrap:wrap; margin-bottom:16px;">
            <div><strong>Shares:</strong> ${formatNumber(detail.total_shares)}</div>
            <div><strong>VWAP Cost:</strong> ${formatNumber(detail.vwap_cost)}</div>
            <div><strong>Current Price:</strong> ${detail.current_price ? formatNumber(detail.current_price) : '-'}</div>
            <div><strong>Unrealized P&L:</strong> <span class="${pnlClass(detail.unrealized_pnl)}">${formatNumber(detail.unrealized_pnl)}</span></div>
            <div><strong>Realized P&L:</strong> <span class="${pnlClass(detail.realized_pnl)}">${formatNumber(detail.realized_pnl)}</span></div>
            <div><strong>Positions:</strong> ${detail.position_number}</div>
        </div>

        ${activePositions.length > 0 ? `
        <h4 style="margin:12px 0 8px">Active Positions (${activePositions.length})</h4>
        <div style="overflow-x:auto">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Order No</th>
                        <th class="text-right">Buy Shares</th>
                        <th class="text-right">Avg Price</th>
                        <th class="text-right">Remaining</th>
                        <th class="text-right">Sold</th>
                        <th class="text-right">P&L per Share</th>
                    </tr>
                </thead>
                <tbody>
                    ${activePositions.map(p => {
                        const pnlPerShare = detail.current_price ? detail.current_price - p.avg_price : 0;
                        return `<tr>
                            <td><code>${p.order_no}</code></td>
                            <td class="text-right">${formatNumber(p.buy_shares)}</td>
                            <td class="text-right">${formatNumber(p.avg_price)}</td>
                            <td class="text-right">${formatNumber(p.remaining_shares)}</td>
                            <td class="text-right">${formatNumber(p.sold_shares)}</td>
                            <td class="text-right ${pnlClass(pnlPerShare)}">${formatNumber(pnlPerShare)}</td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>
        ` : ''}

        ${closedPositions.length > 0 ? `
        <details style="margin-top:12px">
            <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">Closed Positions (${closedPositions.length})</summary>
            <div style="overflow-x:auto">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Order No</th>
                            <th class="text-right">Buy Shares</th>
                            <th class="text-right">Avg Price</th>
                            <th class="text-right">Sold</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${closedPositions.map(p => `
                            <tr>
                                <td><code>${p.order_no}</code></td>
                                <td class="text-right">${formatNumber(p.buy_shares)}</td>
                                <td class="text-right">${formatNumber(p.avg_price)}</td>
                                <td class="text-right">${formatNumber(p.sold_shares)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </details>
        ` : ''}

        ${detail.trades && detail.trades.length > 0 ? `
        <details style="margin-top:12px">
            <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">Trade History (${detail.trades.length})</summary>
            <div style="overflow-x:auto">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Side</th>
                            <th class="text-right">Volume</th>
                            <th class="text-right">Price</th>
                            <th class="text-right">Value</th>
                            <th class="text-right">Fee</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${detail.trades.map(t => `
                            <tr>
                                <td>${t.date}</td>
                                <td class="${t.side === 'BUY' ? 'positive' : 'negative'}">${t.side}</td>
                                <td class="text-right">${formatNumber(t.volume)}</td>
                                <td class="text-right">${formatNumber(t.price)}</td>
                                <td class="text-right">${formatNumber(t.value)}</td>
                                <td class="text-right">${formatNumber(t.fee)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </details>
        ` : ''}
    `;

    panel.querySelector('#closeDetail').addEventListener('click', () => {
        panel.remove();
        document.querySelectorAll('.clickable-row').forEach(r => r.classList.remove('selected-row'));
    });
}
