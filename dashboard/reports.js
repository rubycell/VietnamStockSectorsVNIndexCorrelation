/* Reports Tab - Vietstock analysis reports */

registerTab('reports', async function initReportsTab() {
    const container = document.getElementById('tab-reports');
    showLoading(container);

    try {
        const data = await apiFetch('/api/reports');
        renderReports(container, data, 1);
    } catch (error) {
        showError(container, `Failed to load reports: ${error.message}`);
    }
});

function renderReports(container, data, currentPage) {
    const { reports, error } = data;

    if (error) {
        container.innerHTML = `
            <div class="panel-card">
                <div class="toolbar"><h2>Analysis Reports</h2></div>
                <div class="empty-state"><p>Error: ${error}</p></div>
            </div>`;
        return;
    }

    if (!reports || reports.length === 0) {
        container.innerHTML = `
            <div class="panel-card">
                <div class="toolbar"><h2>Analysis Reports</h2></div>
                <div class="empty-state"><p>No reports found.</p></div>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div class="panel-card">
            <div class="toolbar">
                <h2>Analysis Reports</h2>
                <div>
                    <span style="color:#64748b;font-size:12px;margin-right:12px">Vietstock + CafeF</span>
                    <button class="btn btn-primary" id="fetchNewReports">Fetch New</button>
                    <button class="btn" id="refreshReports">Refresh</button>
                </div>
            </div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width:45%">Report</th>
                        <th>Ticker</th>
                        <th>Broker</th>
                        <th>Date</th>
                        <th>From</th>
                        <th class="text-right">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${reports.map(r => {
                        const srcBadge = r.report_source === 'cafef'
                            ? '<span style="background:#92400e;color:#fde68a;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600">CafeF</span>'
                            : '<span style="background:#1e3a5f;color:#93c5fd;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600">VS</span>';
                        return `
                        <tr>
                            <td>
                                <a href="${r.detail_url}" target="_blank" rel="noopener"
                                   style="color:#e2e8f0;text-decoration:none;font-weight:500">
                                    ${r.title}
                                </a>
                            </td>
                            <td><span style="color:#4ade80;font-weight:600">${r.ticker || '-'}</span></td>
                            <td><span style="color:#60a5fa;font-weight:500">${r.source || '-'}</span></td>
                            <td style="white-space:nowrap">${r.date || '-'}</td>
                            <td>${srcBadge}</td>
                            <td class="text-right" style="white-space:nowrap">
                                ${r.download_url
                                    ? `<a class="btn btn-sm" href="${r.download_url}" target="_blank" rel="noopener">PDF</a>`
                                    : ''}
                                <button class="btn btn-sm btn-primary analyze-btn" data-edoc="${r.edoc_id}" style="margin-left:4px">Analyze</button>
                            </td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
            <div style="display:flex;justify-content:center;align-items:center;gap:12px;margin-top:16px">
                ${currentPage > 1 ? '<button class="btn" id="prevPage">Previous</button>' : ''}
                <span style="color:#64748b;font-size:13px">Page ${currentPage}</span>
                ${reports.length >= 5 ? '<button class="btn" id="nextPage">Next</button>' : ''}
            </div>
        </div>
        <div id="analysisResult" class="panel-card" style="display:none;margin-top:16px">
            <div class="toolbar">
                <h2 id="analysisTitle">Analysis</h2>
                <button class="btn btn-sm" id="closeAnalysis">Close</button>
            </div>
            <div id="analysisContent" style="white-space:pre-wrap;line-height:1.7;color:#e2e8f0"></div>
        </div>
    `;

    document.getElementById('fetchNewReports').addEventListener('click', async () => {
        const btn = document.getElementById('fetchNewReports');
        btn.disabled = true;
        btn.textContent = 'Fetching...';
        try {
            const result = await apiFetch('/api/reports/fetch', { method: 'POST' });
            const msg = `Found ${result.new_reports} new report(s)`;
            btn.textContent = msg;
            setTimeout(() => { btn.textContent = 'Fetch New'; btn.disabled = false; }, 3000);
            const freshData = await apiFetch('/api/reports');
            renderReports(container, freshData, 1);
        } catch (err) {
            btn.textContent = 'Fetch New';
            btn.disabled = false;
            showError(container, 'Failed to fetch: ' + err.message);
        }
    });

    document.querySelectorAll('.analyze-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const edocId = btn.dataset.edoc;
            const resultPanel = document.getElementById('analysisResult');
            const titleEl = document.getElementById('analysisTitle');
            const contentEl = document.getElementById('analysisContent');

            btn.disabled = true;
            btn.textContent = 'Analyzing...';
            resultPanel.style.display = 'block';
            titleEl.textContent = 'Analyzing...';
            contentEl.textContent = 'Sending report to NotebookLM. This may take 30-60 seconds...';
            resultPanel.scrollIntoView({ behavior: 'smooth' });

            try {
                const result = await apiFetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ edoc_id: edocId }),
                });
                titleEl.textContent = `Analysis: ${result.title}`;
                contentEl.textContent = result.answer;
            } catch (err) {
                titleEl.textContent = 'Analysis Failed';
                contentEl.textContent = err.message;
            } finally {
                btn.textContent = 'Analyze';
                btn.disabled = false;
            }
        });
    });

    document.getElementById('closeAnalysis').addEventListener('click', () => {
        document.getElementById('analysisResult').style.display = 'none';
    });

    document.getElementById('refreshReports').addEventListener('click', async () => {
        showLoading(container);
        try {
            const freshData = await apiFetch('/api/reports?page=' + currentPage);
            renderReports(container, freshData, currentPage);
        } catch (err) {
            showError(container, 'Failed to refresh: ' + err.message);
        }
    });

    const prevBtn = document.getElementById('prevPage');
    if (prevBtn) {
        prevBtn.addEventListener('click', async () => {
            showLoading(container);
            try {
                const prevData = await apiFetch('/api/reports?page=' + (currentPage - 1));
                renderReports(container, prevData, currentPage - 1);
            } catch (err) {
                showError(container, 'Failed to load page: ' + err.message);
            }
        });
    }

    const nextBtn = document.getElementById('nextPage');
    if (nextBtn) {
        nextBtn.addEventListener('click', async () => {
            showLoading(container);
            try {
                const nextData = await apiFetch('/api/reports?page=' + (currentPage + 1));
                renderReports(container, nextData, currentPage + 1);
            } catch (err) {
                showError(container, 'Failed to load page: ' + err.message);
            }
        });
    }
}
