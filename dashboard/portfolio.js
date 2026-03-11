/* Portfolio Tab - Shows holdings with P&L, detail view with levels + chart */

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
                            <th class="text-right">Avg Cost</th>
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
                                <td class="text-right">${formatNumber(h.avg_cost)}</td>
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
            const existing = container.querySelector('.ticker-detail');
            if (existing) existing.remove();
            container.querySelectorAll('.clickable-row').forEach(r => r.classList.remove('selected-row'));
            row.classList.add('selected-row');

            const detailPanel = document.createElement('div');
            detailPanel.className = 'ticker-detail panel-card';
            detailPanel.style.marginTop = '16px';
            detailPanel.innerHTML = '<p>Loading details...</p>';
            container.appendChild(detailPanel);
            try {
                const [detail, levels, configData] = await Promise.all([
                    apiFetch(`/api/portfolio/${ticker}`),
                    apiFetch(`/api/levels/${ticker}?detect=true`).catch(() => null),
                    apiFetch('/api/config/round_number_increments').catch(() => null),
                ]);
                renderTickerDetail(detailPanel, detail, levels, configData);
            } catch (error) {
                detailPanel.innerHTML = `<p class="error-text">Failed to load details: ${error.message}</p>`;
            }
        });
    });
}

function renderTickerDetail(panel, detail, levels, configData) {
    const activePositions = detail.positions.filter(p => p.status === 'active');
    const closedPositions = detail.positions.filter(p => p.status === 'closed');
    const currentIncrements = configData?.value || '10,50';

    // All summary numbers from trade history (single source of truth)
    const ts = detail.trade_summary || {};
    const currentPrice = detail.current_price || 0;
    const reconciled = detail.reconciled;
    const positionRemaining = detail.position_remaining || 0;

    const reconcileWarning = !reconciled
        ? `<div style="background:#450a0a; border:1px solid #991b1b; border-radius:8px; padding:8px 12px; margin-bottom:12px; font-size:13px; color:#fca5a5;">
            ⚠ Positions mismatch: positions show <strong>${formatNumber(positionRemaining)}</strong> remaining vs trades show <strong>${formatNumber(ts.net_shares || 0)}</strong> net shares.
            <button class="btn btn-small" id="recalcPositionsBtn" style="margin-left:8px">Recalculate from Trades</button>
           </div>`
        : '';

    panel.innerHTML = `
        <div class="toolbar">
            <h3>${detail.ticker} — Position Detail</h3>
            <button class="btn" id="closeDetail">Close</button>
        </div>
        <div style="display:flex; gap:24px; flex-wrap:wrap; margin-bottom:12px; font-size:14px;">
            <div><strong>Net Shares:</strong> ${formatNumber(ts.net_shares || 0)}</div>
            <div><strong>Avg Cost:</strong> ${formatNumber(ts.avg_cost || 0)}</div>
            <div><strong>Current Price:</strong> ${currentPrice ? formatNumber(currentPrice) : '-'}</div>
            <div><strong>Unrealized P&L:</strong> <span class="${pnlClass(ts.unrealized_pnl)}">${formatNumber(ts.unrealized_pnl || 0)}</span></div>
            <div><strong>Realized P&L:</strong> <span class="${pnlClass(ts.realized_pnl)}">${formatNumber(ts.realized_pnl || 0)}</span></div>
            <div><strong>Total Fees:</strong> ${formatNumber(ts.total_fees || 0)}</div>
        </div>
        <div style="display:flex; gap:24px; flex-wrap:wrap; margin-bottom:16px; font-size:12px; color:#94a3b8;">
            <div>Bought: ${formatNumber(ts.total_bought || 0)} shares (${formatNumber(ts.total_buy_cost || 0)})</div>
            <div>Sold: ${formatNumber(ts.total_sold || 0)} shares (${formatNumber(ts.total_sell_revenue || 0)})</div>
        </div>

        ${reconcileWarning}

        <div style="display:flex; align-items:center; gap:12px; margin:12px 0 8px">
            <h4 style="margin:0">Active Positions (${activePositions.length})</h4>
            <button class="btn btn-small" id="addPositionBtn" title="Add position">+ Add</button>
        </div>
        <div style="overflow-x:auto">
            <table class="data-table" id="positionsTable">
                <thead>
                    <tr>
                        <th>Order No</th>
                        <th class="text-right">Size</th>
                        <th class="text-right">Avg Price</th>
                        <th class="text-right">Remaining</th>
                        <th class="text-right">Sold</th>
                        <th class="text-right">P&L per Share</th>
                        <th style="width:60px"></th>
                    </tr>
                </thead>
                <tbody>
                    ${activePositions.map(p => {
                        const pnlPerShare = currentPrice ? currentPrice - p.avg_price : 0;
                        const editable = p.id !== null;
                        return `<tr data-position-id="${p.id || ''}" data-ticker="${detail.ticker}">
                            <td><code>${p.order_no || '-'}</code></td>
                            <td class="text-right editable-cell" data-field="size" data-value="${p.size}">${formatNumber(p.size)}</td>
                            <td class="text-right editable-cell" data-field="avg_price" data-value="${p.avg_price}">${formatNumber(p.avg_price)}</td>
                            <td class="text-right editable-cell" data-field="remaining" data-value="${p.remaining}">${formatNumber(p.remaining)}</td>
                            <td class="text-right editable-cell" data-field="sold" data-value="${p.sold}">${formatNumber(p.sold)}</td>
                            <td class="text-right ${pnlClass(pnlPerShare)}">${formatNumber(pnlPerShare)}</td>
                            <td class="text-center">${editable ? `<button class="btn-icon delete-position-btn" title="Remove position">&times;</button>` : ''}</td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>

        ${closedPositions.length > 0 ? `
        <details style="margin-top:12px">
            <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">Closed Positions (${closedPositions.length})</summary>
            <div style="overflow-x:auto">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Order No</th>
                            <th class="text-right">Size</th>
                            <th class="text-right">Avg Price</th>
                            <th class="text-right">Sold</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${closedPositions.map(p => `
                            <tr>
                                <td><code>${p.order_no || '-'}</code></td>
                                <td class="text-right">${formatNumber(p.size)}</td>
                                <td class="text-right">${formatNumber(p.avg_price)}</td>
                                <td class="text-right">${formatNumber(p.sold)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </details>
        ` : ''}

        <details style="margin-top:12px" id="tradeHistorySection">
            <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">
                Trade History (${detail.trades ? detail.trades.length : 0})
                <button class="btn btn-small" id="addTradeBtn" title="Add trade" style="margin-left:12px" onclick="event.stopPropagation()">+ Add Trade</button>
            </summary>
            <div style="overflow-x:auto">
                <table class="data-table" id="tradesTable">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Side</th>
                            <th class="text-right">Volume</th>
                            <th class="text-right">Price</th>
                            <th class="text-right">Value</th>
                            <th class="text-right">Fee</th>
                            <th style="width:40px"></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${(detail.trades || []).map(t => `
                            <tr data-trade-id="${t.id || ''}">
                                <td class="trade-editable" data-field="trading_date" data-value="${t.date}">${t.date}</td>
                                <td class="trade-editable ${t.side === 'BUY' ? 'positive' : 'negative'}" data-field="trade_side" data-value="${t.side}">${t.side}</td>
                                <td class="text-right trade-editable" data-field="matched_volume" data-value="${t.volume}">${formatNumber(t.volume)}</td>
                                <td class="text-right trade-editable" data-field="matched_price" data-value="${t.price}">${formatNumber(t.price)}</td>
                                <td class="text-right">${formatNumber(t.value)}</td>
                                <td class="text-right trade-editable" data-field="fee" data-value="${t.fee}">${formatNumber(t.fee)}</td>
                                <td class="text-center"><button class="btn-icon delete-trade-btn" title="Remove trade">&times;</button></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </details>

        ${levels ? renderLevelsSection(levels, detail.ticker, currentIncrements) : ''}

        ${detail.ohlcv && detail.ohlcv.length > 0 ? `
        <div style="margin-top:16px">
            <h4 style="margin:0 0 8px; color:#94a3b8">Price Chart with Key Levels</h4>
            <div id="tickerChart" style="width:100%; height:400px; border-radius:8px; overflow:hidden; border:1px solid #1e293b;"></div>
            <div id="chartLegend" style="display:flex; gap:16px; flex-wrap:wrap; margin-top:8px; font-size:12px; color:#94a3b8;"></div>
        </div>
        ` : ''}
    `;

    panel.querySelector('#closeDetail').addEventListener('click', () => {
        panel.remove();
        document.querySelectorAll('.clickable-row').forEach(r => r.classList.remove('selected-row'));
    });

    // Position editing: inline click-to-edit
    bindPositionEditing(panel, detail);

    // Bind level management actions
    if (levels) {
        bindLevelActions(panel, detail.ticker, levels);
    }

    // Render candlestick chart with levels
    if (detail.ohlcv && detail.ohlcv.length > 0) {
        setTimeout(() => renderTickerChart(detail, levels), 50);
    }
}


function bindPositionEditing(panel, detail) {
    const ticker = detail.ticker;

    // Recalculate positions from trades (delete all stored, let API recompute)
    const recalcBtn = panel.querySelector('#recalcPositionsBtn');
    if (recalcBtn) {
        recalcBtn.addEventListener('click', async () => {
            if (!confirm('This will delete all stored positions and recalculate from trade history. Continue?')) return;
            try {
                // Delete all stored positions for this ticker
                const positions = await apiFetch(`/api/positions/${ticker}`);
                for (const p of positions) {
                    await apiFetch(`/api/positions/${p.id}`, { method: 'DELETE' });
                }
                reloadTickerDetail(panel, ticker);
            } catch (error) {
                alert(`Recalculate failed: ${error.message}`);
            }
        });
    }

    // Add position — directly creates a new active position
    const addBtn = panel.querySelector('#addPositionBtn');
    if (addBtn) {
        addBtn.addEventListener('click', async () => {
            const manualCount = detail.positions.filter(p => p.is_manual).length + 1;
            const orderNo = `MANUAL-${String(manualCount).padStart(3, '0')}`;
            const body = { ticker, order_no: orderNo, size: 100, avg_price: 0, remaining: 100, sold: 0 };
            try {
                const created = await apiFetch(`/api/positions/${ticker}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                await reloadTickerDetail(panel, ticker);
                // Flash new row
                const newRow = panel.querySelector(`tr[data-position-id="${created.id}"]`);
                if (newRow) {
                    newRow.style.transition = 'background 0.3s';
                    newRow.style.background = '#052e16';
                    setTimeout(() => { newRow.style.background = ''; }, 800);
                }
            } catch (error) {
                alert(`Add failed: ${error.message}`);
            }
        });
    }

    // Delete position buttons
    panel.querySelectorAll('.delete-position-btn').forEach(btn => {
        btn.addEventListener('click', async (event) => {
            event.stopPropagation();
            const row = btn.closest('tr');
            const positionId = row.dataset.positionId;
            if (!positionId) return;
            if (!confirm('Remove this position?')) return;

            try {
                await apiFetch(`/api/positions/${positionId}`, { method: 'DELETE' });
                reloadTickerDetail(panel, ticker);
            } catch (error) {
                alert(`Delete failed: ${error.message}`);
            }
        });
    });

    // Inline editing: click on editable cell
    panel.querySelectorAll('.editable-cell').forEach(cell => {
        cell.style.cursor = 'pointer';
        cell.title = 'Click to edit';

        cell.addEventListener('click', async (event) => {
            event.stopPropagation();
            if (cell.querySelector('input')) return; // already editing

            const row = cell.closest('tr');
            const positionId = row.dataset.positionId;
            if (!positionId) return;

            const field = cell.dataset.field;
            const currentValue = cell.dataset.value;

            const input = document.createElement('input');
            input.type = 'number';
            input.value = currentValue;
            input.className = 'inline-input';
            input.style.cssText = 'width:80px; text-align:right; font-size:13px; padding:2px 4px;';

            cell.textContent = '';
            cell.appendChild(input);
            input.focus();
            input.select();

            const saveEdit = async () => {
                const newValue = parseFloat(input.value);
                if (isNaN(newValue) || newValue === parseFloat(currentValue)) {
                    cell.textContent = formatNumber(parseFloat(currentValue));
                    return;
                }

                try {
                    const updateBody = {};
                    updateBody[field] = field === 'avg_price' ? newValue : Math.round(newValue);
                    await apiFetch(`/api/positions/${positionId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(updateBody),
                    });
                    await reloadTickerDetail(panel, ticker);
                    // Flash the updated row green briefly
                    const updatedRow = panel.querySelector(`tr[data-position-id="${positionId}"]`);
                    if (updatedRow) {
                        updatedRow.style.transition = 'background 0.3s';
                        updatedRow.style.background = '#052e16';
                        setTimeout(() => { updatedRow.style.background = ''; }, 800);
                    }
                } catch (error) {
                    cell.textContent = formatNumber(parseFloat(currentValue));
                    alert(`Update failed: ${error.message}`);
                }
            };

            input.addEventListener('blur', saveEdit);
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
                if (e.key === 'Escape') {
                    cell.textContent = formatNumber(parseFloat(currentValue));
                }
            });
        });
    });

    // --- Trade History editing ---

    // Add trade button
    const addTradeBtn = panel.querySelector('#addTradeBtn');
    if (addTradeBtn) {
        addTradeBtn.addEventListener('click', async (event) => {
            event.stopPropagation();
            const today = new Date().toISOString().slice(0, 10);
            const body = {
                ticker,
                trading_date: today,
                trade_side: 'BUY',
                matched_volume: 100,
                matched_price: 0,
                fee: 0,
            };
            try {
                await apiFetch(`/api/trades/${ticker}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                await reloadTickerDetail(panel, ticker);
                // Open the trade history section
                const section = panel.querySelector('#tradeHistorySection');
                if (section) section.open = true;
            } catch (error) {
                alert(`Add trade failed: ${error.message}`);
            }
        });
    }

    // Delete trade buttons
    panel.querySelectorAll('.delete-trade-btn').forEach(btn => {
        btn.addEventListener('click', async (event) => {
            event.stopPropagation();
            const row = btn.closest('tr');
            const tradeId = row.dataset.tradeId;
            if (!tradeId) return;
            if (!confirm('Remove this trade?')) return;
            try {
                await apiFetch(`/api/trades/${tradeId}`, { method: 'DELETE' });
                reloadTickerDetail(panel, ticker);
            } catch (error) {
                alert(`Delete failed: ${error.message}`);
            }
        });
    });

    // Inline editing for trade cells
    panel.querySelectorAll('.trade-editable').forEach(cell => {
        cell.style.cursor = 'pointer';
        cell.title = 'Click to edit';

        cell.addEventListener('click', async (event) => {
            event.stopPropagation();
            if (cell.querySelector('input')) return;

            const row = cell.closest('tr');
            const tradeId = row.dataset.tradeId;
            if (!tradeId) return;

            const field = cell.dataset.field;
            const currentValue = cell.dataset.value;

            const input = document.createElement('input');
            if (field === 'trading_date') {
                input.type = 'date';
                input.value = currentValue;
            } else if (field === 'trade_side') {
                input.type = 'text';
                input.value = currentValue;
                input.style.textTransform = 'uppercase';
            } else {
                input.type = 'number';
                input.value = currentValue;
                input.step = field === 'fee' ? '0.01' : '1';
            }
            input.className = 'inline-input';
            input.style.cssText += 'width:100px; font-size:13px; padding:2px 4px;';

            cell.textContent = '';
            cell.appendChild(input);
            input.focus();
            input.select();

            const saveTradeEdit = async () => {
                let newValue = input.value;
                if (field === 'trade_side') {
                    newValue = newValue.toUpperCase();
                    if (newValue !== 'BUY' && newValue !== 'SELL') {
                        cell.textContent = currentValue;
                        return;
                    }
                }
                if (field !== 'trading_date' && field !== 'trade_side') {
                    newValue = parseFloat(newValue);
                    if (isNaN(newValue)) {
                        cell.textContent = currentValue;
                        return;
                    }
                }
                if (String(newValue) === String(currentValue)) {
                    cell.textContent = currentValue;
                    return;
                }

                try {
                    const updateBody = {};
                    updateBody[field] = newValue;
                    await apiFetch(`/api/trades/${tradeId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(updateBody),
                    });
                    await reloadTickerDetail(panel, ticker);
                    // Keep trade history open and flash row
                    const section = panel.querySelector('#tradeHistorySection');
                    if (section) section.open = true;
                    const updatedRow = panel.querySelector(`tr[data-trade-id="${tradeId}"]`);
                    if (updatedRow) {
                        updatedRow.style.transition = 'background 0.3s';
                        updatedRow.style.background = '#052e16';
                        setTimeout(() => { updatedRow.style.background = ''; }, 800);
                    }
                } catch (error) {
                    cell.textContent = currentValue;
                    alert(`Update failed: ${error.message}`);
                }
            };

            input.addEventListener('blur', saveTradeEdit);
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
                if (e.key === 'Escape') { cell.textContent = currentValue; }
            });
        });
    });
}

async function reloadTickerDetail(panel, ticker) {
    try {
        const [detail, levels, configData] = await Promise.all([
            apiFetch(`/api/portfolio/${ticker}`),
            apiFetch(`/api/levels/${ticker}?detect=true`).catch(() => null),
            apiFetch('/api/config/round_number_increments').catch(() => null),
        ]);
        renderTickerDetail(panel, detail, levels, configData);
    } catch (error) {
        panel.innerHTML = `<p class="error-text">Failed to reload: ${error.message}</p>`;
    }
}


function renderLevelsSection(levels, ticker, currentIncrements) {
    // Active swing lows
    const swingLowsHtml = levels.active_swing_lows && levels.active_swing_lows.length > 0
        ? levels.active_swing_lows.map(sl =>
            `<span class="level-tag level-support">${formatNumber(sl.price, 2)}
             <span style="color:#64748b; font-size:11px">(${sl.date})</span></span>`
          ).join(' ')
        : '<span style="color:#64748b">None active</span>';

    // Active swing highs
    const swingHighsHtml = levels.active_swing_highs.length > 0
        ? levels.active_swing_highs.map(sh =>
            `<span class="level-tag level-resistance">${formatNumber(sh.price, 2)}
             <span style="color:#64748b; font-size:11px">(${sh.date})</span></span>`
          ).join(' ')
        : '<span style="color:#64748b">None active</span>';

    // Round levels (nearby only)
    const nearbyRoundLevels = levels.round_levels.filter(rl =>
        rl.price >= levels.current_price * 0.7 && rl.price <= levels.current_price * 1.3
    );
    const roundLevelsHtml = nearbyRoundLevels.length > 0
        ? nearbyRoundLevels.map(rl =>
            `<span class="level-tag level-round">${formatNumber(rl.price, 1)} (${rl.description})</span>`
          ).join(' ')
        : '<span style="color:#64748b">None in range</span>';

    // Manual levels with delete buttons
    const manualHtml = levels.manual_levels.length > 0
        ? levels.manual_levels.map(ml =>
            `<span class="level-tag level-manual">
                ${formatNumber(ml.price, 2)} — ${ml.description}
                <button class="level-delete-btn" data-level-id="${ml.id}" title="Delete">&times;</button>
            </span>`
          ).join(' ')
        : '<span style="color:#64748b">None set</span>';

    return `
    <div style="margin-top:16px; padding:16px; background:#1e293b; border-radius:8px;" id="levelsSection">
        <h4 style="margin:0 0 12px; color:#60a5fa">Key Levels</h4>
        <div style="display:grid; grid-template-columns:140px 1fr; gap:8px 16px; font-size:13px;">
            <div style="color:#94a3b8">Swing Lows</div>
            <div>${swingLowsHtml}</div>
            <div style="color:#94a3b8">Swing Highs</div>
            <div>${swingHighsHtml}</div>
            <div style="color:#94a3b8">Round Numbers</div>
            <div>${roundLevelsHtml}</div>
            <div style="color:#94a3b8">Manual Levels</div>
            <div id="manualLevelsDisplay">${manualHtml}</div>
        </div>

        <!-- Round Number Config -->
        <div style="margin-top:16px; padding-top:12px; border-top:1px solid #334155;">
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <span style="color:#94a3b8; font-size:12px;">Round increments (x1000 VND):</span>
                <input type="text" class="inline-input" id="roundIncrementsInput"
                       value="${currentIncrements}" style="width:120px; font-size:12px;"
                       placeholder="e.g. 10,50">
                <button class="btn btn-sm btn-primary" id="saveRoundIncrements">Save</button>
                <span id="roundConfigStatus" style="font-size:12px;"></span>
            </div>
        </div>

        <!-- Add Manual Level -->
        <div style="margin-top:12px; padding-top:12px; border-top:1px solid #334155;">
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <span style="color:#94a3b8; font-size:12px;">Add level:</span>
                <input type="number" step="0.01" class="inline-input" id="manualLevelPrice"
                       placeholder="Price" style="width:100px; font-size:12px;">
                <input type="text" class="inline-input" id="manualLevelDesc"
                       placeholder="Description" style="width:140px; font-size:12px;">
                <select class="inline-input" id="manualLevelType" style="font-size:12px; padding:5px 8px;">
                    <option value="support">Support</option>
                    <option value="resistance">Resistance</option>
                </select>
                <button class="btn btn-sm btn-primary" id="addManualLevel">Add</button>
                <span id="manualLevelStatus" style="font-size:12px;"></span>
            </div>
        </div>
    </div>`;
}


function bindLevelActions(panel, ticker, levels) {
    // Save round number config
    const saveBtn = panel.querySelector('#saveRoundIncrements');
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            const input = panel.querySelector('#roundIncrementsInput');
            const statusEl = panel.querySelector('#roundConfigStatus');
            const newValue = input.value.trim();

            if (!newValue) {
                statusEl.innerHTML = '<span style="color:#f87171">Enter values</span>';
                return;
            }

            try {
                await apiFetch('/api/config/round_number_increments', {
                    method: 'PUT',
                    body: JSON.stringify({ value: newValue }),
                });
                statusEl.innerHTML = '<span style="color:#4ade80">Saved! Reload detail to see changes.</span>';
                setTimeout(() => { statusEl.innerHTML = ''; }, 3000);
            } catch (error) {
                statusEl.innerHTML = `<span style="color:#f87171">Error: ${error.message}</span>`;
            }
        });
    }

    // Add manual level
    const addBtn = panel.querySelector('#addManualLevel');
    if (addBtn) {
        addBtn.addEventListener('click', async () => {
            const priceInput = panel.querySelector('#manualLevelPrice');
            const descInput = panel.querySelector('#manualLevelDesc');
            const typeSelect = panel.querySelector('#manualLevelType');
            const statusEl = panel.querySelector('#manualLevelStatus');
            const price = parseFloat(priceInput.value);

            if (!price || price <= 0) {
                statusEl.innerHTML = '<span style="color:#f87171">Enter a valid price</span>';
                return;
            }

            const description = descInput.value.trim() || `${typeSelect.value} level`;

            try {
                const result = await apiFetch(
                    `/api/levels/${ticker}/manual?price=${price}&description=${encodeURIComponent(description)}&level_type=${typeSelect.value}`,
                    { method: 'POST' }
                );

                // Add tag to display
                const display = panel.querySelector('#manualLevelsDisplay');
                const noneSpan = display.querySelector('span[style*="color:#64748b"]');
                if (noneSpan && noneSpan.textContent.includes('None')) {
                    display.innerHTML = '';
                }
                display.insertAdjacentHTML('beforeend',
                    `<span class="level-tag level-manual">
                        ${formatNumber(price, 2)} — ${description}
                        <button class="level-delete-btn" data-level-id="${result.id}" title="Delete">&times;</button>
                    </span>`
                );
                bindDeleteButtons(panel, ticker);

                priceInput.value = '';
                descInput.value = '';
                statusEl.innerHTML = '<span style="color:#4ade80">Added!</span>';
                setTimeout(() => { statusEl.innerHTML = ''; }, 2000);
            } catch (error) {
                statusEl.innerHTML = `<span style="color:#f87171">${error.message}</span>`;
            }
        });
    }

    // Bind delete buttons for existing manual levels
    bindDeleteButtons(panel, ticker);
}


function bindDeleteButtons(panel, ticker) {
    panel.querySelectorAll('.level-delete-btn').forEach(btn => {
        // Remove old listener by cloning
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);

        newBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const levelId = newBtn.dataset.levelId;
            if (!levelId) return;

            try {
                await apiFetch(`/api/levels/${ticker}/manual/${levelId}`, { method: 'DELETE' });
                const tag = newBtn.closest('.level-tag');
                if (tag) tag.remove();

                // If no more manual levels, show "None set"
                const display = panel.querySelector('#manualLevelsDisplay');
                if (display && display.querySelectorAll('.level-tag').length === 0) {
                    display.innerHTML = '<span style="color:#64748b">None set</span>';
                }
            } catch (error) {
                alert(`Failed to delete: ${error.message}`);
            }
        });
    });
}


function renderTickerChart(detail, levels) {
    const chartContainer = document.getElementById('tickerChart');
    if (!chartContainer) return;

    const tickerChart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: 400,
        layout: {
            background: { type: 'solid', color: '#0f172a' },
            textColor: '#d1d5db',
        },
        grid: {
            vertLines: { color: '#1e293b' },
            horzLines: { color: '#1e293b' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#334155',
        },
        timeScale: {
            borderColor: '#334155',
            timeVisible: false,
        },
    });

    // Candlestick series
    const candleSeries = tickerChart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: '#4ade80',
        downColor: '#f87171',
        borderDownColor: '#f87171',
        borderUpColor: '#4ade80',
        wickDownColor: '#f87171',
        wickUpColor: '#4ade80',
    });

    candleSeries.setData(detail.ohlcv);

    // --- Add price lines for levels ---
    const legendItems = [];

    // OHLCV is in x1000 VND, position prices are in raw VND
    const lastClose = detail.ohlcv[detail.ohlcv.length - 1]?.close || 1;
    const avgCost = detail.trade_summary?.avg_cost || 0;
    const scaleRatio = avgCost && avgCost > lastClose * 100 ? 1000 : 1;

    // Avg Cost line (convert to OHLCV scale)
    if (avgCost > 0) {
        const avgCostScaled = avgCost / scaleRatio;
        candleSeries.createPriceLine({
            price: avgCostScaled,
            color: '#38bdf8',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: 'Avg Cost',
        });
        legendItems.push({ color: '#38bdf8', label: 'Avg Cost' });
    }

    // Position avg_price lines (numbered #1, #2, ...)
    const chartActivePositions = detail.positions.filter(p => p.status === 'active' && p.avg_price > 0);
    chartActivePositions
        .sort((a, b) => a.avg_price - b.avg_price)
        .forEach((p, idx) => {
            const priceScaled = p.avg_price / scaleRatio;
            candleSeries.createPriceLine({
                price: priceScaled,
                color: '#fb923c',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: `#${idx + 1} (${p.remaining})`,
            });
        });
    if (chartActivePositions.length > 0) {
        legendItems.push({ color: '#fb923c', label: 'Position Avg Price' });
    }

    if (levels) {
        // Active Swing Lows
        const activeLows = levels.active_swing_lows || [];
        activeLows.forEach((sl, idx) => {
            candleSeries.createPriceLine({
                price: sl.price,
                color: '#4ade80',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: true,
                title: `SL${idx + 1}`,
            });
        });
        if (activeLows.length > 0) {
            legendItems.push({ color: '#4ade80', label: 'Swing Low (active)' });
        }

        // Active Swing Highs
        levels.active_swing_highs.forEach((sh, idx) => {
            candleSeries.createPriceLine({
                price: sh.price,
                color: '#f87171',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: true,
                title: `SH${idx + 1}`,
            });
        });
        if (levels.active_swing_highs.length > 0) {
            legendItems.push({ color: '#f87171', label: 'Swing High (active)' });
        }

        // Round number levels — within visible price range (±30%)
        const priceLow = levels.current_price * 0.7;
        const priceHigh = levels.current_price * 1.3;
        const visibleRoundLevels = levels.round_levels.filter(rl =>
            rl.price >= priceLow && rl.price <= priceHigh
        );
        visibleRoundLevels.forEach(rl => {
            candleSeries.createPriceLine({
                price: rl.price,
                color: '#fbbf24',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: false,
                title: '',
            });
        });
        if (visibleRoundLevels.length > 0) {
            legendItems.push({ color: '#fbbf24', label: 'Round Number' });
        }

        // Manual levels
        levels.manual_levels.forEach(ml => {
            candleSeries.createPriceLine({
                price: ml.price,
                color: '#c084fc',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: ml.description || 'Manual',
            });
        });
        if (levels.manual_levels.length > 0) {
            legendItems.push({ color: '#c084fc', label: 'Manual Level' });
        }
    }

    tickerChart.timeScale().fitContent();

    // Render legend
    const legendEl = document.getElementById('chartLegend');
    if (legendEl) {
        legendEl.innerHTML = legendItems.map(item =>
            `<span style="display:flex; align-items:center; gap:4px;">
                <span style="width:12px; height:3px; background:${item.color}; display:inline-block; border-radius:1px;"></span>
                ${item.label}
            </span>`
        ).join('');
    }

    // Resize observer
    const resizeObserver = new ResizeObserver(() => {
        tickerChart.applyOptions({ width: chartContainer.clientWidth });
    });
    resizeObserver.observe(chartContainer);

    // Cleanup when panel is removed
    const detailPanel = chartContainer.closest('.ticker-detail');
    if (detailPanel) {
        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                for (const node of mutation.removedNodes) {
                    if (node === detailPanel || node.contains?.(detailPanel)) {
                        resizeObserver.disconnect();
                        tickerChart.remove();
                        observer.disconnect();
                        return;
                    }
                }
            }
        });
        if (detailPanel.parentNode) {
            observer.observe(detailPanel.parentNode, { childList: true });
        }
    }
}
