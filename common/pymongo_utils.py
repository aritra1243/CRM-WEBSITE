"""
PyMongo direct utilities for saving Django models.

This module bypasses djongo's SQL-to-MongoDB translation which has issues
with Django 5.x's new parameter format (%(N)s instead of %s).
"""
from django.conf import settings
from django.utils import timezone
from pymongo import MongoClient
import urllib.parse


_client = None


def get_mongo_client():
    """Get or create a MongoDB client connection."""
    global _client
    if _client is None:
        db_config = settings.DATABASES.get('default', {})
        client_config = db_config.get('CLIENT', {})
        host = client_config.get('host', 'localhost')
        
        # Handle MongoDB URI connection string
        if host.startswith('mongodb'):
            _client = MongoClient(host)
        else:
            # Build connection from individual settings
            port = client_config.get('port', 27017)
            username = db_config.get('USER', '')
            password = db_config.get('PASSWORD', '')
            
            if username and password:
                uri = f"mongodb://{urllib.parse.quote_plus(username)}:{urllib.parse.quote_plus(password)}@{host}:{port}/"
            else:
                uri = f"mongodb://{host}:{port}/"
            _client = MongoClient(uri)
    
    return _client


def get_mongo_db():
    """Get the MongoDB database instance."""
    client = get_mongo_client()
    db_name = settings.DATABASES.get('default', {}).get('NAME', 'default')
    return client[db_name]


def get_next_id(collection):
    """Get the next available integer ID for a collection."""
    # Find the maximum id in the collection
    result = collection.find_one(
        {'id': {'$exists': True, '$ne': None}},
        sort=[('id', -1)],
        projection={'id': 1}
    )
    
    if result and result.get('id') is not None:
        return result['id'] + 1
    return 1


def pymongo_create(model_class, **kwargs):
    """
    Create a model instance and save it directly to MongoDB using PyMongo.
    Bypasses djongo's SQL parser.
    
    Args:
        model_class: The Django model class
        **kwargs: Field values to set on the model
    
    Returns:
        The created model instance with the generated ID
    """
    # Create model instance
    instance = model_class(**kwargs)
    
    # Get collection name
    collection_name = model_class._meta.db_table
    
    # Get the MongoDB collection
    db = get_mongo_db()
    collection = db[collection_name]
    
    # Generate a unique ID
    new_id = get_next_id(collection)
    
    # Build document from model fields
    document = {'id': new_id}
    
    for field in model_class._meta.fields:
        field_name = field.name
        if field_name == 'id':
            continue  # Already handled
        
        value = getattr(instance, field_name, None)
        
        # Handle ForeignKey fields
        if hasattr(field, 'related_model') and field.related_model is not None:
            # Get the actual value (should be the foreign key ID)
            fk_value = getattr(instance, f'{field_name}_id', None)
            if fk_value is not None:
                document[f'{field_name}_id'] = fk_value
            else:
                document[f'{field_name}_id'] = value.pk if value else None
        else:
            # Store the value directly
            document[field_name] = value
    
    # Insert document
    result = collection.insert_one(document)
    
    # Set the id on the instance
    instance.id = new_id
    
    return instance
