"""
Custom Djongo database backend wrapper for Django 5.x compatibility.

Django 5.x changed from %s positional placeholders to %(0)s named placeholders.
djongo5 doesn't support the new format, so this wrapper converts them back.
"""
import re
from djongo.base import DatabaseWrapper as DjongoDatabaseWrapper
from djongo.cursor import Cursor as DjongoCursor


class PatchedCursor(DjongoCursor):
    """
    A patched cursor that converts Django 5.x named placeholders back to positional.
    """
    
    def execute(self, sql, params=None):
        """
        Convert %(0)s, %(1)s, etc. to %s placeholders before executing.
        """
        # Handle SQL that might be wrapped in a tuple
        if isinstance(sql, tuple):
            sql = sql[0] if sql else sql
        
        if sql and params is not None:
            # Check if we have the new Django 5.x format with named placeholders
            if isinstance(sql, str) and re.search(r'%\(\d+\)s', sql):
                # Convert %(0)s, %(1)s, %(2)s to %s
                sql = re.sub(r'%\(\d+\)s', '%s', sql)
                
            # Handle params that might be wrapped in extra tuple/list layers
            if isinstance(params, (list, tuple)) and len(params) == 1:
                inner = params[0]
                if isinstance(inner, (list, tuple)):
                    params = tuple(inner)
        
        return super().execute(sql, params)


class DatabaseWrapper(DjongoDatabaseWrapper):
    """
    A custom database wrapper that uses the patched cursor.
    """
    
    def create_cursor(self, name=None):
        """
        Return a patched cursor instead of the default djongo cursor.
        """
        return PatchedCursor(
            self.client_connection,
            self.connection,
            self.Database
        )
