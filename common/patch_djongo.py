import re
import djongo.cursor
from djongo.sql2mongo.query import Query
from logging import getLogger

logger = getLogger(__name__)

def unwrap_sql(sql):
    """Unwrap SQL from tuple/list if needed."""
    if isinstance(sql, (tuple, list)):
        if len(sql) > 0:
            return unwrap_sql(sql[0])
    return sql if isinstance(sql, str) else str(sql) if sql else ''

def flatten_params(params):
    """Flatten nested params."""
    if params is None:
        return None
    
    # Deeply flatten if it's a tuple of tuples
    if isinstance(params, (list, tuple)) and len(params) == 1:
        inner = params[0]
        if isinstance(inner, (list, tuple)):
            return flatten_params(inner)
            
    return tuple(params) if isinstance(params, list) else params

def convert_params(sql):
    """Clean up SQL for Djongo compatibility."""
    if isinstance(sql, str):
        original = sql
        # 1. Convert any %(name)s or %(N)s to %s
        new_sql = re.sub(r'%\([^)]+\)s', '%s', sql)
        # 2. Remove quotes from identifiers (djongo parser often fails with them)
        new_sql = new_sql.replace('"', '')
        # 3. Handle potential doubled escapes
        new_sql = re.sub(r'%%', '%', new_sql)
        
        return new_sql
    return sql

def apply_djongo_patches():
    """Apply robust patches to djongo to handle Django 5.x / 4.2 SQL generation."""
    
    print("Applying robust Djongo patches...")
    
    # 1. Patch Query.__init__
    original_query_init = Query.__init__
    
    def patched_query_init(self, client_conn, db_conn, connection_properties, sql, params):
        # Unwrap and convert before original init
        clean_sql = unwrap_sql(sql)
        clean_sql = convert_params(clean_sql)
        clean_params = flatten_params(params)
        
        # print(f"DJONGO_PATCH: Parsed SQL: {clean_sql[:100]}...")
        if "SELECT" in clean_sql:
            print(f"DJONGO_PATCH: SQL -> {clean_sql}")
        
        return original_query_init(self, client_conn, db_conn, connection_properties, clean_sql, clean_params)
    
    Query.__init__ = patched_query_init
    
    # 2. Patch Cursor.execute
    original_execute = djongo.cursor.Cursor.execute
    
    def patched_execute(self, sql, params=None):
        clean_sql = unwrap_sql(sql)
        clean_sql = convert_params(clean_sql)
        clean_params = flatten_params(params)
        
        return original_execute(self, clean_sql, clean_params)
    
    djongo.cursor.Cursor.execute = patched_execute
    
    print("Djongo patches applied successfully.")
