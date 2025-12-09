from vnstock import Listing
import pandas as pd

def count_sectors():
    try:
        listing = Listing(source='VCI')
        df = listing.symbols_by_industries()
        
        # ICB has different levels. Level 2 (Supersector/Industry Group) or Level 3 (Sector) are common.
        if 'icb_name2' in df.columns:
            sectors_l2 = df['icb_name2'].unique()
            print(f"Number of Level 2 Sectors (Industry Groups): {len(sectors_l2)}")
            print("List:", sorted(sectors_l2))
            
        if 'icb_name3' in df.columns:
            sectors_l3 = df['icb_name3'].unique()
            print(f"\nNumber of Level 3 Sectors: {len(sectors_l3)}")
            print("List:", sorted(sectors_l3))
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    count_sectors()
