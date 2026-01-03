from pymongo import MongoClient
import re

# Manual settings parse
with open(r'c:\Users\User\Desktop\NCRM_20_12_2025\ncrm\settings.py', 'r') as f:
    content = f.read()
    uri_match = re.search(r"'CLIENT':\s*{\s*'host':\s*'([^']+)'", content)
    if uri_match:
        uri = uri_match.group(1)
        client = MongoClient(uri)
        db = client['NCRM_2025']
        coll = db['custom_users_specialisations']
        doc = coll.find_one()
        print(f"Schema for custom_users_specialisations: {list(doc.keys()) if doc else 'Empty'}")
    else:
        print("Could not find URI in settings.py")
