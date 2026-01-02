from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
import random
import string

class Holiday(models.Model):
    """Holiday Master Model"""
    
    HOLIDAY_TYPE_CHOICES = [
        ('full_day', 'Full Day'),
        ('half_day', 'Half Day'),
    ]
    
    DATE_TYPE_CHOICES = [
        ('single', 'Single'),
        ('consecutive', 'Consecutive Days'),
    ]
    
    # Basic Information
    holiday_name = models.CharField(max_length=255, null=True, blank=True)
    holiday_type = models.CharField(max_length=20, choices=HOLIDAY_TYPE_CHOICES, default='full_day')
    date_type = models.CharField(max_length=20, choices=DATE_TYPE_CHOICES, default='single')
    
    # Date fields
    date = models.DateField(null=True, blank=True)  # For single date
    from_date = models.DateField(null=True, blank=True)  # For consecutive dates
    to_date = models.DateField(null=True, blank=True)  # For consecutive dates
    
    # Description
    description = models.TextField(blank=True, null=True)
    
    # Lifecycle Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='holidays_created')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='holidays_updated')
    deleted_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='holidays_deleted')
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'holidays'
        ordering = ['-created_at']
        verbose_name = 'Holiday'
        verbose_name_plural = 'Holidays'
    
    def __str__(self):
        if self.date_type == 'single':
            return f"{self.holiday_name} - {self.date}"
        return f"{self.holiday_name} - {self.from_date} to {self.to_date}"
    

class PriceMaster(models.Model):
    """Price Master Model"""
    
    CATEGORY_CHOICES = [
        ('IT', 'IT'),
        ('NON-IT', 'NON-IT'),
    ]
    
    LEVEL_CHOICES = [
        ('basic', 'Basic'),
        ('intermediate', 'Intermediate'),
        ('advance', 'Advance'),
    ]
    
    # Basic Information
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    price_per_word = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Lifecycle Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='prices_created'
    )
    updated_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='prices_updated'
    )
    deleted_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='prices_deleted'
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'price_master'
        ordering = ['-created_at']
        verbose_name = 'Price Master'
        verbose_name_plural = 'Price Masters'
        unique_together = ['category', 'level']
    
    def __str__(self):
        return f"{self.get_category_display()} - {self.get_level_display()} - ₹{self.price_per_word}/word"


class ReferencingMaster(models.Model):
    """Referencing Master Model"""
    
    # Basic Information
    referencing_style = models.CharField(max_length=100)
    used_in = models.CharField(max_length=255)
    
    # Lifecycle Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='references_created'
    )
    updated_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='references_updated'
    )
    deleted_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='references_deleted'
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'referencing_master'
        ordering = ['-created_at']
        verbose_name = 'Referencing Master'
        verbose_name_plural = 'Referencing Masters'
    
    def __str__(self):
        return f"{self.referencing_style} - {self.used_in}"
    
class AcademicWritingMaster(models.Model):
    """Academic Writing Style Master Model"""
    
    # Basic Information
    writing_style = models.CharField(max_length=100)
    
    # Lifecycle Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='writings_created'
    )
    updated_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='writings_updated'
    )
    deleted_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='writings_deleted'
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'academic_writing_master'
        ordering = ['-created_at']
        verbose_name = 'Academic Writing Style'
        verbose_name_plural = 'Academic Writing Styles'
    
    def __str__(self):
        return self.writing_style
    
class ProjectGroupMaster(models.Model):
    """Project Group Master Model"""
    
    # Basic Information
    project_group_name = models.CharField(max_length=255)
    project_group_prefix = models.CharField(max_length=50, unique=True)
    
    # Lifecycle Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='project_groups_created'
    )
    updated_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='project_groups_updated'
    )
    deleted_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='project_groups_deleted'
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'project_group_master'
        ordering = ['-created_at']
        verbose_name = 'Project Group Master'
        verbose_name_plural = 'Project Group Masters'
    
    def __str__(self):
        return f"{self.project_group_name} ({self.project_group_prefix})"


    
    @staticmethod
    def generate_task_id(project_prefix, task_code):
        """Generate task ID: {ProjectPrefix}-{TaskCode}"""
        return f"{project_prefix}-{task_code}"
    
    def calculate_duration(self):
        """Calculate duration between start and completion"""
        if self.start_date and self.completed_at:
            duration = self.completed_at - self.start_date
            return duration
        return None
    
    def update_work_hours(self):
        """Update work hours based on status timestamps"""
        if self.start_date and self.completed_at:
            duration = self.completed_at - self.start_date
            self.work_hours = duration.total_seconds() / 3600  # Convert to hours
            self.save(update_fields=['work_hours'])

class SpecialisationMaster(models.Model):
    """Specialisation Master Model"""
    
    # Basic Information
    specialisation_name = models.CharField(max_length=255)
    
    # Lifecycle Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='specialisations_created'
    )
    updated_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='specialisations_updated'
    )
    deleted_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='specialisations_deleted'
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'specialisation_master'
        ordering = ['-created_at']
        verbose_name = 'Specialisation Master'
        verbose_name_plural = 'Specialisation Masters'
    
    def __str__(self):
        return self.specialisation_name


class OrganisationMaster(models.Model):
    """Organisation Master Model - Mother and Child Organizations"""
    
    ORG_TYPE_CHOICES = [
        ('mother', 'Mother'),
        ('child', 'Child'),
    ]
    
    # Basic Information
    organisation_code = models.CharField(max_length=50, unique=True)
    organisation_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Organisation Type
    org_type = models.CharField(max_length=10, choices=ORG_TYPE_CHOICES, default='mother')
    parent_organisation = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_organisations'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Lifecycle Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='organisations_created'
    )
    updated_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='organisations_updated'
    )
    deleted_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='organisations_deleted'
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'organisation_master'
        ordering = ['-created_at']
        verbose_name = 'Organisation Master'
        verbose_name_plural = 'Organisation Masters'
    
    def __str__(self):
        return f"{self.organisation_code} - {self.organisation_name}"
    
    @property
    def is_mother(self):
        """Check if this is a mother (parent) organisation"""
        return self.org_type == 'mother'
    
    @property
    def status_display(self):
        """Return Active or Inactive status"""
        return 'Active' if self.is_active else 'Inactive'



class JobDrop(models.Model):
    """
    Track when marketing users submit new jobs.
    Allows SuperAdmin to view, edit, and manage job submissions.
    """
    
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('viewed', 'Viewed'),
        ('edited', 'Edited'),
        ('rejected', 'Rejected'),
    ]
    
    # Link to marketing job
    job = models.OneToOneField(
        'marketing.Job',
        on_delete=models.CASCADE,
        related_name='job_drop'
    )
    
    # Marketing user who created the job
    submitted_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='job_drops_submitted'
    )
    
    # SuperAdmin who edited the job (if any)
    edited_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_drops_edited'
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='submitted'
    )
    
    # Change history (JSON to store what was changed)
    changes_history = models.JSONField(
        default=dict,
        blank=True,
        help_text="Track changes made by SuperAdmin"
    )
    
    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    last_modified_at = models.DateTimeField(auto_now=True)
    
    # Additional metadata
    is_new = models.BooleanField(default=True)  # Mark as new job drop
    priority = models.IntegerField(default=0)   # Priority level for display
    
    class Meta:
        db_table = 'job_drops'
        ordering = ['-submitted_at']
        verbose_name = 'Job Drop'
        verbose_name_plural = 'Job Drops'

    def __str__(self):
        return f"Job Drop: {self.job.system_id} by {self.submitted_by.email}"


class LetterTemplate(models.Model):
    """Letter Template Master Model"""
    
    LETTER_TYPE_CHOICES = [
        ('appointment', 'Appointment Letter'),
        ('experience', 'Experience Letter'),
        ('joining', 'Joining Letter'),
        ('no_objection', 'No Objection Letter'),
        ('offer', 'Offer Letter'),
        ('payment', 'Payment Letter'),
        ('relieving', 'Relieving Letter'),
        ('salary_increment', 'Salary Increment Letter'),
        ('termination', 'Termination Letter'),
        ('warning', 'Warning Letter'),
    ]
    
    # Basic Information
    letter_type = models.CharField(max_length=50, choices=LETTER_TYPE_CHOICES)
    template_content = models.TextField(help_text="HTML template content")
    is_trigger = models.BooleanField(default=False, help_text="Triggers specific system actions")
    
    # Lifecycle Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='letter_templates_created'
    )
    updated_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='letter_templates_updated'
    )
    deleted_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='letter_templates_deleted'
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'letter_templates'
        verbose_name = 'Letter Template'
        verbose_name_plural = 'Letter Templates'
    
    def __str__(self):
        return self.get_letter_type_display()


class GeneratedLetter(models.Model):
    """Model to store generated letters for users"""
    
    # Letter identification
    letter_id = models.CharField(max_length=50, unique=True)
    
    # Relationships
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='received_letters'
    )
    template = models.ForeignKey(
        LetterTemplate,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_letters'
    )
    
    # Letter content
    letter_type = models.CharField(max_length=50)
    rendered_content = models.TextField(help_text="Final rendered HTML content")
    
    # Metadata
    generated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='letters_generated'
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    
    # Store form field values as JSON for reuse (e.g., offer letter -> joining letter)
    field_data = models.TextField(blank=True, null=True, help_text="JSON of form field values")
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='letters_deleted'
    )
    
    class Meta:
        db_table = 'generated_letters'
        verbose_name = 'Generated Letter'
        verbose_name_plural = 'Generated Letters'
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"{self.letter_id} - {self.letter_type} for {self.user.get_full_name()}"
