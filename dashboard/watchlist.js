/* Watchlist Tab — tickers to track (not necessarily held) */

registerTab('watchlist', async function initWatchlistTab() {
    const container = document.getElementById('tab-watchlist');
    showLoading(container);
    try {
        await renderWatchlistTab(container);
    } catch (error) {
        showError(container, `Failed to load watchlist: ${error.message}`);
    }
});

async function renderWatchlistTab(container) {
    const [watchlistData, notebookData] = await Promise.all([
        apiFetch('/api/watchlist'),
        apiFetch('/api/watchlist/notebook-tickers'),
    ]);

    container.innerHTML = `
        <div class="panel-card">
            <div class="toolbar">
                <h2>Watchlist</h2>
                <span style="color:#64748b;font-size:12px">Tickers that receive NotebookLM notebooks</span>
            </div>

            <!-- Add form -->
            <div style="display:flex;gap:8px;margin-bottom:16px;align-items:flex-end">
                <div>
                    <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px">Ticker</label>
                    <input id="wl-ticker-input" type="text" placeholder="e.g. VRE"
                        style="width:120px;padding:6px 10px;background:#1e293b;border:1px solid #334155;
                               border-radius:6px;color:#f1f5f9;font-size:14px;text-transform:uppercase">
                </div>
                <div style="flex:1">
                    <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px">Notes (optional)</label>
                    <input id="wl-notes-input" type="text" placeholder="e.g. Watching for breakout"
                        style="width:100%;padding:6px 10px;background:#1e293b;border:1px solid #334155;
                               border-radius:6px;color:#f1f5f9;font-size:14px">
                </div>
                <button id="wl-add-btn" class="btn btn-primary">Add</button>
            </div>

            <!-- Watchlist table -->
            ${renderWatchlistTable(watchlistData)}
        </div>

        <!-- Notebook Tickers section -->
        <div class="panel-card" style="margin-top:16px">
            <div class="toolbar">
                <h2>Notebook Tickers</h2>
                <span style="color:#64748b;font-size:12px">
                    ${notebookData.portfolio_count} holdings + ${notebookData.watchlist_count} watchlist
                    = <strong style="color:#94a3b8">${notebookData.total} total</strong>
                </span>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;padding:4px 0">
                ${notebookData.notebook_tickers.map(ticker =>
                    `<span style="background:#1e293b;border:1px solid #334155;border-radius:4px;
                                  padding:3px 8px;font-size:12px;color:#94a3b8;font-family:monospace">
                        ${ticker}
                    </span>`
                ).join('')}
            </div>
            ${notebookData.total === 0 ? '<p style="color:#64748b;font-size:13px">No holdings or watchlist items yet.</p>' : ''}
        </div>
    `;

    // Add button handler
    document.getElementById('wl-add-btn').addEventListener('click', async () => {
        const tickerInput = document.getElementById('wl-ticker-input');
        const notesInput = document.getElementById('wl-notes-input');
        const ticker = tickerInput.value.trim().toUpperCase();
        if (!ticker) return;

        try {
            await apiFetch('/api/watchlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker, notes: notesInput.value.trim() }),
            });
            tickerInput.value = '';
            notesInput.value = '';
            await renderWatchlistTab(container);
        } catch (error) {
            alert(`Failed to add ${ticker}: ${error.message}`);
        }
    });

    // Allow Enter key to submit
    document.getElementById('wl-ticker-input').addEventListener('keydown', (event) => {
        if (event.key === 'Enter') document.getElementById('wl-add-btn').click();
    });

    // Delete button handlers (event delegation)
    container.addEventListener('click', async (event) => {
        const deleteButton = event.target.closest('[data-delete-ticker]');
        if (!deleteButton) return;
        const ticker = deleteButton.dataset.deleteTicker;
        if (!confirm(`Remove ${ticker} from watchlist?`)) return;
        try {
            await apiFetch(`/api/watchlist/${ticker}`, { method: 'DELETE' });
            await renderWatchlistTab(container);
        } catch (error) {
            alert(`Failed to remove ${ticker}: ${error.message}`);
        }
    });
}

function renderWatchlistTable(items) {
    if (!items || items.length === 0) {
        return '<div class="empty-state"><p>No watchlist items yet. Add a ticker above.</p></div>';
    }

    const rows = items.map(item => {
        const addedDate = item.added_at ? item.added_at.slice(0, 10) : '—';
        return `
            <tr>
                <td><strong style="font-family:monospace">${item.ticker}</strong></td>
                <td style="color:#94a3b8">${item.notes || '—'}</td>
                <td style="color:#64748b;font-size:12px">${addedDate}</td>
                <td class="text-right">
                    <button class="btn" data-delete-ticker="${item.ticker}"
                        style="color:#ef4444;border-color:#ef444444">Remove</button>
                </td>
            </tr>`;
    }).join('');

    return `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Notes</th>
                    <th>Added</th>
                    <th class="text-right">Actions</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>`;
}
