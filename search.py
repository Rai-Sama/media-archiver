import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "everything/personal/backup/media_index.db"

def search_media(args):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = "SELECT original_name, source, date_taken, camera_model, file_size_kb, current_path FROM media WHERE 1=1"
    params = []
    
    if args.name:
        query += " AND original_name LIKE ?"
        params.append(f"%{args.name}%")
    if args.source:
        query += " AND source = ?"
        params.append(args.source)
    if args.date:
        query += " AND date_taken LIKE ?"
        params.append(f"%{args.date}%")
    if args.camera:
        query += " AND camera_model LIKE ?"
        params.append(f"%{args.camera}%")
    if args.min_size:
        query += " AND file_size_kb >= ?"
        params.append(args.min_size)
    if args.flash:
        query += " AND flash_fired = 1"
    if args.gps:
        query += " AND latitude IS NOT NULL"
        
    query += " ORDER BY date_taken DESC"
        
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        print("No matches found.")
        return

    print(f"{'File Name':<20} | {'Src':<6} | {'Date Taken':<19} | {'Camera':<15} | {'Size(KB)':<8} | {'Path'}")
    print("-" * 115)
    for row in results:
        cam = row[3] if row[3] else "N/A"
        print(f"{row[0][:18]+'..':<20} | {row[1]:<6} | {row[2]:<19} | {cam[:13]+'..':<15} | {row[4]:<8.0f} | {row[5]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deep search local media DB.")
    parser.add_argument("--name", help="Filename snippet")
    parser.add_argument("--source", choices=["me", "shared", "misc"], help="Staging origin")
    parser.add_argument("--date", help="Date format YYYY-MM-DD or YYYY-MM")
    parser.add_argument("--camera", help="Camera model snippet")
    parser.add_argument("--min_size", type=float, help="Minimum file size in KB")
    parser.add_argument("--flash", action="store_true", help="Photos where flash fired")
    parser.add_argument("--gps", action="store_true", help="Photos with location data")
    
    search_media(parser.parse_args())
