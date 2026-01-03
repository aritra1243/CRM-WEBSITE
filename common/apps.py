from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'common'
    
    def ready(self):
        """
        Apply robust patches to djongo at startup.
        """
        from .patch_djongo import apply_djongo_patches
        apply_djongo_patches()
