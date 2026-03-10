/* Config Tab - View and edit key-value configuration */

registerTab('config', async function initConfigTab() {
    const container = document.getElementById('tab-config');
    showLoading(container);

    try {
        const configs = await apiFetch('/api/config');
        renderConfig(container, configs);
    } catch (error) {
        showError(container, `Failed to load config: ${error.message}`);
    }
});

function renderConfig(container, configs) {
    container.innerHTML = `
        <div class="panel-card">
            <div class="toolbar">
                <h2>Configuration</h2>
                <button class="btn btn-primary" id="refreshConfig">Refresh</button>
            </div>
            <div style="overflow-x: auto;">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Key</th>
                            <th>Value</th>
                            <th>Description</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="configTableBody">
                        ${configs.map(c => configRow(c)).join('')}
                    </tbody>
                </table>
            </div>
            <div style="margin-top: 16px; display: flex; gap: 8px; align-items: center;">
                <input type="text" class="inline-input" id="newConfigKey" placeholder="Key" style="width: 150px;">
                <input type="text" class="inline-input" id="newConfigValue" placeholder="Value" style="width: 200px;">
                <input type="text" class="inline-input" id="newConfigDesc" placeholder="Description (optional)" style="width: 200px;">
                <button class="btn btn-primary" id="addConfig">Add</button>
            </div>
            <div id="configStatus"></div>
        </div>
    `;

    document.getElementById('refreshConfig').addEventListener('click', async () => {
        showLoading(container);
        try {
            const freshConfigs = await apiFetch('/api/config');
            renderConfig(container, freshConfigs);
        } catch (error) {
            showError(container, `Failed to refresh: ${error.message}`);
        }
    });

    document.getElementById('addConfig').addEventListener('click', addConfigEntry);
    bindConfigActions();
}

function configRow(config) {
    return `
        <tr data-key="${config.key}">
            <td><code style="color: #93c5fd;">${config.key}</code></td>
            <td>
                <span class="config-display">${config.value || '-'}</span>
                <input type="text" class="inline-input config-edit" value="${escapeHtml(config.value || '')}" style="display: none; width: 200px;">
            </td>
            <td style="color: #94a3b8; font-size: 12px;">${config.description || '-'}</td>
            <td>
                <button class="btn btn-sm btn-primary config-edit-btn" data-key="${config.key}">Edit</button>
                <button class="btn btn-sm btn-primary config-save-btn" data-key="${config.key}" style="display: none;">Save</button>
            </td>
        </tr>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function bindConfigActions() {
    document.querySelectorAll('.config-edit-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const row = e.target.closest('tr');
            row.querySelector('.config-display').style.display = 'none';
            row.querySelector('.config-edit').style.display = 'inline-block';
            e.target.style.display = 'none';
            row.querySelector('.config-save-btn').style.display = 'inline-block';
        });
    });

    document.querySelectorAll('.config-save-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const key = e.target.dataset.key;
            const row = e.target.closest('tr');
            const input = row.querySelector('.config-edit');
            const newValue = input.value;

            e.target.disabled = true;
            try {
                await apiFetch(`/api/config/${encodeURIComponent(key)}`, {
                    method: 'PUT',
                    body: JSON.stringify({ value: newValue }),
                });

                const display = row.querySelector('.config-display');
                display.textContent = newValue || '-';
                display.style.display = 'inline';
                input.style.display = 'none';
                e.target.style.display = 'none';
                row.querySelector('.config-edit-btn').style.display = 'inline-block';
            } catch (error) {
                alert(`Failed to save: ${error.message}`);
            } finally {
                e.target.disabled = false;
            }
        });
    });
}

async function addConfigEntry() {
    const key = document.getElementById('newConfigKey').value.trim();
    const value = document.getElementById('newConfigValue').value.trim();
    const description = document.getElementById('newConfigDesc').value.trim();
    const statusEl = document.getElementById('configStatus');

    if (!key) {
        statusEl.innerHTML = '<div class="status-message status-error">Key is required.</div>';
        return;
    }

    try {
        const body = { value };
        if (description) body.description = description;

        await apiFetch(`/api/config/${encodeURIComponent(key)}`, {
            method: 'PUT',
            body: JSON.stringify(body),
        });

        const tbody = document.getElementById('configTableBody');
        tbody.insertAdjacentHTML('beforeend', configRow({ key, value, description }));
        bindConfigActions();

        document.getElementById('newConfigKey').value = '';
        document.getElementById('newConfigValue').value = '';
        document.getElementById('newConfigDesc').value = '';
        statusEl.innerHTML = '<div class="status-message status-success">Config added.</div>';
        setTimeout(() => { statusEl.innerHTML = ''; }, 3000);
    } catch (error) {
        statusEl.innerHTML = `<div class="status-message status-error">Failed: ${error.message}</div>`;
    }
}
