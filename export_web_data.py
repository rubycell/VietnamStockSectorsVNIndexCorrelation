import pandas as pd
import json
import os
from datetime import datetime, timedelta
from vnstock import Quote, Listing
import warnings
import numpy as np

warnings.filterwarnings("ignore")

CACHE_DIR = 'data/1D'
DASHBOARD_DIR = 'dashboard'
DATA_FILE = os.path.join(DASHBOARD_DIR, 'data.json')

if not os.path.exists(DASHBOARD_DIR):
    os.makedirs(DASHBOARD_DIR)

def get_sector_stocks(sector_name, limit=20):
    try:
        listing = Listing(source='VCI')
        df_ind = listing.symbols_by_industries()
        if 'icb_name2' not in df_ind.columns: return []
        sector_stocks = df_ind[df_ind['icb_name2'] == sector_name]
        return sector_stocks['symbol'].head(limit).tolist()
    except:
        return []

def get_stock_data_cached(ticker, start_date, end_date):
    file_path = os.path.join(CACHE_DIR, f"{ticker}.csv")
    if not os.path.exists(file_path):
        return None
    try:
        df = pd.read_csv(file_path)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        mask = (df.index >= start_date) & (df.index <= end_date)
        return df.loc[mask, ['close', 'high', 'low']]
    except:
        return None

# --- Indicator Calculations ---

def calculate_stochastic(df, period=14):
    """Fast %K Stochastic Oscillator"""
    df = df.copy()
    df['L14'] = df['low'].rolling(window=period).min()
    df['H14'] = df['high'].rolling(window=period).max()
    df['stoch'] = 100 * ((df['close'] - df['L14']) / (df['H14'] - df['L14']))
    return df

def calculate_smi(df, k_period=14, d_period=3):
    """
    Stochastic Momentum Index (SMI).
    SMI = 100 * EMA(EMA(close - midpoint)) / EMA(EMA(range/2))
    where midpoint = (H14 + L14) / 2 and range = H14 - L14
    """
    df = df.copy()
    df['L14'] = df['low'].rolling(window=k_period).min()
    df['H14'] = df['high'].rolling(window=k_period).max()
    
    df['midpoint'] = (df['H14'] + df['L14']) / 2
    df['dist'] = df['close'] - df['midpoint']
    df['range'] = df['H14'] - df['L14']
    
    # Double smoothing with EMA
    df['dist_ema1'] = df['dist'].ewm(span=d_period, adjust=False).mean()
    df['dist_ema2'] = df['dist_ema1'].ewm(span=d_period, adjust=False).mean()
    
    df['range_ema1'] = (df['range'] / 2).ewm(span=d_period, adjust=False).mean()
    df['range_ema2'] = df['range_ema1'].ewm(span=d_period, adjust=False).mean()
    
    df['smi'] = np.where(df['range_ema2'] != 0, 100 * df['dist_ema2'] / df['range_ema2'], 0)
    return df

def calculate_sma(df, period=50):
    """Simple Moving Average"""
    df = df.copy()
    df['sma50'] = df['close'].rolling(window=period).mean()
    df['below_sma'] = df['close'] < df['sma50']
    return df

def main():
    print("Starting data export for dashboard (multi-indicator)...")
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365*10)).strftime('%Y-%m-%d')
    
    # VN-Index
    print("Fetching VN-Index...")
    try:
        vnindex_quote = Quote(symbol='VNINDEX', source='VCI')
        vnindex = vnindex_quote.history(start=start_date, end=end_date, resolution='1D')
        vnindex['time'] = pd.to_datetime(vnindex['time'])
        vnindex.set_index('time', inplace=True)
        vnindex['close'] = pd.to_numeric(vnindex['close'], errors='coerce')
        vnindex = vnindex[['close']]
    except Exception as e:
        print(f"Error fetching VN-Index: {e}")
        return

    common_dates = vnindex.index.strftime('%Y-%m-%d').tolist()
    vnindex_values = vnindex['close'].fillna(0).tolist()
    
    export_data = {
        'dates': common_dates,
        'vnindex': vnindex_values,
        'indicators': {
            'stoch_20': 'Stochastic < 20',
            'smi_40': 'SMI < -40',
            'sma_50': 'Close < SMA(50)'
        },
        'sectors': {}
    }

    # Sectors
    sectors_file = 'data/sectors_level2.csv'
    if not os.path.exists(sectors_file):
        print("Sectors file not found.")
        return
    sectors_df = pd.read_csv(sectors_file)
    sector_names = sectors_df['icb_name2'].tolist()

    for sector_name in sector_names:
        print(f"Processing {sector_name}...")
        tickers = get_sector_stocks(sector_name)
        if len(tickers) < 3:
            continue
            
        # Initialize counters
        stoch_counts = pd.DataFrame(index=vnindex.index)
        stoch_counts['stoch_20'] = 0
        stoch_counts['smi_40'] = 0
        stoch_counts['sma_50'] = 0
        valid_stock_count = 0
        
        for ticker in tickers:
            df = get_stock_data_cached(ticker, start_date, end_date)
            if df is None or df.empty:
                continue
            
            # Calculate all indicators
            df = calculate_stochastic(df)
            df = calculate_smi(df)
            df = calculate_sma(df)
            
            # Reindex to VN-Index dates
            df = df.reindex(vnindex.index)
            
            # Count conditions
            stoch_counts['stoch_20'] += (df['stoch'] < 20).fillna(False).astype(int)
            stoch_counts['smi_40'] += (df['smi'] < -40).fillna(False).astype(int)
            stoch_counts['sma_50'] += (df['below_sma']).fillna(False).astype(int)
            valid_stock_count += 1
            
        if valid_stock_count == 0:
            continue
            
        # Convert to percentages
        stoch_20_pct = ((stoch_counts['stoch_20'] / valid_stock_count) * 100).fillna(0).tolist()
        smi_40_pct = ((stoch_counts['smi_40'] / valid_stock_count) * 100).fillna(0).tolist()
        sma_50_pct = ((stoch_counts['sma_50'] / valid_stock_count) * 100).fillna(0).tolist()
        
        export_data['sectors'][sector_name] = {
            'stoch_20': stoch_20_pct,
            'smi_40': smi_40_pct,
            'sma_50': sma_50_pct,
            'count': valid_stock_count
        }

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False)
        
    print(f"Export complete. Saved to {DATA_FILE}")

if __name__ == "__main__":
    main()
