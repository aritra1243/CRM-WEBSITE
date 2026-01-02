from django.contrib import admin
from .models import Holiday

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = [
        'holiday_name',
        'holiday_type',
        'date_type',
        'get_date_display',
        'created_by',
        'created_at',
    ]
    
    list_filter = [
        'holiday_type',
        'date_type',
        'is_deleted',
        'created_at',
    ]
    
    search_fields = [
        'holiday_name',
        'description',
        'created_by__email',
        'created_by__first_name',
        'created_by__last_name',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'deleted_at',
        'restored_at',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'holiday_name',
                'holiday_type',
                'date_type',
                'description',
            )
        }),
        ('Date Information', {
            'fields': (
                'date',
                'from_date',
                'to_date',
            )
        }),
        ('User Tracking', {
            'fields': (
                'created_by',
                'updated_by',
                'deleted_by',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'deleted_at',
                'restored_at',
            )
        }),
        ('Deletion', {
            'fields': (
                'is_deleted',
            )
        }),
    )
    
    def get_date_display(self, obj):
        """Display date based on type"""
        if obj.date_type == 'single':
            return obj.date.strftime('%B %d, %Y') if obj.date else 'N/A'
        else:
            if obj.from_date and obj.to_date:
                return f"{obj.from_date.strftime('%b %d')} - {obj.to_date.strftime('%b %d, %Y')}"
            return 'N/A'
    get_date_display.short_description = 'Date(s)'
    
    def save_model(self, request, obj, form, change):
        """Set created_by or updated_by when saving through admin"""
        if not change:  # Creating new object
            obj.created_by = request.user
        else:  # Updating existing object
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, queryset):
        """Only show non-deleted holidays by default"""
        qs = super().get_queryset(queryset)
        return qs.filter(is_deleted=False)