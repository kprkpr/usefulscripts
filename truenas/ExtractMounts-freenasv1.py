#!/usr/bin/env python3
import sqlite3
import os
"""
Tool to extract and print SMB/CIFS and NFS share configurations from a FreeNAS v1
SQLite database. It reads share records, resolves NFS paths from auxiliary tables
when available, and outputs a human-readable summary with key settings and
additional properties, while omitting internal IDs. Intended for quick auditing
or migration reporting of share configurations.
"""

DB_FILE = 'freenas-v1.db'

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def print_section(title):
    print("\n" + "#" * 60)
    print(f" {title}")
    print("#" * 60)

def dump_row(row, indent=2):
    """Print all columns that have data (ignore None or empty)"""
    max_len = 0
    # Calculate width for alignment
    valid_keys = [k for k, v in row.items() if v is not None and v != '']
    if not valid_keys: return
    
    max_len = max(len(k) for k in valid_keys)
    
    for key in valid_keys:
        # Omit internal IDs that do not provide useful info to the user
        if key == 'id': continue
        val = row[key]
        print(f"{' ' * indent}{key.ljust(max_len)} : {val}")

def get_smb_shares(cursor):
    print_section("SMB / CIFS SHARES (Complete Configuration)")
    try:
        cursor.execute("SELECT * FROM sharing_cifs_share")
        shares = cursor.fetchall()
        
        if not shares:
            print("No SMB shares found.")
            return

        for share in shares:
            print(f"\n--- Share: {share.get('cifs_name', 'No Name')} ---")
            
            # Print main path
            print(f"  Main Path     : {share.get('cifs_path', 'N/A')}")
            
            # Print Hosts Allow/Deny specifically if they exist
            if share.get('cifs_hostsallow'):
                print(f"  HOSTS ALLOW    : {share['cifs_hostsallow']}")
            if share.get('cifs_hostsdeny'):
                print(f"  HOSTS DENY     : {share['cifs_hostsdeny']}")
                
            # Print the rest of the properties dynamically
            print("  [Additional Details]:")
            dump_row(share, indent=4)

    except sqlite3.OperationalError as e:
        print(f"Error reading SMB table: {e}")

def get_nfs_shares(cursor):
    print_section("NFS SHARES (Complete Configuration)")
    try:
        cursor.execute("SELECT * FROM sharing_nfs_share")
        nfs_shares = cursor.fetchall()

        if not nfs_shares:
            print("No NFS shares found.")
            return

        # Try to detect the name of the paths table
        path_table = None
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sharing_nfs_share_paths'")
            if cursor.fetchone(): path_table = 'sharing_nfs_share_paths'
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sharing_nfs_share_path'")
                if cursor.fetchone(): path_table = 'sharing_nfs_share_path'
        except:
            pass

        for share in nfs_shares:
            share_id = share.get('id')
            print(f"\n--- NFS Share ID: {share_id} ---")

            # 1. Intentar obtener rutas (Paths)
            paths = []
            if path_table:
                try:
                    cursor.execute(f"SELECT path FROM {path_table} WHERE share_id = ?", (share_id,))
                    rows = cursor.fetchall()
                    paths = [r['path'] for r in rows]
                except Exception as e:
                    paths = [f"Error reading paths: {e}"]
            
            # Fallback for older versions where the path was in the main table
            if not paths and 'nfs_path' in share and share['nfs_path']:
                paths = [share['nfs_path']]

            if paths:
                print(f"  PATHS          : {', '.join(paths)}")
            else:
                print(f"  PATHS          : [NOT FOUND OR EMPTY]")

            # 2. Hosts / Networks
            if share.get('nfs_network'):
                print(f"  ALLOWED NETWORKS: {share['nfs_network']}")
            if share.get('nfs_hosts'):
                print(f"  ALLOWED HOSTS  : {share['nfs_hosts']}")

            # 3. Other details
            print("  [Configuration]:")
            dump_row(share, indent=4)

    except sqlite3.OperationalError as e:
        print(f"Error reading NFS table: {e}")

def main():
    if not os.path.exists(DB_FILE):
        print(f"ERROR: '{DB_FILE}' not found")
        return

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = dict_factory
    cursor = conn.cursor()

    get_smb_shares(cursor)
    get_nfs_shares(cursor)
    conn.close()

if __name__ == "__main__":
    main()
