import pandas as pd
from vnstock import Listing
import os

def cache_sectors():
    print("Fetching sector data from vnstock...")
    try:
        listing = Listing(source='VCI')
        df = listing.symbols_by_industries()
        
        data_dir = 'data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Level 2 Sectors (Industry Group)
        if 'icb_code2' in df.columns and 'icb_name2' in df.columns:
            l2_sectors = df[['icb_code2', 'icb_name2']].drop_duplicates().sort_values('icb_code2')
            l2_path = os.path.join(data_dir, 'sectors_level2.csv')
            l2_sectors.to_csv(l2_path, index=False)
            print(f"Saved {len(l2_sectors)} Level 2 sectors to {l2_path}")
        else:
            print("Level 2 sector columns not found.")

        # Level 3 Sectors (Sector)
        if 'icb_code3' in df.columns and 'icb_name3' in df.columns:
            l3_sectors = df[['icb_code3', 'icb_name3']].drop_duplicates().sort_values('icb_code3')
            l3_path = os.path.join(data_dir, 'sectors_level3.csv')
            l3_sectors.to_csv(l3_path, index=False)
            print(f"Saved {len(l3_sectors)} Level 3 sectors to {l3_path}")
        else:
            print("Level 3 sector columns not found.")
            
    except Exception as e:
        print(f"Error fetching/saving sectors: {e}")

if __name__ == "__main__":
    cache_sectors()
