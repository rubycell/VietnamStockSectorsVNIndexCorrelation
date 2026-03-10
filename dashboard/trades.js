/* Trades Tab - TCBS XLSX Upload */

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
        <div class="panel-card" id="uploadHistory">
            <h2>Recent Uploads</h2>
            <div id="uploadHistoryContent">
                <div class="empty-state"><p>Upload a file to see results here.</p></div>
            </div>
        </div>
    `;

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
