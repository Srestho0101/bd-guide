import xml.etree.ElementTree as ET
import sqlite3
import argparse
import sys

def create_database(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS upazilas (
            wp_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            development_info TEXT,
            travel_info TEXT,
            geographic_info TEXT,
            history_info TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS informative_upazilas (
            wp_id INT,
            title TEXT,
            development_info TEXT,
            travel_info TEXT,
            geographic_info TEXT,
            history_info TEXT
        )
    ''')
    
    conn.commit()
    return conn

def process_xml_to_db(xml_file, db_name):
    try:
        conn = create_database(db_name)
        cursor = conn.cursor()
        
        namespaces = {
            'wp': 'http://wordpress.org/export/1.2/',
            'content': 'http://purl.org/rss/1.0/modules/content/',
            'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }
        
        print(f"Loading XML file: {xml_file}...")
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        channel = root.find('channel')
        if channel is None:
            print("Error: Invalid WXR file. No <channel> tag found.")
            sys.exit(1)
            
        items = channel.findall('item')
        print(f"Found {len(items)} total items in the XML. Filtering for 'upazila'...")
        
        insert_count = 0
        
        # This maps the ACF XML keys to our SQLite column names
        key_mapping = {
            'development-info': 'development_info',
            'travel-guide-data': 'travel_info',
            'geo-location-data': 'geographic_info',
            'upazila-history-data': 'history_info'
        }
        
        for item in items:
            post_type_elem = item.find('wp:post_type', namespaces)
            if post_type_elem is None or post_type_elem.text != 'upazila':
                continue
                
            status_elem = item.find('wp:status', namespaces)
            if status_elem is None or status_elem.text != 'publish':
                continue

            title_elem = item.find('title')
            title = title_elem.text.strip() if title_elem is not None and title_elem.text and title_elem.text.strip() else 'Unknown Title'
            
            wp_id_elem = item.find('wp:post_id', namespaces)
            if wp_id_elem is None or not wp_id_elem.text:
                continue
            
            wp_id = int(wp_id_elem.text)
            
            # Set default values for the database columns
            db_data = {
                'development_info': 'এই উপজেলার উন্নয়ন ও অগ্রযাত্রার তথ্য শীঘ্রই আপডেট করা হচ্ছে।',
                'travel_info': '',
                'geographic_info': '',
                'history_info': ''
            }
            
            # Extract relevant custom fields based on the new ACF keys
            for postmeta in item.findall('wp:postmeta', namespaces):
                meta_key_elem = postmeta.find('wp:meta_key', namespaces)
                meta_value_elem = postmeta.find('wp:meta_value', namespaces)
                
                if meta_key_elem is not None and meta_key_elem.text in key_mapping:
                    db_column = key_mapping[meta_key_elem.text]
                    if meta_value_elem is not None and meta_value_elem.text:
                        db_data[db_column] = meta_value_elem.text
            
            cursor.execute('''
                INSERT OR REPLACE INTO upazilas 
                (wp_id, title, development_info, travel_info, geographic_info, history_info)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                wp_id, title, 
                db_data['development_info'], 
                db_data['travel_info'], 
                db_data['geographic_info'], 
                db_data['history_info']
            ))
            insert_count += 1
            
        conn.commit()
        conn.close()
        
        print(f"Success! {insert_count} clean 'upazila' records inserted into {db_name}.")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Convert WordPress XML Export to Upazila SQLite Database")
    parser.add_argument('-i', '--input', required=True, help="Path to the new WordPress XML export file")
    parser.add_argument('-o', '--output', default="upazila_text.db", help="Name of the output SQLite database")
    
    args = parser.parse_args()
    process_xml_to_db(args.input, args.output)
