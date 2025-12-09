# Vietnam Stock Sectors VNINDEX Correlation
Feel free to edit and use this code for your own purposes.

## Overview
This project provides an interactive web dashboard that visualises Vietnamese stock market data. It:
- Fetches historical price data for the VN‑Index and sector stocks.
- Calculates three indicators per sector:
  - Stochastic Oscillator (threshold < 20)
  - Stochastic Momentum Index (SMI < ‑40)
  - 50‑day Simple Moving Average (price < SMA‑50)
- Exports the data to `dashboard/data.json`.
- Displays the data in a browser using **TradingView Lightweight Charts** with a dark theme, dual‑axis (VN‑Index on the left, indicator on the right), sector and indicator selectors, and a fullscreen mode.

## Project Structure
```
project_root/
├─ data/                     # Cached CSV data for stocks & sectors
├─ dashboard/
│   ├─ index.html           # Main page UI
│   ├─ style.css            # Styling (dark theme, responsive)
│   ├─ app.js               # Front‑end logic, chart setup
│   └─ data.json            # Generated data for the dashboard
├─ export_web_data.py        # Generates data.json from cached CSVs
├─ analyze_all_sectors.py    # Runs analysis for every sector
├─ cache_sectors.py          # Caches sector definitions
└─ README.md                # **You are reading it**
```

## Prerequisites
- Python 3.9+ with packages: `vnstock`, `pandas`, `numpy` (install via `pip install -r requirements.txt` if you have a `requirements.txt`).
- Node/npm is **not** required; the frontend uses only CDN‑served JavaScript.
- A modern browser (Chrome, Firefox, Edge) for the dashboard.

## Setup & Usage
1. **Install Python dependencies**
   ```bash
   pip install vnstock pandas numpy
   ```
2. **Cache sector data** (run once or when you need updates)
   ```bash
   python cache_sectors.py
   ```
3. **Run the full sector analysis** (populates `data/` with CSVs)
   ```bash
   python analyze_all_sectors.py
   ```
4. **Export data for the dashboard**
   ```bash
   python export_web_data.py
   ```
   This creates/overwrites `dashboard/data.json`.
5. **Start the local server**
   ```bash
   cd dashboard
   python -m http.server 8000
   ```
6. **Open the dashboard**
   Navigate to `http://localhost:8000` in your browser.
   - Use the **Sector** dropdown to pick a sector.
   - Use the **Indicator** dropdown to switch between the three indicators.
   - Click the **⛶** button to toggle fullscreen mode.

## Customisation
- **Add new indicators**: Extend `export_web_data.py` with additional calculations and update the `indicators` mapping.
- **Change chart style**: Edit `dashboard/style.css` or modify the chart options in `app.js`.
- **Deploy**: Serve the `dashboard/` folder with any static‑file web server (e.g., Nginx, GitHub Pages).

## License
This project is provided under the MIT License. Feel free to modify and redistribute.
