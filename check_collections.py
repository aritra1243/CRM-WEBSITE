
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM_WEBSITE.settings')
django.setup()

from common.pymongo_utils import get_mongo_db

def check_collections():
    try:
        db = get_mongo_db()
        print("Connected to MongoDB:", db.name)
        collections = db.list_collection_names()
        print("Collections found:", collections)
        
        # Check specific collections
        target_collections = ['organisation_master', 'superadminpanel_organisationmaster', 'custom_user']
        for col in target_collections:
            if col in collections:
                count = db[col].count_documents({})
                print(f"Collection '{col}' has {count} documents.")
            else:
                print(f"Collection '{col}' NOT found.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_collections()
