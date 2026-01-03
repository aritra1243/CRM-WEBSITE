import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM_WEBSITE.settings')
django.setup()

from common.pymongo_utils import get_mongo_db
from accounts.models import CustomUser

from superadminpanel.models import SpecialisationMaster, OrganisationMaster

def check_data():
    db = get_mongo_db()
    users_coll = db[CustomUser._meta.db_table]
    spec_coll = db[SpecialisationMaster._meta.db_table]
    org_coll = db[OrganisationMaster._meta.db_table]
    
    print(f"Total users: {users_coll.count_documents({})}")
    print(f"Total specialisations: {spec_coll.count_documents({})}")
    print(f"Total organisations: {org_coll.count_documents({})}")
    
    # List some users
    print("\n--- User Details ---")
    for user in users_coll.find():
        print(f"ID: {user.get('_id')} | Email: {user.get('email')} | Role: {user.get('role')} | Status: {user.get('approval_status')} | Active: {user.get('is_active')}")

if __name__ == "__main__":
    check_data()
