import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
import sys
from pathlib import Path
import warnings

# Suppress warnings for clean output
warnings.filterwarnings("ignore")

from eda_pipeline import ingest_and_preprocess

def generate_daily_archive(df, output_dir):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Filter for dates >= 2026-03-01
    df = df[df['created_at'] >= '2026-03-01'].copy()
    
    # Ensure sorted by time
    df = df.sort_values('created_at')
    
    # Group by node
    nodes = df['node_id'].unique()
    
    for node in nodes:
        node_df = df[df['node_id'] == node].copy()
        if node_df.empty:
            continue
            
        # Group by day
        node_df['date_only'] = node_df['created_at'].dt.date
        dates = sorted(node_df['date_only'].unique())
        
        pdf_path = out_dir / f"Daily_Archive_Node_{node}.pdf"
        
        print(f"Generating {pdf_path.name} with {len(dates)} days...")
        
        with PdfPages(pdf_path) as pdf:
            for day in dates:
                day_df = node_df[node_df['date_only'] == day]
                
                # Setup figure
                fig = plt.figure(figsize=(11, 8.5))
                fig.suptitle(f"Daily Telemetry Archive | Node {node} | Date: {day}", fontsize=16, fontweight='bold', y=0.95)
                
                # --- 1. Summary Statistics Table ---
                stats = []
                metrics = [('vwc_raw', 'VWC Raw'), ('temp_c', 'Temp (C)'), ('rssi_dbm', 'RSSI (dBm)'), ('snr_db', 'SNR (dB)')]
                for col, name in metrics:
                    if day_df[col].notna().any():
                        c_min = day_df[col].min()
                        c_mean = day_df[col].mean()
                        c_max = day_df[col].max()
                        
                        # Biggest jump: max absolute difference between consecutive readings
                        diffs = day_df[col].diff().abs()
                        c_jump = diffs.max()
                        if pd.isna(c_jump): c_jump = 0
                        
                        stats.append([name, f"{c_min:.2f}", f"{c_mean:.2f}", f"{c_max:.2f}", f"{c_jump:.2f}"])
                    else:
                        stats.append([name, "N/A", "N/A", "N/A", "N/A"])
                
                # Add Packets
                total_packets = len(day_df)
                stats.append(["Packets", "-", "-", f"{total_packets}", "-"])
                
                ax_table = plt.subplot2grid((6, 1), (0, 0))
                ax_table.axis('off')
                table = ax_table.table(cellText=stats, 
                                     colLabels=['Metric', 'Min', 'Mean', 'Max', 'Biggest Jump'],
                                     loc='center', cellLoc='center')
                table.scale(1, 1.5)
                table.auto_set_font_size(False)
                table.set_fontsize(10)
                
                # --- 2. Trend Plots ---
                # We have 5 remaining rows in the subplot grid, perfect for VWC, Temp, RSSI, SNR, and Packets
                ax_vwc = plt.subplot2grid((6, 1), (1, 0))
                ax_temp = plt.subplot2grid((6, 1), (2, 0), sharex=ax_vwc)
                ax_rssi = plt.subplot2grid((6, 1), (3, 0), sharex=ax_vwc)
                ax_snr = plt.subplot2grid((6, 1), (4, 0), sharex=ax_vwc)
                ax_pkt = plt.subplot2grid((6, 1), (5, 0), sharex=ax_vwc)
                
                # VWC
                ax_vwc.plot(day_df['created_at'], day_df['vwc_raw'], color='#1f77b4', marker='o', markersize=3, linewidth=1.5)
                ax_vwc.set_ylabel('VWC Raw')
                ax_vwc.grid(True, linestyle='--', alpha=0.6)
                
                # Temp
                ax_temp.plot(day_df['created_at'], day_df['temp_c'], color='#ff7f0e', marker='o', markersize=3, linewidth=1.5)
                ax_temp.set_ylabel('Temp (C)')
                ax_temp.grid(True, linestyle='--', alpha=0.6)
                
                # RSSI
                ax_rssi.plot(day_df['created_at'], day_df['rssi_dbm'], color='purple', marker='o', markersize=3, linewidth=1.5)
                ax_rssi.set_ylabel('RSSI (dBm)')
                ax_rssi.grid(True, linestyle='--', alpha=0.6)
                
                # SNR
                ax_snr.plot(day_df['created_at'], day_df['snr_db'], color='green', marker='o', markersize=3, linewidth=1.5)
                ax_snr.set_ylabel('SNR (dB)')
                ax_snr.grid(True, linestyle='--', alpha=0.6)
                
                # Cumulative Packets
                ax_pkt.plot(day_df['created_at'], np.arange(1, len(day_df) + 1), color='black', marker='o', markersize=3, linewidth=1.5, drawstyle='steps-post')
                ax_pkt.set_ylabel('Cumul. Packets')
                ax_pkt.set_xlabel('Time (UTC)')
                ax_pkt.grid(True, linestyle='--', alpha=0.6)
                
                # Format X-axis for hours
                ax_pkt.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                plt.xticks(rotation=45)
                
                plt.tight_layout(rect=[0, 0, 1, 0.93])
                pdf.savefig(fig)
                plt.close(fig)

if __name__ == "__main__":
    script_dir = Path(__file__).parent.absolute()
    
    target_files = [
        str(script_dir / "data" / "Node_1.csv"),
        str(script_dir / "data" / "Node_2.csv"),
        str(script_dir / "data" / "Node_3.csv")
    ]
    
    # Only process files that exist (in case one fails to download)
    target_files = [f for f in target_files if Path(f).exists()]
    
    if not target_files:
        print("No data files found in data/ directory. Run fetch_data.py first.")
        sys.exit(1)
    
    print("Ingesting payloads...")
    df_clean = ingest_and_preprocess(target_files)
    
    print("Generating Daily Archive PDFs...")
    generate_daily_archive(df_clean, script_dir / "outputs" / "daily_archives")
    print("Done!")
