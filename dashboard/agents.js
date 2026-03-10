/* Agents Tab - List, toggle, and execute AI agents */

registerTab('agents', async function initAgentsTab() {
    const container = document.getElementById('tab-agents');
    showLoading(container);

    try {
        const agents = await apiFetch('/api/agents');
        renderAgents(container, agents);
    } catch (error) {
        showError(container, `Failed to load agents: ${error.message}`);
    }
});

function renderAgents(container, agents) {
    if (!agents || agents.length === 0) {
        showEmpty(container, 'No agents configured.');
        return;
    }

    container.innerHTML = `
        <div class="panel-card">
            <div class="toolbar">
                <h2>AI Agents (${agents.length})</h2>
                <button class="btn btn-primary" id="refreshAgents">Refresh</button>
            </div>
            <div style="overflow-x: auto;">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Type</th>
                            <th>Schedule</th>
                            <th>Enabled</th>
                            <th>Alert</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="agentsTableBody">
                        ${agents.map(a => agentRow(a)).join('')}
                    </tbody>
                </table>
            </div>
        </div>
        <div class="panel-card" id="agentExecutionResult" style="display: none;">
            <h2>Execution Result</h2>
            <pre id="agentResultContent" style="color: #e2e8f0; font-size: 13px; white-space: pre-wrap; overflow-x: auto;"></pre>
        </div>
    `;

    document.getElementById('refreshAgents').addEventListener('click', async () => {
        showLoading(container);
        try {
            const freshAgents = await apiFetch('/api/agents');
            renderAgents(container, freshAgents);
        } catch (error) {
            showError(container, `Failed to refresh: ${error.message}`);
        }
    });

    bindAgentActions(container);
}

function agentRow(agent) {
    return `
        <tr data-agent-id="${agent.id}">
            <td>
                <strong>${agent.name}</strong>
                ${agent.description ? `<br><span style="color: #64748b; font-size: 12px;">${agent.description}</span>` : ''}
            </td>
            <td><span style="color: #94a3b8; font-size: 12px;">${agent.agent_type}</span></td>
            <td>${agent.schedule || '-'}</td>
            <td>
                <label class="toggle">
                    <input type="checkbox" class="agent-toggle" data-id="${agent.id}" ${agent.enabled ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </td>
            <td>${agent.alert_on_result ? 'Yes' : 'No'}</td>
            <td>
                <button class="btn btn-primary btn-sm agent-execute" data-id="${agent.id}">Run</button>
            </td>
        </tr>
    `;
}

function bindAgentActions(container) {
    container.querySelectorAll('.agent-toggle').forEach(toggle => {
        toggle.addEventListener('change', async (e) => {
            const agentId = e.target.dataset.id;
            const enabled = e.target.checked;
            try {
                await apiFetch(`/api/agents/${agentId}`, {
                    method: 'PUT',
                    body: JSON.stringify({ enabled }),
                });
            } catch (error) {
                e.target.checked = !enabled;
                alert(`Failed to update agent: ${error.message}`);
            }
        });
    });

    container.querySelectorAll('.agent-execute').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const agentId = e.target.dataset.id;
            const resultPanel = document.getElementById('agentExecutionResult');
            const resultContent = document.getElementById('agentResultContent');

            e.target.disabled = true;
            e.target.textContent = '...';
            resultPanel.style.display = 'block';
            resultContent.textContent = `Running agent ${agentId}...`;

            try {
                const result = await apiFetch(`/api/agents/${agentId}/execute`, {
                    method: 'POST',
                    body: JSON.stringify({}),
                });
                resultContent.textContent = JSON.stringify(result, null, 2);
            } catch (error) {
                resultContent.textContent = `Error: ${error.message}`;
            } finally {
                e.target.disabled = false;
                e.target.textContent = 'Run';
            }
        });
    });
}
