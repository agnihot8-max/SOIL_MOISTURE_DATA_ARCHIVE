import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def ingest_weather_data(filepath):
    df = pd.read_excel(filepath, skiprows=3, usecols=[0, 1, 2, 6], names=['year', 'month', 'day', 'rain_in'])
    df['rain_in'] = df['rain_in'].replace('T', 0.0)
    df['rain_in'] = pd.to_numeric(df['rain_in'], errors='coerce').fillna(0)
    df = df.dropna(subset=['year', 'month', 'day'])
    df['date'] = pd.to_datetime(df[['year', 'month', 'day']])
    return df.set_index('date')

# --- Academic Export Formatting ---
sns.set_theme(style="ticks", context="paper", font_scale=1.2)
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'

def ingest_and_preprocess(file_paths: list) -> pd.DataFrame:
    df_list = []
    for f in file_paths:
        df_temp = pd.read_csv(f)
        
        # Hardware Node injection based on explicit payload file
        filename = Path(f).name
        if "NODE28000MAY28" in filename or "feeds (3)" in filename or "feeds (5)" in filename or "Node_2" in filename:
            node_id = "2"
        elif "NODE3MAY28" in filename or "feeds (2)" in filename or "feeds (6)" in filename or "Node_3" in filename:
            node_id = "3"
        elif "NODE18000MAY28" in filename or "feeds (1)" in filename or "feeds (4)" in filename or "Node_1" in filename:
            node_id = "1"
        else:
            node_id = "Unknown"
            
        df_temp['node_id'] = node_id
        df_list.append(df_temp)
        
    df = pd.concat(df_list, ignore_index=True)
    
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
    df = df.sort_values('created_at').reset_index(drop=True)
    
    payload_cols = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6']
    for col in payload_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    df = df.rename(columns={
        'field1': 'bus_id',
        'field2': 'vwc_raw',
        'field3': 'temp_c',
        'field4': 'v_batt',
        'field5': 'rssi_dbm',
        'field6': 'snr_db'
    })
    
    return df

def execute_eda_pipeline(df: pd.DataFrame, output_dir: str = ".", weather_df: pd.DataFrame = None):
    base_out = Path(output_dir)
    base_out.mkdir(exist_ok=True)
    
    df['month_period'] = df['created_at'].dt.to_period('M')
    months = df['month_period'].unique()
    
    for month in sorted(months):
        month_str = str(month)
        print(f"Processing month: {month_str}...")
        
        month_dir = base_out / month_str
        month_dir.mkdir(exist_ok=True)
        month_df = df[df['month_period'] == month]
        
        # Isolate explicitly by the hardcoded physical Node ID
        nodes = month_df['node_id'].dropna().unique()
        
        for node in nodes:
            node_id = str(node)
            sensor_df = month_df[month_df['node_id'] == node]
            file_suffix = f"node_{node_id}.png"
            
            # --- 00A. Executive Summary Table ---
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.axis('tight')
            ax.axis('off')
            
            expected_monthly = month.days_in_month * 48.0
            actual_monthly = len(sensor_df)
            monthly_yield = (actual_monthly / expected_monthly) * 100
            
            table_data = [
                ["Total Packets", f"{actual_monthly}"],
                ["Uptime Yield", f"{monthly_yield:.1f}%"],
                ["Temp (Min / Mean / Max)", f"{sensor_df['temp_c'].min():.1f} / {sensor_df['temp_c'].mean():.1f} / {sensor_df['temp_c'].max():.1f} °C"],
                ["VWC (Min / Mean / Max)", f"{sensor_df['vwc_raw'].min():.1f} / {sensor_df['vwc_raw'].mean():.1f} / {sensor_df['vwc_raw'].max():.1f}"],
                ["Battery Drop (Max - Min)", f"{(sensor_df['v_batt'].max() - sensor_df['v_batt'].min()):.3f} V"],
                ["Battery Absolute Min", f"{sensor_df['v_batt'].min():.3f} V"]
            ]
            
            table = ax.table(cellText=table_data, colLabels=["Metric", "Value"], cellLoc='center', loc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.2, 1.5)
            plt.title(f'Executive Summary - {month_str} (Node {node_id})', y=1.1)
            plt.savefig(month_dir / f'00_monthly_statistics_{file_suffix}')
            plt.close()
            
            # --- 00B. Daily Boxplots (Outlier Isolation) ---
            if not sensor_df.empty:
                sensor_df_copy = sensor_df.copy()
                sensor_df_copy['day'] = sensor_df_copy['created_at'].dt.day
                
                fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
                
                sns.boxplot(x='day', y='temp_c', data=sensor_df_copy, ax=axes[0], color='#ff7f0e', fliersize=3)
                axes[0].set_title(f'Daily Temperature Distributions - {month_str} (Node {node_id})')
                axes[0].set_ylabel('Temperature (°C)')
                
                sns.boxplot(x='day', y='vwc_raw', data=sensor_df_copy, ax=axes[1], color='#1f77b4', fliersize=3)
                axes[1].set_title('Daily VWC Distributions')
                axes[1].set_ylabel('VWC Raw Count')
                axes[1].set_xlabel('Day of Month')
                
                plt.tight_layout()
                plt.savefig(month_dir / f'00_daily_boxplots_{file_suffix}')
                plt.close()
            
            # --- 00C. Hardware Vital Signs (Battery & Link) ---
            if not sensor_df.empty:
                hourly_vitals = sensor_df.set_index('created_at').resample('1h').mean(numeric_only=True)
                
                fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
                
                axes[0].plot(hourly_vitals.index, hourly_vitals['v_batt'], color='green')
                axes[0].set_title(f'Hardware Vitals (Battery Voltage) - {month_str} (Node {node_id})')
                axes[0].set_ylabel('Battery (V)')
                
                axes[1].plot(hourly_vitals.index, hourly_vitals['rssi_dbm'], color='purple', label='RSSI')
                axes[1].set_title('Link Quality (RSSI)')
                axes[1].set_ylabel('RSSI (dBm)')
                axes[1].set_xlabel('Date')
                
                fig.autofmt_xdate(rotation=45)
                fig.tight_layout()
                plt.savefig(month_dir / f'00_hardware_vitals_{file_suffix}')
                plt.close()
            
            # --- 1. Data Coverage ---
            fig, ax = plt.subplots(figsize=(12, 5))
            daily_counts = sensor_df.set_index('created_at').resample('1D').size()
            bars = ax.bar(daily_counts.index, daily_counts.values, color='#2ca02c', width=0.8)
            
            # Calculate aggregate monthly yield
            expected_monthly = month.days_in_month * 48.0
            actual_monthly = len(sensor_df)
            monthly_yield = (actual_monthly / expected_monthly) * 100
            
            ax.axhline(48, color='red', linestyle='--', alpha=0.7, label='Expected (48/day)')
            ax.set_ylim(0, max(55, daily_counts.max() * 1.2))
            ax.legend(loc='upper right')
            
            ax.set_title(f'Data Coverage - {month_str} (Node {node_id}) | Monthly Yield: {monthly_yield:.1f}%')
            ax.set_xlabel('Date')
            ax.set_ylabel('Packets Received')
            fig.autofmt_xdate(rotation=45)
            fig.tight_layout()
            plt.savefig(month_dir / f'01_data_coverage_{file_suffix}')
            plt.close()
            
            # --- 2. Sensor Distributions ---
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            
            valid_vwc = sensor_df['vwc_raw'].dropna()
            if not valid_vwc.empty:
                sns.histplot(valid_vwc, kde=(len(valid_vwc) > 1), ax=axes[0], color='#1f77b4')
            axes[0].set_title(f'VWC Raw Distribution - {month_str} (Node {node_id})')
            axes[0].set_xlabel('VWC Raw Count')
            
            valid_temp = sensor_df['temp_c'].dropna()
            if not valid_temp.empty:
                sns.histplot(valid_temp, kde=(len(valid_temp) > 1), ax=axes[1], color='#ff7f0e')
            axes[1].set_title(f'Temperature (°C) Distribution - {month_str} (Node {node_id})')
            axes[1].set_xlabel('Temperature (°C)')
            
            plt.tight_layout()
            plt.savefig(month_dir / f'02_distributions_{file_suffix}')
            plt.close()
            
            # --- 3. Link Quality Density ---
            fig, ax = plt.subplots(figsize=(8, 6))
            if len(sensor_df.dropna(subset=['snr_db', 'rssi_dbm'])) > 5:
                hb = ax.hexbin(sensor_df['snr_db'], sensor_df['rssi_dbm'], gridsize=30, cmap='inferno', mincnt=1)
                cb = fig.colorbar(hb, ax=ax)
                cb.set_label('Packet Density')
                ax.set_title(f'LoRaWAN Link Diagnostics - {month_str} (Node {node_id})')
                ax.set_xlabel('SNR (dB)')
                ax.set_ylabel('RSSI (dBm)')
                plt.tight_layout()
                plt.savefig(month_dir / f'03_rf_diagnostics_{file_suffix}')
            plt.close()
            
            # --- 4. Thermal-Moisture Correlation (Rate of Change / Delta) ---
            dry_days_df = sensor_df.copy()
            if weather_df is not None:
                dry_days_df['date_only'] = dry_days_df['created_at'].dt.date.astype(str)
                weather_str = weather_df.copy()
                weather_str.index = weather_str.index.astype(str)
                rain_dates = weather_str[weather_str['rain_in'] > 0].index.tolist()
                dry_days_df = dry_days_df[~dry_days_df['date_only'].isin(rain_dates)]
                
            # Calculate Hourly Means, then calculate First Derivative (Rate of Change)
            hourly_means = dry_days_df.set_index('created_at').resample('1h').mean(numeric_only=True)
            corr_df = hourly_means[['temp_c', 'vwc_raw']].diff().dropna()
            corr_df = corr_df.rename(columns={'temp_c': 'delta_temp', 'vwc_raw': 'delta_vwc'})
            
            if not corr_df.empty and len(corr_df) > 10:
                fig, ax = plt.subplots(figsize=(8, 6))
                
                sns.regplot(
                    data=corr_df, x='delta_temp', y='delta_vwc',
                    scatter_kws={'alpha':0.8, 's':15, 'color':'#2c5282'},
                    line_kws={'color':'red', 'linewidth':2},
                    ax=ax
                )
                
                pearson_corr = corr_df['delta_temp'].corr(corr_df['delta_vwc'])
                ax.set_title(f'Thermal-Moisture Δ Correlation (Dry Days) - {month_str}\nPearson r: {pearson_corr:.2f}')
                ax.set_xlabel('Δ Temperature (°C / Hour)')
                ax.set_ylabel('Δ VWC (Raw / Hour)')
                
                # Draw crosshairs at (0,0) to show the origin of no change
                ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
                ax.axvline(0, color='black', linewidth=0.8, linestyle='--')
                
                plt.tight_layout()
                plt.savefig(month_dir / f'04_thermal_correlation_{file_suffix}')
                plt.close()
            
            # --- 5. Log-Scaled Distributions (Tail Isolation) ---
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            
            if not valid_vwc.empty:
                axes[0].hist(valid_vwc, bins=50, color='#1f77b4', log=True, edgecolor='black', alpha=0.7)
            axes[0].set_title(f'Log-Scaled VWC Distribution (Tails) - {month_str} (Node {node_id})')
            axes[0].set_xlabel('VWC Raw Count')
            axes[0].set_ylabel('Log Packet Count')
            
            if not valid_temp.empty:
                axes[1].hist(valid_temp, bins=50, color='#ff7f0e', log=True, edgecolor='black', alpha=0.7)
            axes[1].set_title(f'Log-Scaled Temp Distribution (Tails) - {month_str} (Node {node_id})')
            axes[1].set_xlabel('Temperature (°C)')
            axes[1].set_ylabel('Log Packet Count')
            
            plt.tight_layout()
            plt.savefig(month_dir / f'05_log_distributions_{file_suffix}')
            plt.close()
            
            # --- 6. Environmental Ribbon (Trend Isolation) ---
            hourly_ribbon = sensor_df.set_index('created_at').resample('1h').mean(numeric_only=True)
            
            if not hourly_ribbon.empty and len(hourly_ribbon.dropna(subset=['temp_c', 'vwc_raw'])) > 24:
                # Plot 06: Pure Environment (Temp + VWC)
                fig, ax1 = plt.subplots(figsize=(12, 5))
                
                # Temp rolling metrics
                r_mean_temp = hourly_ribbon['temp_c'].rolling(window=24, min_periods=1).mean()
                r_min_temp = hourly_ribbon['temp_c'].rolling(window=24, min_periods=1).min()
                r_max_temp = hourly_ribbon['temp_c'].rolling(window=24, min_periods=1).max()
                
                color1 = '#ff7f0e'
                ax1.set_xlabel('Time (24H Smoothed)')
                ax1.set_ylabel('Temperature (°C)', color=color1)
                ax1.plot(r_mean_temp.index, r_mean_temp, color=color1, linewidth=2, label='Temp 24h Avg')
                ax1.fill_between(r_mean_temp.index, r_min_temp, r_max_temp, color=color1, alpha=0.2, label='Temp Min/Max Ribbon')
                ax1.tick_params(axis='y', labelcolor=color1)
                
                # VWC rolling metrics
                r_mean_vwc = hourly_ribbon['vwc_raw'].rolling(window=24, min_periods=1).mean()
                r_min_vwc = hourly_ribbon['vwc_raw'].rolling(window=24, min_periods=1).min()
                r_max_vwc = hourly_ribbon['vwc_raw'].rolling(window=24, min_periods=1).max()
                
                ax2 = ax1.twinx()
                color2 = '#1f77b4'
                ax2.set_ylabel('VWC Raw Count', color=color2)
                ax2.plot(r_mean_vwc.index, r_mean_vwc, color=color2, linewidth=2, label='VWC 24h Avg')
                ax2.fill_between(r_mean_vwc.index, r_min_vwc, r_max_vwc, color=color2, alpha=0.2, label='VWC Min/Max Ribbon')
                ax2.tick_params(axis='y', labelcolor=color2)
                
                # Combine legends from both axes
                lines_1, labels_1 = ax1.get_legend_handles_labels()
                lines_2, labels_2 = ax2.get_legend_handles_labels()
                ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left', fontsize=8)
                
                plt.title(f'24-Hour Environmental Ribbon (Trend Isolation) - {month_str} (Node {node_id})')
                fig.autofmt_xdate(rotation=45)
                fig.tight_layout()
                plt.savefig(month_dir / f'06_environmental_ribbon_{file_suffix}')
                plt.close()
                
                # --- 7. Hydrology Validation (VWC vs Precipitation) ---
                if weather_df is not None:
                    start_str = str(month.start_time.date())
                    end_str = str(month.end_time.date())
                    try:
                        month_weather = weather_df.loc[start_str:end_str]
                    except KeyError:
                        month_weather = pd.DataFrame()
                        
                    if not month_weather.empty:
                        fig, ax1 = plt.subplots(figsize=(12, 5))
                        
                        # VWC Ribbon (Primary Axis)
                        color1 = '#1f77b4'
                        ax1.set_xlabel('Time (24H Smoothed)')
                        ax1.set_ylabel('VWC Raw Count', color=color1)
                        ax1.plot(r_mean_vwc.index, r_mean_vwc, color=color1, linewidth=2, label='VWC 24h Avg')
                        ax1.fill_between(r_mean_vwc.index, r_min_vwc, r_max_vwc, color=color1, alpha=0.2, label='VWC Min/Max Ribbon')
                        ax1.tick_params(axis='y', labelcolor=color1)
                        
                        # Rain Bar Chart (Secondary Axis)
                        ax2 = ax1.twinx()
                        color2 = '#2ca02c' # Green for rain to contrast with blue VWC
                        ax2.set_ylabel('Precipitation (in)', color=color2)
                        bars = ax2.bar(month_weather.index, month_weather['rain_in'], width=1.0, color=color2, alpha=0.4, label='Rainfall (in)')
                        ax2.tick_params(axis='y', labelcolor=color2)
                        ax2.set_ylim(0, max(2.0, month_weather['rain_in'].max() * 2)) 
                        
                        # Combine legends
                        lines_1, labels_1 = ax1.get_legend_handles_labels()
                        lines_2 = [bars]
                        labels_2 = ['Rainfall (in)']
                        ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left', fontsize=8)
                        
                        plt.title(f'Hydrology Validation (VWC vs Rain) - {month_str} (Node {node_id})')
                        fig.autofmt_xdate(rotation=45)
                        fig.tight_layout()
                        plt.savefig(month_dir / f'07_hydrology_validation_{file_suffix}')
                        plt.close()

if __name__ == "__main__":
    target_files = [
        "/mnt/c/Users/Adhar/Downloads/NODE28000MAY28.csv",   # Node 2
        "/mnt/c/Users/Adhar/Downloads/NODE3MAY28.csv",       # Node 3
        "/mnt/c/Users/Adhar/Downloads/NODE18000MAY28.csv"    # Node 1
    ]
    
    print("Ingesting payloads...")
    df_clean = ingest_and_preprocess(target_files)
    
    print("Ingesting meteorological ground-truth...")
    weather_df = ingest_weather_data('/mnt/c/Users/Adhar/Downloads/MBG Data.xlsx')
    
    print(f"Data mapping complete. Extracted {len(df_clean)} packets.")
    print("Executing temporal month-over-month pipeline explicitly by Node...")
    
    execute_eda_pipeline(df_clean, output_dir="/home/adhar/SOILMOSTURE_DATA/outputs", weather_df=weather_df)
    
    print("Execution nominal. Visual proofs structured by month and node in ./outputs/")
