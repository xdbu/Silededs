#!/usr/bin/env python3
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random

BAN_DIR = os.path.join("input", "ban_compressed")
os.makedirs(BAN_DIR, exist_ok=True)

departements = []
for i in range(1, 96):
    if i == 20:
        continue
    departements.append(f"{i:02d}")
departements.extend(["2A", "2B"])
departements.extend(["971", "972", "973", "974", "975", "976", "977", "978", "984", "986", "987", "988", "989"])

BASE_URL = "https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

def download_file(dept):
    filename = f"adresses-{dept}.csv.gz"
    url = f"{BASE_URL}{filename}"
    dest_path = os.path.join(BAN_DIR, filename)
    
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
        return dept, "exists"
    
    for attempt in range(2):
        try:
            response = session.get(url, timeout=45, stream=True)
            if response.status_code == 200:
                with open(dest_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=32768):
                        f.write(chunk)
                if os.path.getsize(dest_path) > 1000:
                    return dept, True
            return dept, f"HTTP {response.status_code}"
        except:
            if attempt == 1:
                return dept, "timeout"
            time.sleep(2)

def main():
    total = len(departements)
    print(f"[*] Telechargement BAN ({total} fichiers) dans : {BAN_DIR}\n")
    
    success_count = 0
    exists_count = 0
    failed = []
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_file, dept): dept for dept in departements}
        for i, future in enumerate(as_completed(futures), 1):
            dept, result = future.result()
            if result is True:
                success_count += 1
                print(f"[{i}/{total}] [OK] {dept}")
            elif result == "exists":
                exists_count += 1
                print(f"[{i}/{total}] [OK] {dept} (deja)")
            else:
                failed.append(dept)
                print(f"[{i}/{total}] [Echec] {dept}")
    
    if failed:
        print(f"\n[*] Retente {len(failed)} departements...")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(download_file, dept): dept for dept in failed}
            for future in as_completed(futures):
                dept, result = future.result()
                if result is True:
                    success_count += 1
                    print(f"[OK] {dept} (retry)")
                elif result == "exists":
                    exists_count += 1
    
    print(f"\n[Termine] {success_count} telecharges, {exists_count} deja presents, {total - success_count - exists_count} echecs.")

if __name__ == "__main__":
    main()