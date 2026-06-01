import os
import re
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter, landscape

def draw_img_fit(c, img_path, x, y, max_w, max_h):
    """
    Draws an image within a bounding box while preserving its aspect ratio.
    Centers it inside the bounding box.
    """
    try:
        img = Image.open(img_path)
        w, h = img.size
        aspect = w / h
        
        # Fit inside bounding box while preserving aspect ratio
        target_w = max_w
        target_h = target_w / aspect
        
        if target_h > max_h:
            target_h = max_h
            target_w = target_h * aspect
            
        # Center the image inside the bounding box
        offset_x = (max_w - target_w) / 2
        offset_y = (max_h - target_h) / 2
        
        c.drawImage(str(img_path), x + offset_x, y + offset_y, width=target_w, height=target_h)
    except Exception as e:
        print(f"Error loading image {img_path}: {e}")
        draw_placeholder(c, x, y, max_w, max_h, img_path.name)

def draw_placeholder(c, x, y, w, h, name):
    """
    Draws a visual placeholder if an image is missing or cannot be loaded.
    """
    c.setFillColor(HexColor("#f7fafc"))
    # Draw background box with light grey fill and thin grey stroke
    c.rect(x, y, w, h, fill=True, stroke=True)
    c.setFillColor(HexColor("#e2e8f0"))
    c.rect(x + 5, y + 5, w - 10, h - 10, fill=True, stroke=False)
    
    # Text placeholder
    c.setFillColor(HexColor("#718096"))
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(x + w/2, y + h/2 + 10, f"Metric Plot Not Available")
    c.setFont("Helvetica", 9)
    c.drawCentredString(x + w/2, y + h/2 - 10, f"({name})")
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(x + w/2, y + h/2 - 25, "Verify telemetry packet yield or weather station ground-truth")

def draw_wrapped_text(c, text, x, y, max_w):
    """
    Simple word-wrapping utility to draw captions within box width.
    """
    c.setFillColor(HexColor("#2d3748"))
    c.setFont("Helvetica-Oblique", 9)
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        if c.stringWidth(line_str, "Helvetica-Oblique", 9) > max_w:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
        
    curr_y = y + (len(lines) - 1) * 12
    for line in lines:
        c.drawString(x, curr_y, line)
        curr_y -= 12

def compile_node_pdf(month_dir, node_id, month_str):
    """
    Compiles all generated plots for a single node in a month folder
    into a beautiful multi-page landscape PDF.
    """
    pdf_path = month_dir / f"report_node_{node_id}.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=landscape(letter))
    width, height = landscape(letter) # 792 x 612
    
    # Define our pages: (Page Title, [Left Image, Left Caption], [Right Image, Right Caption], is_single_wide_plot)
    pages = [
        (
            "EXECUTIVE SUMMARY & SYSTEM VITALS",
            (f"00_monthly_statistics_node_{node_id}.png", "Overview of monthly data yield, temperature, raw moisture boundaries, and battery voltage range."),
            (f"00_hardware_vitals_node_{node_id}.png", "Monitors battery voltage depletion alongside wireless Link Quality (RSSI) to verify hardware stability."),
            False
        ),
        (
            "NETWORK COVERAGE & RF DIAGNOSTICS",
            (f"01_data_coverage_node_{node_id}.png", "Daily packet reception count. The red line represents the target expected baseline of 48 packets/day (one every 30 mins)."),
            (f"03_rf_diagnostics_node_{node_id}.png", "Signal-to-Noise Ratio (SNR) vs. Received Signal Strength (RSSI) density heatmap to assess connection quality and canopy wetness attenuation."),
            False
        ),
        (
            "DATA DISTRIBUTION & LOG TAIL ANALYSIS",
            (f"02_distributions_node_{node_id}.png", "Standard probability distribution of raw VWC counts and temperature readings showing main operating modes."),
            (f"05_log_distributions_node_{node_id}.png", "Log-scaled histograms designed to isolate rare anomalies, electrical spikes, and extreme weather events in the distribution tails."),
            False
        ),
        (
            "DAILY VARIABILITY & OUTLIER DETECTION",
            (f"00_daily_boxplots_node_{node_id}.png", "Daily boxplots showing the 25th, 50th, and 75th percentiles. Dots floating outside the whiskers are mathematically proven outliers."),
            None,
            True
        ),
        (
            "ENVIRONMENTAL TRENDS & THERMAL DYNAMICS",
            (f"06_environmental_ribbon_node_{node_id}.png", "24-hour rolling averages and min/max ribbons, smoothing out diurnal day/night oscillations to isolate underlying trends."),
            (f"04_thermal_correlation_node_{node_id}.png", "Rate of change correlation (Δ Temp vs. Δ VWC) on dry days, proving physical evaporation and drying curves."),
            False
        ),
        (
            "HYDROLOGICAL VALIDATION",
            (f"07_hydrology_validation_node_{node_id}.png", "Compiles raw VWC moisture counts against ground-truth weather station rainfall (green bars) to validate drainage and infiltration."),
            None,
            True
        )
    ]
    
    for page_idx, (title, left_info, right_info, is_wide) in enumerate(pages):
        # 1. Header Banner
        c.setFillColor(HexColor("#1a365d")) # Deep Navy Blue
        c.rect(0, 562, 792, 50, fill=True, stroke=False)
        
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica-Bold", 13)
        c.drawString(20, 582, f"SOIL MOISTURE TELEMETRY REPORT | NODE {node_id} | {month_str}")
        
        c.setFont("Helvetica", 11)
        c.drawRightString(772, 582, title)
        
        # 2. Footer
        c.setFillColor(HexColor("#718096")) # Gray
        c.setFont("Helvetica", 8)
        c.drawString(20, 15, "Automated Agronomy Analytics Pipeline")
        c.drawRightString(772, 15, f"Page {page_idx + 1} of {len(pages)}")
        
        # Divider Line
        c.setStrokeColor(HexColor("#cbd5e0"))
        c.setLineWidth(0.75)
        c.line(20, 28, 772, 28)
        
        # 3. Content Area
        if is_wide:
            img_name, caption = left_info
            img_path = month_dir / img_name
            
            # Bounding box: x=30, y=95, w=732, h=440
            if img_path.exists():
                draw_img_fit(c, img_path, 30, 95, 732, 440)
            else:
                draw_placeholder(c, 30, 95, 732, 440, img_name)
                
            # Caption text
            c.setFillColor(HexColor("#2d3748"))
            c.setFont("Helvetica-Oblique", 10)
            c.drawCentredString(396, 50, caption)
            
        else:
            # Left Box: bounding box x=30, y=95, w=350, h=440
            img_name_l, caption_l = left_info
            img_path_l = month_dir / img_name_l
            if img_path_l.exists():
                draw_img_fit(c, img_path_l, 30, 95, 350, 440)
            else:
                draw_placeholder(c, 30, 95, 350, 440, img_name_l)
                
            # Left Caption
            draw_wrapped_text(c, caption_l, 30, 50, 350)
            
            # Right Box: bounding box x=412, y=95, w=350, h=440
            if right_info:
                img_name_r, caption_r = right_info
                img_path_r = month_dir / img_name_r
                if img_path_r.exists():
                    draw_img_fit(c, img_path_r, 412, 95, 350, 440)
                else:
                    draw_placeholder(c, 412, 95, 350, 440, img_name_r)
                    
                # Right Caption
                draw_wrapped_text(c, caption_r, 412, 50, 350)
                
        c.showPage()
        
    c.save()
    print(f"  Successfully compiled: {pdf_path.name}")

def main():
    base_dir = Path("/home/adhar/SOILMOSTURE_DATA/outputs")
    if not base_dir.exists():
        print(f"Error: Base outputs directory {base_dir} does not exist.")
        return
        
    print(f"Scanning for output subdirectories in: {base_dir}")
    
    # 1. Scan for month folders (e.g. 2026-04, 2025-08)
    month_pattern = re.compile(r"^\d{4}-\d{2}$")
    month_dirs = [d for d in base_dir.iterdir() if d.is_dir() and month_pattern.match(d.name)]
    
    if not month_dirs:
        print("No month subdirectories found (e.g. 2026-04).")
        return
        
    print(f"Found {len(month_dirs)} month directory/directories: {', '.join(sorted([d.name for d in month_dirs]))}")
    
    # 2. Iterate through each month folder and find unique nodes
    for month_dir in sorted(month_dirs):
        month_str = month_dir.name
        print(f"\n--- Processing Month: {month_str} ---")
        
        # Scan for node suffixes in PNG files
        node_ids = set()
        for file in month_dir.glob("*.png"):
            # e.g. 00_monthly_statistics_node_1.png -> node_1.png
            match = re.search(r"node_(\w+)\.png$", file.name)
            if match:
                node_ids.add(match.group(1))
                
        if not node_ids:
            print(f"  No node plots found in directory {month_str}")
            continue
            
        print(f"  Found node IDs: {', '.join(sorted(node_ids))}")
        
        # 3. For each node ID, compile a landscape PDF
        for node_id in sorted(node_ids):
            compile_node_pdf(month_dir, node_id, month_str)

if __name__ == "__main__":
    main()
