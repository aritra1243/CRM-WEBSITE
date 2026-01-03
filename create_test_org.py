
import os
import django
from django.utils import timezone
from bson import ObjectId

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM_WEBSITE.settings')
django.setup()

from common.pymongo_utils import get_mongo_db
from superadminpanel.models import OrganisationMaster

def create_test_org():
    try:
        db = get_mongo_db()
        collection = db['organisation_master']
        
        # Check if already exists
        if collection.find_one({'organisation_code': 'TEST_ORG_001'}):
            print("Test organisation already exists.")
            return

        test_org = {
            'organisation_code': 'TEST_ORG_001',
            'organisation_name': 'Test Organisation Alpha',
            'email': 'test@alpha.com',
            'address': '123 Test St',
            'org_type': 'mother',
            'is_active': True,
            'created_at': timezone.now(),
            'updated_at': timezone.now(),
            'is_deleted': False
        }
        
        result = collection.insert_one(test_org)
        new_id = result.inserted_id
        
        # Update id field
        collection.update_one({'_id': new_id}, {'$set': {'id': new_id}})
        
        print(f"Successfully created test organisation with ID: {new_id}")
        
    except Exception as e:
        print(f"Error creating test organisation: {e}")

if __name__ == "__main__":
    create_test_org()
