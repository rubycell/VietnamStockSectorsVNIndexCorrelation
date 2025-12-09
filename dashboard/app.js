let chart = null;
let vnindexSeries = null;
let indicatorSeries = null;
let dashboardData = null;

document.addEventListener('DOMContentLoaded', async () => {
    const sectorSelect = document.getElementById('sectorSelect');
    const indicatorSelect = document.getElementById('indicatorSelect');
    const chartContainer = document.getElementById('chart');

    // Fetch Data
    try {
        const response = await fetch('data.json');
        dashboardData = await response.json();
    } catch (e) {
        console.error("Failed to load data.json", e);
        alert("Error loading data. Make sure server is running.");
        return;
    }

    const { dates, vnindex, sectors } = dashboardData;

    // Populate Sector Select
    sectorSelect.innerHTML = '';
    const sectorNames = Object.keys(sectors).sort();

    sectorNames.forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        sectorSelect.appendChild(option);
    });

    // Create Chart (v5 API)
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

    // VN-Index Series (Left Axis) - v5 API
    vnindexSeries = chart.addSeries(LightweightCharts.LineSeries, {
        color: '#3b82f6',
        lineWidth: 2,
        priceScaleId: 'left',
    });

    // Indicator Series (Right Axis) - v5 API
    indicatorSeries = chart.addSeries(LightweightCharts.AreaSeries, {
        topColor: 'rgba(251, 146, 60, 0.5)',
        bottomColor: 'rgba(251, 146, 60, 0.05)',
        lineColor: '#fb923c',
        lineWidth: 2,
        priceScaleId: 'right',
    });

    // Set defaults
    const defaultSector = sectorNames.includes('Ngân hàng') ? 'Ngân hàng' : sectorNames[0];
    sectorSelect.value = defaultSector;
    indicatorSelect.value = 'stoch_20';

    // Initial Plot
    updateChart(defaultSector, 'stoch_20');

    // Event Listeners
    sectorSelect.addEventListener('change', () => {
        updateChart(sectorSelect.value, indicatorSelect.value);
    });

    indicatorSelect.addEventListener('change', () => {
        updateChart(sectorSelect.value, indicatorSelect.value);
    });

    // Handle Resize
    window.addEventListener('resize', () => {
        chart.applyOptions({ width: chartContainer.clientWidth });
    });

    // Fullscreen toggle
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
        if (!document.fullscreenElement) {
            chart.applyOptions({ width: chartContainer.clientWidth, height: 500 });
        }
    });
});

function updateChart(sectorName, indicatorKey) {
    const { dates, vnindex, sectors } = dashboardData;
    const sectorData = sectors[sectorName];
    if (!sectorData) return;

    const indicatorData = sectorData[indicatorKey];
    if (!indicatorData) return;

    // Format data for Lightweight Charts
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
