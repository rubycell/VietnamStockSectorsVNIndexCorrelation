/* global LightweightCharts */

let chart = null;
let vnindexSeries = null;
let indicatorSeries = null;
let dashboardData = null;

// ── Tab Router ──────────────────────────────────────────────────

const tabModules = {};
const loadedTabs = new Set();

function initTabRouter() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.dataset.tab;

            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            button.classList.add('active');
            document.getElementById(`tab-${tabName}`).classList.add('active');

            if (!loadedTabs.has(tabName) && tabModules[tabName]) {
                loadedTabs.add(tabName);
                tabModules[tabName]();
            }

            if (tabName === 'sectors' && chart) {
                setTimeout(() => {
                    const chartContainer = document.getElementById('chart');
                    chart.applyOptions({ width: chartContainer.clientWidth });
                }, 50);
            }
        });
    });

    loadedTabs.add('sectors');
}

function registerTab(name, initFunction) {
    tabModules[name] = initFunction;
}

// ── API Helper ──────────────────────────────────────────────────

async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error ${response.status}: ${errorText}`);
    }
    if (response.status === 204) return null;
    return response.json();
}

function formatNumber(value, decimals = 0) {
    if (value == null || isNaN(value)) return '-';
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);
}

function formatCurrency(value) {
    if (value == null || isNaN(value)) return '-';
    return formatNumber(value, 0) + ' VND';
}

function pnlClass(value) {
    if (value > 0) return 'positive';
    if (value < 0) return 'negative';
    return '';
}

function severityBadge(severity) {
    const cls = severity === 'CRITICAL' ? 'severity-critical'
        : severity === 'WARNING' ? 'severity-warning'
        : 'severity-info';
    return `<span class="severity-badge ${cls}">${severity}</span>`;
}

function showLoading(container) {
    container.innerHTML = '<div class="loading">Loading</div>';
}

function showError(container, message) {
    container.innerHTML = `<div class="status-message status-error">${message}</div>`;
}

function showEmpty(container, message) {
    container.innerHTML = `<div class="empty-state"><p>${message}</p></div>`;
}

// ── Sectors Tab (existing chart logic) ──────────────────────────

async function initSectorsTab() {
    const sectorSelect = document.getElementById('sectorSelect');
    const indicatorSelect = document.getElementById('indicatorSelect');
    const chartContainer = document.getElementById('chart');

    try {
        const response = await fetch('data.json');
        dashboardData = await response.json();
    } catch (e) {
        console.error("Failed to load data.json", e);
        return;
    }

    const { sectors } = dashboardData;

    sectorSelect.innerHTML = '';
    const sectorNames = Object.keys(sectors).sort();

    sectorNames.forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        sectorSelect.appendChild(option);
    });

    chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: 500,
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
            visible: true,
        },
        leftPriceScale: {
            visible: true,
            borderColor: '#334155',
        },
        timeScale: {
            borderColor: '#334155',
            timeVisible: true,
        },
    });

    vnindexSeries = chart.addSeries(LightweightCharts.LineSeries, {
        color: '#3b82f6',
        lineWidth: 2,
        priceScaleId: 'left',
    });

    indicatorSeries = chart.addSeries(LightweightCharts.AreaSeries, {
        topColor: 'rgba(251, 146, 60, 0.5)',
        bottomColor: 'rgba(251, 146, 60, 0.05)',
        lineColor: '#fb923c',
        lineWidth: 2,
        priceScaleId: 'right',
    });

    const defaultSector = sectorNames.includes('Ngân hàng') ? 'Ngân hàng' : sectorNames[0];
    sectorSelect.value = defaultSector;
    indicatorSelect.value = 'stoch_20';

    updateChart(defaultSector, 'stoch_20');

    sectorSelect.addEventListener('change', () => {
        updateChart(sectorSelect.value, indicatorSelect.value);
    });

    indicatorSelect.addEventListener('change', () => {
        updateChart(sectorSelect.value, indicatorSelect.value);
    });

    window.addEventListener('resize', () => {
        if (chart) {
            chart.applyOptions({ width: chartContainer.clientWidth });
        }
    });

    const fullscreenBtn = document.getElementById('fullscreenBtn');
    const chartContainerEl = document.getElementById('chartContainer');

    fullscreenBtn.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            chartContainerEl.requestFullscreen().then(() => {
                setTimeout(() => {
                    chart.applyOptions({
                        width: chartContainerEl.clientWidth - 40,
                        height: window.innerHeight - 80
                    });
                }, 100);
            });
        } else {
            document.exitFullscreen().then(() => {
                setTimeout(() => {
                    chart.applyOptions({
                        width: chartContainer.clientWidth,
                        height: 500
                    });
                }, 100);
            });
        }
    });

    document.addEventListener('fullscreenchange', () => {
        if (!document.fullscreenElement && chart) {
            chart.applyOptions({ width: chartContainer.clientWidth, height: 500 });
        }
    });
}

function updateChart(sectorName, indicatorKey) {
    if (!dashboardData) return;
    const { dates, vnindex, sectors } = dashboardData;
    const sectorData = sectors[sectorName];
    if (!sectorData) return;

    const indicatorData = sectorData[indicatorKey];
    if (!indicatorData) return;

    const vnindexData = [];
    const indicatorChartData = [];

    for (let i = 0; i < dates.length; i++) {
        const vn = vnindex[i];
        const ind = indicatorData[i];

        if (dates[i] && typeof vn === 'number' && !isNaN(vn) && vn > 0) {
            vnindexData.push({ time: dates[i], value: vn });
        }

        if (dates[i] && typeof ind === 'number' && !isNaN(ind)) {
            indicatorChartData.push({ time: dates[i], value: ind });
        }
    }

    vnindexSeries.setData(vnindexData);
    indicatorSeries.setData(indicatorChartData);
    chart.timeScale().fitContent();
}

// ── Init ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initTabRouter();
    initSectorsTab();
});
