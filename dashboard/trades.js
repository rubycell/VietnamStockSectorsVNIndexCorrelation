/* Trades Tab - TCBS XLSX Upload + Portfolio Snapshot Import */

registerTab('trades', function initTradesTab() {
    const container = document.getElementById('tab-trades');

    container.innerHTML = `
        <div class="panel-card">
            <h2>Upload TCBS Trade History</h2>
            <p style="color: #94a3b8; margin-bottom: 16px;">
                Upload your TCBS trade history XLSX file. Supports both margin and normal accounts.
            </p>
            <div class="upload-area" id="uploadArea">
                <p style="font-size: 1.5rem; margin-bottom: 8px;">&#128196;</p>
                <p>Drag & drop XLSX file here or click to browse</p>
                <input type="file" id="fileInput" accept=".xlsx,.xls" style="display: none;">
            </div>
            <div id="uploadStatus"></div>
        </div>

        <div class="panel-card">
            <h2>Import Portfolio Snapshot</h2>
            <p style="color: #94a3b8; margin-bottom: 16px;">
                Paste your broker's portfolio table (markdown or CSV). This sets your current positions and overwrites previous snapshot data.
            </p>
            <textarea id="snapshotInput" class="inline-input" style="width:100%; height:200px; resize:vertical; font-family:monospace; font-size:12px;"
                placeholder="| ACB 23.20 | 1,150 Được GD 1,150 ... | 19,397 | 26,680,000 | +4,373,450 ... | 0 | 0 | 0 | 0 | 0 | 0 |"></textarea>
            <div style="display:flex; gap:8px; margin-top:12px; align-items:center;">
                <button class="btn btn-primary" id="importSnapshotBtn">Import Snapshot</button>
                <span id="snapshotStatus" style="font-size:13px;"></span>
            </div>
            <div id="snapshotResult" style="margin-top:12px;"></div>
        </div>

        <div class="panel-card" id="uploadHistory">
            <h2>Recent Uploads</h2>
            <div id="uploadHistoryContent">
                <div class="empty-state"><p>Upload a file to see results here.</p></div>
            </div>
        </div>
    `;

    // --- TCBS Upload ---
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadStatus = document.getElementById('uploadStatus');

    uploadArea.addEventListener('click', () => fileInput.click());

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) uploadFile(file, uploadStatus);
    });

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) uploadFile(file, uploadStatus);
    });

    // --- Snapshot Import ---
    const importBtn = document.getElementById('importSnapshotBtn');
    const snapshotInput = document.getElementById('snapshotInput');
    const snapshotStatus = document.getElementById('snapshotStatus');
    const snapshotResult = document.getElementById('snapshotResult');

    importBtn.addEventListener('click', async () => {
        const text = snapshotInput.value.trim();
        if (!text) {
            snapshotStatus.innerHTML = '<span style="color:#f87171">Paste your portfolio table first.</span>';
            return;
        }

        importBtn.disabled = true;
        snapshotStatus.innerHTML = '<span style="color:#94a3b8">Importing...</span>';

        try {
            const result = await apiFetch('/api/import-snapshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
            });

            const cleanedMsg = result.cleaned && result.cleaned.length > 0
                ? ` Cleaned ${result.cleaned.length} sold-out: ${result.cleaned.join(', ')}`
                : '';
            snapshotStatus.innerHTML = `<span style="color:#4ade80">Imported ${result.imported} tickers.${cleanedMsg}</span>`;

            // Show results table
            const rows = result.tickers.map(t =>
                `<tr>
                    <td>${t.ticker}</td>
                    <td class="text-right">${formatNumber(t.shares)}</td>
                    <td class="text-right">${formatNumber(t.avg_cost)}</td>
                    <td class="text-right">${formatNumber(t.current_price)}</td>
                </tr>`
            ).join('');

            snapshotResult.innerHTML = `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th class="text-right">Shares</th>
                            <th class="text-right">Avg Cost</th>
                            <th class="text-right">Current Price</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `;

            // Log to history
            const historyContent = document.getElementById('uploadHistoryContent');
            const entry = document.createElement('div');
            entry.style.cssText = 'padding: 8px 0; border-bottom: 1px solid #1e293b; color: #e2e8f0; font-size: 13px;';
            entry.textContent = `${new Date().toLocaleString()} — Snapshot: ${result.imported} tickers imported`;
            historyContent.prepend(entry);
        } catch (error) {
            snapshotStatus.innerHTML = `<span style="color:#f87171">Import failed: ${error.message}</span>`;
        } finally {
            importBtn.disabled = false;
        }
    });
});

async function uploadFile(file, statusContainer) {
    if (!file.name.match(/\.xlsx?$/i)) {
        statusContainer.innerHTML = '<div class="status-message status-error">Please upload an XLSX or XLS file.</div>';
        return;
    }

    statusContainer.innerHTML = '<div class="loading">Uploading</div>';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData,
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || 'Upload failed');
        }

        statusContainer.innerHTML = `
            <div class="status-message status-success">
                <strong>Upload successful!</strong><br>
                Account type: ${result.account_type}<br>
                Fills imported: ${result.fills_imported}<br>
                Fills skipped (duplicates): ${result.fills_skipped}<br>
                Invalid rows: ${result.invalid_rows}
            </div>
        `;

        const historyContent = document.getElementById('uploadHistoryContent');
        const entry = document.createElement('div');
        entry.style.cssText = 'padding: 8px 0; border-bottom: 1px solid #1e293b; color: #e2e8f0; font-size: 13px;';
        entry.textContent = `${new Date().toLocaleString()} — ${file.name}: ${result.fills_imported} fills imported (${result.account_type})`;
        historyContent.innerHTML = '';
        historyContent.prepend(entry);
    } catch (error) {
        statusContainer.innerHTML = `<div class="status-message status-error">Upload failed: ${error.message}</div>`;
    }
}
