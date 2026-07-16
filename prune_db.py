import sqlite3
import sys

def prune_database(db_name):
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

    # 1. Find the Mode (The most frequently occurring character length)
    cursor.execute('''
        SELECT 
            (LENGTH(IFNULL(development_info,'')) + 
             LENGTH(IFNULL(travel_info,'')) + 
             LENGTH(IFNULL(geographic_info,'')) + 
             LENGTH(IFNULL(history_info,''))) AS total_chars,
            COUNT(*) as freq
        FROM upazilas 
        GROUP BY total_chars
        ORDER BY freq DESC
        LIMIT 1
    ''')
    
    mode_record = cursor.fetchone()
    if not mode_record:
        print("Database is empty.")
        return

    junk_length = mode_record[0]
    junk_freq = mode_record[1]

    print("--- ALGORITHM RESULTS ---")
    print(f"Placeholder detected! The most common length is {junk_length} characters.")
    print(f"This exact length appears {junk_freq} times.")
    
    # Add a small buffer of 50 chars just in case some placeholders have extra spaces/newlines
    threshold = junk_length + 50
    print(f"Setting strict wipe threshold to nuke everything with <= {threshold} characters.")

    # 2. Execute the wipe
    cursor.execute(f'''
        DELETE FROM upazilas 
        WHERE (LENGTH(IFNULL(development_info,'')) + 
               LENGTH(IFNULL(travel_info,'')) + 
               LENGTH(IFNULL(geographic_info,'')) + 
               LENGTH(IFNULL(history_info,''))) <= ?
    ''', (threshold,))
    
    deleted_count = cursor.rowcount
    
    # Clean up empty titles just in case
    cursor.execute("DELETE FROM upazilas WHERE title = 'Unknown Title'")
    deleted_count += cursor.rowcount

    # 3. Commit and compress
    conn.commit()
    cursor.execute("VACUUM")

    # 4. Verify final count
    cursor.execute("SELECT COUNT(*) FROM upazilas")
    final_count = cursor.fetchone()[0]

    print("\nExecuting wipe...")
    print(f"Successfully wiped {deleted_count} non-informative records.")
    print(f"Database '{db_name}' now contains exactly {final_count} highly informative records.")
    
    conn.close()

if __name__ == '__main__':
    db_file = 'upazila_text.db'
    print(f"Running frequency-based prune on {db_file}...")
    prune_database(db_file)