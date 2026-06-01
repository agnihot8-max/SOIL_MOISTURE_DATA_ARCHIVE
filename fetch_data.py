import os
import requests
import pandas as pd
from pathlib import Path
import time

CHANNELS = {
    "Node_1": "2996904",
    "Node_2": "2996908",
    "Node_3": "2996910"
}

RESULTS_TO_FETCH = 8000

def fetch_thingspeak_data(output_dir="data"):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for node_name, channel_id in CHANNELS.items():
        print(f"Fetching data for {node_name} (Channel {channel_id})...")
        # To get data starting from March 1, 2026, we can use start parameter
        url = f"https://api.thingspeak.com/channels/{channel_id}/feeds.json?start=2026-03-01T00:00:00Z&results={RESULTS_TO_FETCH}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            feeds = data.get("feeds", [])
            if not feeds:
                print(f"No data returned for {node_name}.")
                continue
                
            df = pd.DataFrame(feeds)
            output_file = out_dir / f"{node_name}.csv"
            df.to_csv(output_file, index=False)
            print(f"Saved {len(df)} records to {output_file}")
            
        except Exception as e:
            print(f"Error fetching {node_name}: {e}")
            
        time.sleep(1.5)

if __name__ == "__main__":
    # Ensure we run this from the project root
    script_dir = Path(__file__).parent.absolute()
    fetch_thingspeak_data(output_dir=script_dir / "data")
