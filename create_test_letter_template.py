
import os
import django
from django.utils import timezone
from bson import ObjectId

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM_WEBSITE.settings')
django.setup()

from common.pymongo_utils import get_mongo_db
from superadminpanel.models import LetterTemplate

def create_test_template():
    try:
        db = get_mongo_db()
        collection = db['letter_templates']
        
        # Check if already exists
        if collection.find_one({'letter_type': 'offer'}):
            print("Test 'offer' template already exists.")
            return

        test_template = {
            'letter_type': 'offer',
            'template_content': '<p>This is a test offer letter.</p>',
            'is_trigger': False,
            'is_deleted': False,
            'created_at': timezone.now(),
            'updated_at': timezone.now()
        }
        
        result = collection.insert_one(test_template)
        new_id = result.inserted_id
        
        # Update id field
        collection.update_one({'_id': new_id}, {'$set': {'id': new_id}})
        
        print(f"Successfully created test letter template with ID: {new_id}")
        
    except Exception as e:
        print(f"Error creating test letter template: {e}")

if __name__ == "__main__":
    create_test_template()
