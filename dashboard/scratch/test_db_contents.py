import os
from pymongo import MongoClient

try:
    uri = "mongodb://anjani:mypasswd@localhost:27018"
    client = MongoClient(uri)
    db = client.get_database('anjani_dashboard')
    bots = list(db.bots.find())
    print("BOTS IN DB:", len(bots))
    for idx, b in enumerate(bots):
        print(f"\n--- Bot {idx+1} ---")
        for k, v in b.items():
            if 'Key' in k or 'Token' in k:
                print(f"  {k}: [REDACTED]")
            else:
                print(f"  {k}: {repr(v)}")
except Exception as e:
    print("DB ERROR:", e)
