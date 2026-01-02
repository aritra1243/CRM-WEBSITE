from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'common'
    
    def ready(self):
        """
        Patch djongo's cursor to handle Django 5.x's new %(N)s parameter format.
        """
        import re
        import djongo.cursor
        
        original_execute = djongo.cursor.Cursor.execute
        
        def patched_execute(self, sql, params=None):
            """
            Convert Django 5.x %(0)s, %(1)s placeholders to %s before executing.
            """
            # Handle SQL that might be wrapped in a tuple
            if isinstance(sql, tuple):
                sql = sql[0] if sql else sql
            
            if sql and params is not None:
                # Check if we have Django 5.x format with named placeholders
                if isinstance(sql, str) and re.search(r'%\(\d+\)s', sql):
                    # Convert %(0)s, %(1)s, %(2)s to %s
                    sql = re.sub(r'%\(\d+\)s', '%s', sql)
                    
                # Flatten params if nested
                if isinstance(params, (list, tuple)) and len(params) == 1:
                    inner = params[0]
                    if isinstance(inner, (list, tuple)):
                        params = tuple(inner)
            
            return original_execute(self, sql, params)
        
        # Replace the original execute method
        djongo.cursor.Cursor.execute = patched_execute
