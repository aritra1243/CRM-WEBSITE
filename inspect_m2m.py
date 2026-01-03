from common.pymongo_utils import get_mongo_db
import json

def inspect_collections():
    db = get_mongo_db()
    collections = db.list_collection_names()
    print(f"Collections: {collections}")
    
    # Check custom_users_specialisations
    if 'custom_users_specialisations' in collections:
        print("\n--- custom_users_specialisations ---")
        for doc in db['custom_users_specialisations'].find().limit(5):
            print(doc)
            
    # Check specialisation_master
    if 'specialisation_master' in collections:
        print("\n--- specialisation_master ---")
        for doc in db['specialisation_master'].find().limit(5):
            print(doc)

if __name__ == "__main__":
    inspect_collections()
