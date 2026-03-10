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
                            <tr>
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
}
