import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from vnstock import Quote, Listing
from datetime import datetime, timedelta
import os
import warnings
import sys

# Suppress warnings
warnings.filterwarnings("ignore")

CACHE_DIR = 'data/1D'
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

PLOTS_DIR = 'plots'
if not os.path.exists(PLOTS_DIR):
    os.makedirs(PLOTS_DIR)

def get_sector_stocks(sector_name, limit=20):
    """
    Fetch list of stocks in a specific Level 2 sector.
    """
    try:
        listing = Listing(source='VCI')
        df_ind = listing.symbols_by_industries()
        
        if 'icb_name2' not in df_ind.columns:
            print(f"Error: icb_name2 column not found in listing data.")
            return []

        sector_stocks = df_ind[df_ind['icb_name2'] == sector_name]
        
        if sector_stocks.empty:
            print(f"No stocks found for sector '{sector_name}'")
            return []
            
        # Get list of symbols
        return sector_stocks['symbol'].head(limit).tolist()
    except Exception as e:
        print(f"Error fetching stocks for {sector_name}: {e}")
        return []

def get_stock_data(ticker, start_date, end_date):
    """
    Fetch historical data with caching in data/1D/
    """
    file_path = os.path.join(CACHE_DIR, f"{ticker}.csv")
    
    try:
        cached_df = None
        fetch_start = start_date
        
        if os.path.exists(file_path):
            try:
                cached_df = pd.read_csv(file_path)
                cached_df['time'] = pd.to_datetime(cached_df['time'])
                cached_df.set_index('time', inplace=True)
                
                if not cached_df.empty:
                    last_date = cached_df.index.max()
                    next_day = last_date + timedelta(days=1)
                    if next_day > datetime.strptime(end_date, '%Y-%m-%d'):
                        mask = (cached_df.index >= start_date) & (cached_df.index <= end_date)
                        return cached_df.loc[mask, ['close', 'high', 'low']]
                    
                    fetch_start = next_day.strftime('%Y-%m-%d')
            except Exception as e:
                print(f"Error reading cache for {ticker}: {e}")
                cached_df = None

        if pd.to_datetime(fetch_start) <= pd.to_datetime(end_date):
            # Fetch new data
            try:
                stock = Quote(symbol=ticker, source='VCI')
                new_df = stock.history(start=fetch_start, end=end_date, resolution='1D')
            except Exception as e:
                print(f"Network error fetching {ticker}: {e}")
                new_df = None

            if new_df is not None and not new_df.empty:
                new_df['time'] = pd.to_datetime(new_df['time'])
                new_df.set_index('time', inplace=True)
                
                for col in ['close', 'high', 'low', 'open', 'volume']:
                    if col in new_df.columns:
                        new_df[col] = pd.to_numeric(new_df[col], errors='coerce')
                
                if cached_df is not None:
                    full_df = pd.concat([cached_df, new_df])
                    full_df = full_df[~full_df.index.duplicated(keep='last')]
                    full_df.sort_index(inplace=True)
                else:
                    full_df = new_df
                
                full_df.reset_index().to_csv(file_path, index=False)
                
                mask = (full_df.index >= start_date) & (full_df.index <= end_date)
                return full_df.loc[mask, ['close', 'high', 'low']]
        
        if cached_df is not None:
             mask = (cached_df.index >= start_date) & (cached_df.index <= end_date)
             return cached_df.loc[mask, ['close', 'high', 'low']]

        return None

    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None

def calculate_stochastic(df, period=14):
    df['L14'] = df['low'].rolling(window=period).min()
    df['H14'] = df['high'].rolling(window=period).max()
    df['%K'] = 100 * ((df['close'] - df['L14']) / (df['H14'] - df['L14']))
    return df

import time

def analyze_sector(sector_name, vnindex, start_date, end_date):
    print(f"Analyzing Sector: {sector_name}")
    tickers = get_sector_stocks(sector_name)
    
    if not tickers:
        print(f"  No tickers found for {sector_name}")
        return

    stoch_under_20_counts = pd.DataFrame(index=vnindex.index)
    stoch_under_20_counts['count'] = 0
    valid_stock_count = 0
    
    if len(tickers) < 3:
        print(f"  Skipping {sector_name} (only {len(tickers)} stocks)")
        return

    for ticker in tickers:
        # Add basic sleep between requests to be polite
        time.sleep(1) 
        
        # Retry loop for rate limits
        max_retries = 3
        for attempt in range(max_retries):
            df = get_stock_data(ticker, start_date, end_date)
            if df is not None:
                break
            # If df is None, it might be an error or rate limit. 
            # get_stock_data prints errors. 
            # If we suspect rate limit from logs, we should sleep longer.
            # Here we just blindly backoff if None returned and we suspect it usually works?
            # Actually get_stock_data handles the fetch. Let's rely on it or just proceed.
            # But get_stock_data doesn't propagate the specific "Rate limit" exception easily 
            # without refactoring. 
            # For now, let's just make the inner loop more robust if we needed. 
            # Actually, the error causing exit was likely uncaught or sys.exit in vnstock?
            # "Process terminated. Exit code: 1" might mean vnstock raised a hard error.
            # Let's wrap get_stock_data call in try/except in the loop here just in case,
            # though get_stock_data already catches Exception.
            # The rate limit message "Bạn đã gửi quá nhiều request..." might be printed by vnstock 
            # and then it raises SystemExit or similar? 
            # Let's pause more between tickers.
        
        if df is None or df.empty:
            continue
            
        df = calculate_stochastic(df)
        df = df.reindex(vnindex.index)
        mask = (df['%K'] < 20)
        stoch_under_20_counts['count'] += mask.fillna(False).astype(int)
        valid_stock_count += 1

    if valid_stock_count == 0:
        print(f"  No valid data for {sector_name}")
        return

    # Normalisation and plotting...
    stoch_under_20_counts['percent'] = (stoch_under_20_counts['count'] / valid_stock_count) * 100
    final_df = vnindex.join(stoch_under_20_counts[['percent']])
    final_df.dropna(subset=['VNINDEX'], inplace=True)

    # Plot
    plt.figure(figsize=(12, 6))
    
    ax1 = plt.gca()
    ax2 = ax1.twinx()

    sns.lineplot(data=final_df, x=final_df.index, y='VNINDEX', ax=ax1, color='#1f77b4', label='VN-Index')
    ax1.set_ylabel('VN-Index', color='#1f77b4')
    ax1.tick_params(axis='y', labelcolor='#1f77b4')

    sns.lineplot(data=final_df, x=final_df.index, y='percent', ax=ax2, color='#ff7f0e', alpha=0.6, label=f'% {sector_name} < 20')
    ax2.fill_between(final_df.index, final_df['percent'], color='#ff7f0e', alpha=0.3)
    ax2.set_ylabel('% Oversold', color='#ff7f0e')
    ax2.tick_params(axis='y', labelcolor='#ff7f0e')
    ax2.set_ylim(0, 100)

    slug = sector_name.replace(' ', '_').replace('&', 'and').replace(',', '').lower()
    plt.title(f'VN-Index vs % {sector_name} Oversold (Stoch < 20)\nBased on {valid_stock_count} stocks')
    plt.tight_layout()
    
    plot_path = os.path.join(PLOTS_DIR, f'vn_index_vs_{slug}.png')
    plt.savefig(plot_path)
    plt.close()
    print(f"  Saved plot to {plot_path}")
    
    # Sleep between sectors
    time.sleep(5)

def main():
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d') # Last 5 years to be faster? Or 10? User said "Do the same" so 10.
    start_date = (datetime.now() - timedelta(days=365*10)).strftime('%Y-%m-%d')
    
    # Get Sectors
    sectors_file = 'data/sectors_level2.csv'
    if not os.path.exists(sectors_file):
        print("Sector cache not found. Please run cache_sectors.py first.")
        return
        
    sectors_df = pd.read_csv(sectors_file)
    sector_names = sectors_df['icb_name2'].tolist()
    
    # Get VN-Index (Global for all plots)
    print("Fetching VN-Index...")
    vnindex_quote = Quote(symbol='VNINDEX', source='VCI')
    vnindex = vnindex_quote.history(start=start_date, end=end_date, resolution='1D')
    if vnindex is None or vnindex.empty:
        print("Could not fetch VN-Index")
        return
    vnindex['time'] = pd.to_datetime(vnindex['time'])
    vnindex.set_index('time', inplace=True)
    vnindex['close'] = pd.to_numeric(vnindex['close'], errors='coerce')
    vnindex = vnindex[['close']].rename(columns={'close': 'VNINDEX'})

    for sector in sector_names:
        analyze_sector(sector, vnindex, start_date, end_date)

if __name__ == "__main__":
    main()
