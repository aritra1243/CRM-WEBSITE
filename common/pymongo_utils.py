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


def pymongo_exists(model_class, **filters):
    """
    Check if a document exists using PyMongo directly.
    Bypasses djongo's SQL parser.
    
    Args:
        model_class: The Django model class
        **filters: Field filters to match (e.g., email='test@test.com')
    
    Returns:
        bool: True if document exists, False otherwise
    """
    collection_name = model_class._meta.db_table
    db = get_mongo_db()
    collection = db[collection_name]
    
    result = collection.find_one(filters, projection={'_id': 1})
    return result is not None


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
            continue
            
        value = getattr(instance, field_name, None)
        
        if value is None:
            continue
            
        # Handle ForeignKey fields
        if hasattr(field, 'related_model') and field.related_model is not None:
            # Get the actual value (should be the foreign key ID)
            fk_value = getattr(instance, f'{field_name}_id', None)
            if fk_value is not None:
                document[f'{field_name}_id'] = fk_value
            else:
                document[f'{field_name}_id'] = value.pk if value else None
        else:
            # Handle FileField / ImageField - convert to string path
            from django.db.models.fields.files import FieldFile
            if isinstance(value, FieldFile):
                # Convert to string path, or empty string if no file
                document[field_name] = value.name if value and value.name else ''
            else:
                # Store the value directly
                document[field_name] = value
    
    # Insert document
    result = collection.insert_one(document)
    
    # Set the id on the instance
    instance.id = new_id
    
    return instance


def pymongo_create_user(model_class, password=None, **kwargs):
    """
    Create a user with proper password hashing using PyMongo directly.
    
    Args:
        model_class: The CustomUser model class
        password: Plain text password to hash
        **kwargs: Other user fields
    
    Returns:
        The created user instance
    """
    from django.contrib.auth.hashers import make_password
    
    # Hash the password
    if password:
        kwargs['password'] = make_password(password)
    
    return pymongo_create(model_class, **kwargs)


def pymongo_update(model_class, filter_by, **updates):
    """
    Update a document using PyMongo directly.
    """
    collection_name = model_class._meta.db_table
    db = get_mongo_db()
    collection = db[collection_name]
    
    result = collection.update_one(filter_by, {'$set': updates})
    return result.modified_count > 0


def pymongo_filter(model_class, query=None, sort=None, limit=None):
    """
    Filter documents using PyMongo directly and return model instances.
    Bypasses djongo's SQL parser.
    
    Args:
        model_class: The Django model class
        query: PyMongo query dict (e.g., {'role': 'writer'})
        sort: PyMongo sort list (e.g., [('first_name', 1)])
        limit: Max number of results
    
    Returns:
        list: List of model instances
    """
    collection_name = model_class._meta.db_table
    db = get_mongo_db()
    collection = db[collection_name]
    
    if query is None:
        query = {}
    
    cursor = collection.find(query)
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(limit)
        
    instances = []
    for doc in cursor:
        # Create instance without saving (to avoid DB calls)
        # We need to handle field mapping if needed
        data = doc.copy()
        if '_id' in data:
            del data['_id']
            
        instance = model_class(**data)
        # Force the ID from the doc as it might not be in **data if named differently
        if 'id' in doc:
            instance.id = doc['id']
            
        instances.append(instance)
        
    return instances


def pymongo_get(model_class, **filters):
    """
    Get a single model instance using PyMongo directly.
    Returns None if not found.
    """
    results = pymongo_filter(model_class, query=filters, limit=1)
    return results[0] if results else None


def pymongo_prefetch_m2m(instances, field_name, related_model, join_table, source_field, target_field):
    """
    Prefetch Many-to-Many relationships using PyMongo.
    
    Args:
        instances: List of model instances
        field_name: Name to use for the attached attribute (prefix with pymongo_)
        related_model: The related Django model class
        join_table: Name of the join table collection
        source_field: Field name in join table for current model
        target_field: Field name in join table for related model
    """
    if not instances:
        return
        
    # Get unique IDs from instances
    ids = []
    for inst in instances:
        val = getattr(inst, 'id', None)
        if val is not None:
            ids.append(val)
            
    if not ids:
        return
        
    db = get_mongo_db()
    join_coll = db[join_table]
    
    # Get mappings
    mappings = list(join_coll.find({source_field: {'$in': ids}}))
    target_ids = list(set(m[target_field] for m in mappings))
    
    # Fetch related objects
    related_objects = pymongo_filter(related_model, query={'id': {'$in': target_ids}})
    related_map = {obj.id: obj for obj in related_objects}
    
    # Attach to instances
    attr_name = f"pymongo_{field_name}"
    for inst in instances:
        inst_id = getattr(inst, 'id', None)
        inst_target_ids = [m[target_field] for m in mappings if m[source_field] == inst_id]
        inst_related = [related_map[tid] for tid in inst_target_ids if tid in related_map]
        setattr(inst, attr_name, inst_related)


def pymongo_update_m2m(instance_id, join_table, source_field, target_field, related_ids):
    """
    Update Many-to-Many relationships using PyMongo directly.
    
    Args:
        instance_id: ID of the source model instance
        join_table: Name of the join table collection
        source_field: Field name in join table for current model
        target_field: Field name in join table for related model
        related_ids: List of IDs for the related model instances
    """
    db = get_mongo_db()
    collection = db[join_table]
    
    # 1. Clear existing mappings for this instance
    collection.delete_many({source_field: instance_id})
    
    # 2. Insert new mappings
    if related_ids:
        # Convert related_ids to correct type if needed (currently they should be ints or strings)
        new_mappings = [
            {source_field: instance_id, target_field: rid}
            for rid in related_ids
        ]
        
        # We need to make sure IDs are integers if the database uses integers
        # Most IDs in this project are integers
        for mapping in new_mappings:
            try:
                mapping[target_field] = int(mapping[target_field])
            except (ValueError, TypeError):
                pass
                
        collection.insert_many(new_mappings)
