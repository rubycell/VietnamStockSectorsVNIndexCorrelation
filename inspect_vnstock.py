from vnstock import Quote
import pandas as pd
from datetime import datetime, timedelta

end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

print(f"Fetching from {start_date} to {end_date}")

# Test Stock
try:
    print("Fetching VCB...")
    stock = Quote(symbol='VCB', source='VCI')
    df = stock.history(start=start_date, end=end_date, resolution='1D')
    print("VCB Data:")
    print(df.head() if df is not None else "None")
except Exception as e:
    print(f"Error fetching VCB: {e}")

# Test Index
try:
    print("Fetching VNINDEX...")
    # Try VNINDEX symbol
    index = Quote(symbol='VNINDEX', source='VCI')
    df_index = index.history(start=start_date, end=end_date, resolution='1D')
    print("VNINDEX Data:")
    print(df_index.head() if df_index is not None else "None")
except Exception as e:
    print(f"Error fetching VNINDEX: {e}")
