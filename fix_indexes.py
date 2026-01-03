import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM_WEBSITE.settings')
django.setup()

from common.pymongo_utils import get_mongo_db
from accounts.models import CustomUser

def fix_indexes():
    db = get_mongo_db()
    collection = db[CustomUser._meta.db_table]
    
    print(f"Checking indexes for {CustomUser._meta.db_table}...")
    
    # List current indexes
    indexes = collection.list_indexes()
    for index in indexes:
        name = index['name']
        key = index['key']
        print(f"Found index: {name} on {key}")
        
        # If it's the employee_id index, we want it to be sparse
        if 'employee_id' in key:
            print(f"Dropping index {name} to recreate as sparse...")
            try:
                collection.drop_index(name)
                print("Dropped. Recreating as unique + sparse...")
                collection.create_index([('employee_id', 1)], unique=True, sparse=True)
                print("Index recreated successfully.")
            except Exception as e:
                print(f"Error updating index: {e}")

if __name__ == "__main__":
    fix_indexes()
