from django.db import models
from djongo import models as djongo_models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from accounts.models import CustomUser
from django.core.validators import RegexValidator, MinValueValidator
import os
import random
import string
import time

def job_attachment_path(instance, filename):
    """Generate file path for job attachments"""
    return f'job_attachments/{instance.job.system_id}/{filename}'


class Job(models.Model):
    """Main Job model with comprehensive tracking"""

    # Use Mongo ObjectId as primary key to match stored documents
    id = djongo_models.ObjectIdField(primary_key=True, db_column='_id')
    CATEGORY_CHOICES = [
        ('IT', 'IT'),
        ('NON-IT', 'Non-IT'),
        ('FINANCE', 'Finance'),
    ]

    REFERENCING_STYLE_CHOICES = [
        ('harvard', 'Harvard'),
        ('apa', 'APA'),
        ('mla', 'MLA'),
        ('ieee', 'IEEE'),
        ('vancouver', 'Vancouver'),
        ('chicago', 'Chicago'),
    ]
    
    WRITING_STYLE_CHOICES = [
        ('proposal', 'Proposal'),
        ('report', 'Report'),
        ('essay', 'Essay'),
        ('dissertation', 'Dissertation'),
        ('business_report', 'Business Report'),
        ('personal_development', 'Personal Development'),
        ('reflection_writing', 'Reflection Writing'),
        ('case_study', 'Case Study'),
    ]
    LEVEL_CHOICES = [
        ('basic', 'Basic'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('allocated', 'Allocated'),
        ('in_progress', 'In Progress'),
        ('unallocated', 'Unallocated'),
        ('completed', 'Completed'),
        ('hold', 'Hold'),
        ('query', 'Query'),
        ('cancelled', 'Cancelled'),
        ('Review', 'Review'),
        ('In_Review', 'In_Review'),
    ]
    
    # Primary identifiers
    system_id = models.CharField(max_length=50, unique=True, db_index=True)
    job_id = models.CharField(max_length=200, unique=True, db_index=True)
    
    # Initial Form Fields
    instruction = models.TextField(help_text="Minimum 50 characters required")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        blank=True,
        null=True
    )
    customer_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Customer ID from marketing_customers"
    )
    customer_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Customer name captured at final submission"
    )

    # AI Generated Summary Fields
    topic = models.CharField(max_length=500, blank=True, null=True)
    word_count = models.IntegerField(blank=True, null=True)
    referencing_style = models.CharField(
        max_length=20, 
        choices=REFERENCING_STYLE_CHOICES,
        blank=True, 
        null=True
    )
    writing_style = models.CharField(
        max_length=30,
        choices=WRITING_STYLE_CHOICES,
        blank=True,
        null=True
    )
    job_summary = models.TextField(blank=True, null=True)
    
    # AI Summary Metadata
    ai_summary_version = models.IntegerField(default=0)
    ai_summary_generated_at = models.JSONField(default=list, blank=True)  # Array of timestamps
    job_card_degree = models.IntegerField(default=5)  # 0-5 based on missing fields
    final_form_opened_at = models.DateTimeField(null=True, blank=True)
    final_form_submitted_at = models.DateTimeField(null=True, blank=True)
    expected_deadline = models.DateTimeField(null=True, blank=True)
    strict_deadline = models.DateTimeField(null=True, blank=True)
    software = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    system_expected_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    level = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        blank=True,
        null=True
    )


    # User Relations (using string reference for MongoDB compatibility)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='jobs_created'
    )
    allocated_to = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs_allocated'
    )
    project_group = models.ForeignKey(
        'superadminpanel.ProjectGroupMaster',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_jobs'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Timestamps - Initial Form
    created_at = models.DateTimeField(default=timezone.now)
    initial_form_submitted_at = models.DateTimeField(null=True, blank=True)
    initial_form_last_saved_at = models.DateTimeField(null=True, blank=True)
    job_name_validated_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps - AI Summary
    ai_summary_requested_at = models.DateTimeField(null=True, blank=True)
    ai_summary_accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Job Creation Method - Track whether job was created manually or via AI summary
    job_creation_method = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual Entry'),
            ('ai_summary', 'AI Summary Generated'),
        ],
        default='ai_summary',
        help_text='Whether job was created manually or via AI summary workflow'
    )
    
    # General timestamps
    updated_at = models.DateTimeField(auto_now=True)
    deadline = models.DateField(null=True, blank=True)
    
    # Add these new fields for writer submissions
    structure_submitted = models.BooleanField(default=False)
    structure_submitted_at = models.DateTimeField(null=True, blank=True)
    
    final_copy_submitted = models.BooleanField(default=False)
    final_copy_submitted_at = models.DateTimeField(null=True, blank=True)
    
    writer_selected_at = models.DateTimeField(null=True, blank=True)


    allocated_to_process = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='process_jobs_allocated'
    )
    allocated_to_process_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'marketing_jobs'
        ordering = ['-created_at']
        verbose_name = 'Job'
        verbose_name_plural = 'Jobs'
        indexes = [
            models.Index(fields=['system_id']),
            models.Index(fields=['job_id']),
            models.Index(fields=['status']),
            models.Index(fields=['created_by']),
        ]
    
    def __str__(self):
        return f"{self.system_id} - {self.job_id}"
    
    @staticmethod
    def generate_system_id(max_retries=100):
        """
        Generate unique system ID: CH-XXXXXX
        Where XXXXXX is 6 random alphanumeric characters (A-Z, 0-9)
        Example: CH-A3K9M2, CH-7B4XP1
        
        Falls back to timestamp-based ID with sequence if random generation fails.
        Uses raw MongoDB query for more reliable duplicate checking.
        
        Args:
            max_retries: Maximum number of attempts before using timestamp fallback
        
        Raises:
            RuntimeError: If unable to generate unique ID after max_retries attempts
        """
        import logging
        from django.db import connection
        logger = logging.getLogger('marketing')
        
        # Try random generation with increased attempts
        for attempt in range(max_retries):
            # Generate 6 random alphanumeric characters
            random_part = ''.join(random.choices(
                string.ascii_uppercase + string.digits, 
                k=6
            ))
            system_id = f"CH-{random_part}"
            
            # Use raw count query for more reliable checking
            try:
                count = Job.objects.filter(system_id=system_id).count()
                if count == 0:
                    logger.info(f"Generated unique random system_id: {system_id} (attempt {attempt+1})")
                    return system_id
            except Exception as e:
                logger.warning(f"Error checking system_id in attempt {attempt+1}: {str(e)}")
                # Continue trying
                continue
        
        # Fallback 1: Use timestamp-based ID with sequence
        logger.info("Random generation exhausted, using timestamp fallback")
        base_timestamp = int(time.time() * 1000) % 1000000
        
        for seq in range(100):  # Try up to 100 variations
            if seq == 0:
                timestamp_id = f"CH-{base_timestamp:06d}"
            else:
                # Add sequence number to timestamp
                timestamp_id = f"CH-{(base_timestamp + seq) % 1000000:06d}"
            
            try:
                count = Job.objects.filter(system_id=timestamp_id).count()
                if count == 0:
                    logger.info(f"Using timestamp-based system_id: {timestamp_id}")
                    return timestamp_id
            except Exception as e:
                logger.error(f"Error checking timestamp system_id: {str(e)}")
                continue
        
        # Fallback 2: Use UUID-based ID as last resort
        import uuid
        uuid_id = f"CH-{str(uuid.uuid4())[:6].upper()}"
        logger.warning(f"Using UUID-based system_id as last resort: {uuid_id}")
        return uuid_id
    
    def calculate_degree(self):
        """Calculate job card degree based on missing fields"""
        required_fields = [
            self.topic,
            self.word_count,
            self.referencing_style,
            self.writing_style,
            self.job_summary
        ]
        missing_count = sum(1 for field in required_fields if not field)
        self.job_card_degree = missing_count
        return missing_count
    
    def can_regenerate_summary(self):
        """Check if summary can be regenerated (max 3 versions)"""
        return self.ai_summary_version < 3
    
    def should_auto_accept(self):
        """Determine if summary should be auto-accepted"""
        return self.job_card_degree == 0 or self.ai_summary_version >= 3


class JobAttachment(models.Model):
    """Model for job attachments with validation"""
    
    ALLOWED_EXTENSIONS = ['pdf', 'docx', 'jpg', 'jpeg', 'png']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
    
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(
        upload_to=job_attachment_path,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)
        ]
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()  # in bytes
    uploaded_at = models.DateTimeField(default=timezone.now)
    uploaded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='uploaded_attachments'
    )
    
    class Meta:
        db_table = 'job_attachments'
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"{self.job.system_id} - {self.original_filename}"
    
    def clean(self):
        """Validate file size"""
        from django.core.exceptions import ValidationError
        if self.file.size > self.MAX_FILE_SIZE:
            raise ValidationError(
                f'File size must not exceed 10MB. Current size: {self.file.size / (1024*1024):.2f}MB'
            )
    
    def get_file_extension(self):
        """Get file extension"""
        return os.path.splitext(self.original_filename)[1].lower()


class JobSummaryVersion(models.Model):
    """Store each AI summary generation version"""
    
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='summary_versions'
    )
    version_number = models.IntegerField()
    
    # Summary fields for this version
    topic = models.CharField(max_length=500, blank=True, null=True)
    word_count = models.IntegerField(blank=True, null=True)
    referencing_style = models.CharField(max_length=20, blank=True, null=True)
    writing_style = models.CharField(max_length=30, blank=True, null=True)
    job_summary = models.TextField(blank=True, null=True)
    
    # Metadata
    degree = models.IntegerField()  # 0-5 missing fields
    generated_at = models.DateTimeField(default=timezone.now)
    performed_by = models.CharField(max_length=50, default='system')
    ai_model_used = models.CharField(max_length=50, default='gpt-4o-mini')
    
    class Meta:
        db_table = 'job_summary_versions'
        ordering = ['version_number']
        indexes = [
            models.Index(fields=['job', 'version_number']),
        ]
    
    def __str__(self):
        return f"{self.job.system_id} - V{self.version_number} (Degree: {self.degree})"


class JobActionLog(models.Model):
    """Audit log for all job actions - integrates with your ActivityLog pattern"""
    
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('initial_form_submitted', 'Initial Form Submitted'),
        ('initial_form_saved', 'Initial Form Saved'),
        ('job_name_validated', 'Job Name Validated'),
        ('ai_summary_requested', 'AI Summary Requested'),
        ('ai_summary_generated', 'AI Summary Generated'),
        ('ai_summary_accepted', 'AI Summary Accepted'),
        ('status_changed', 'Status Changed'),
        ('allocated', 'Allocated'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
    ]
    
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='action_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    performed_by_type = models.CharField(
        max_length=20,
        choices=[('user', 'User'), ('system', 'System')],
        default='user'
    )
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'job_action_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['job']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.job.system_id} - {self.action} at {self.timestamp}"


# Utility function to log job actions to ActivityLog
def log_job_activity(job, event_key, category=None, performed_by=None, metadata=None):
    """
    Logs job-related activities to the main ActivityLog table
    This integrates with your existing ActivityLog system
    """
    from accounts.models import ActivityLog
    
    if metadata is None:
        metadata = {}
    
    if category is None:
        category = ActivityLog.CATEGORY_JOB
    
    # Add job-specific metadata
    metadata.update({
        'job_system_id': job.system_id,
        'job_id': job.job_id,
        'job_status': job.status,
    })
    
    # Add new category for jobs if not exists
    ActivityLog.objects.create(
        event_key=event_key,
        category=category,
        subject_user=job.created_by,  # The marketing user who created the job
        performed_by=performed_by,
        metadata=metadata,
    )
class Customer(models.Model):
    """Customer model for marketing module"""
    
    # Use Mongo ObjectId as primary key
    id = djongo_models.ObjectIdField(primary_key=True, db_column='_id')
    
    # Primary identifier
    customer_id = models.CharField(
        max_length=50, 
        unique=True, 
        db_index=True,
        editable=False
    )
    
    # Customer details
    customer_name = models.CharField(
        max_length=255,
        help_text="Minimum 3 characters required"
    )
    
    customer_email = models.EmailField(
        unique=True,
        db_index=True
    )
    
    phone_regex = RegexValidator(
        regex=r'^\d{10}$',
        message="Phone number must be exactly 10 digits"
    )
    customer_phone = models.CharField(
        max_length=10,
        validators=[phone_regex]
    )
    
    targeted_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(1)],
        help_text="Target amount in INR"
    )
    
    current_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Current amount accumulated from jobs"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Relations
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='customers_created'
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # KPI Cache (updated via signals/methods)
    total_projects = models.IntegerField(default=0)
    completed_projects = models.IntegerField(default=0)
    cancelled_projects = models.IntegerField(default=0)
    projects_with_issues = models.IntegerField(default=0)
    total_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    it_projects = models.IntegerField(default=0)
    non_it_projects = models.IntegerField(default=0)
    finance_projects = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'marketing_customers'
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        indexes = [
            models.Index(fields=['customer_id']),
            models.Index(fields=['customer_email']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.customer_id} - {self.customer_name}"
    
    @staticmethod
    def generate_customer_id():
        """Generate unique customer ID: CUST-timestamp_ms"""
        timestamp_ms = int(time.time() * 1000)
        return f"CUST-{timestamp_ms}"
    
    def clean(self):
        """Custom validation"""
        if len(self.customer_name) < 3:
            raise ValidationError({
                'customer_name': 'Customer name must be at least 3 characters long.'
            })
    
    def save(self, *args, **kwargs):
        """Override save to generate customer_id if not exists"""
        if not self.customer_id:
            self.customer_id = self.generate_customer_id()
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def update_kpis(self):
        """Update customer KPIs from related jobs"""
        from marketing.models import Job
        from decimal import Decimal, InvalidOperation
        
        def _to_decimal(value):
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                return Decimal('0')
        
        jobs = Job.objects.filter(customer=self)
        
        self.total_projects = jobs.count()
        self.completed_projects = jobs.filter(status='completed').count()
        self.cancelled_projects = jobs.filter(status='cancelled').count()
        self.projects_with_issues = jobs.filter(status__in=['query', 'hold']).count()
        
        # Financial KPIs
        self.total_order_amount = sum(
            _to_decimal(job.amount or 0) for job in jobs if job.amount is not None
        )
        self.total_paid_amount = sum(
            _to_decimal(job.paid_amount or 0) for job in jobs if hasattr(job, 'paid_amount') and job.paid_amount is not None
        )
        self.remaining_amount = self.total_order_amount - self.total_paid_amount
        
        # Category breakdown
        self.it_projects = jobs.filter(category='IT').count()
        self.non_it_projects = jobs.filter(category='NON-IT').count()
        self.finance_projects = jobs.filter(category='FINANCE').count()
        
        # Update current amount
        self.current_amount = self.total_order_amount
        
        self.save(update_fields=[
            'total_projects', 'completed_projects', 'cancelled_projects',
            'projects_with_issues', 'total_order_amount', 'total_paid_amount',
            'remaining_amount', 'it_projects', 'non_it_projects', 'finance_projects',
            'current_amount'
        ])


class CustomerActionLog(models.Model):
    """Audit log for customer actions"""
    
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('activated', 'Activated'),
        ('deactivated', 'Deactivated'),
        ('kpi_updated', 'KPI Updated'),
    ]
    
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='action_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'customer_action_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.customer.customer_id} - {self.action} at {self.timestamp}"


class WriterSubmission(models.Model):
    """Model to track writer submissions (Structure and Final Copy)"""
    
    SUBMISSION_TYPE_CHOICES = [
        ('structure', 'Structure'),
        ('final_copy', 'Final Copy'),
    ]
    
    SUBMISSION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    # Use Mongo ObjectId as primary key
    id = djongo_models.ObjectIdField(primary_key=True, db_column='_id')
    
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='writer_submissions'
    )
    
    submitted_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='submissions_made'
    )
    
    submission_type = models.CharField(
        max_length=20,
        choices=SUBMISSION_TYPE_CHOICES
    )
    
    notes = models.TextField(
        help_text="Structure: 250 words, Final Copy: 3000 words"
    )
    
    status = models.CharField(
        max_length=20,
        choices=SUBMISSION_STATUS_CHOICES,
        default='pending'
    )
    
    # Timestamps
    submitted_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'writer_submissions'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['job']),
            models.Index(fields=['submitted_by']),
            models.Index(fields=['submission_type']),
        ]
        unique_together = [['job', 'submission_type', 'submitted_by']]
    
    def __str__(self):
        return f"{self.job.system_id} - {self.submission_type} by {self.submitted_by.get_full_name()}"


def structure_upload_path(instance, filename):
    """Generate file path for structure submissions - no duplicates"""
    # Extract file extension
    import os
    ext = os.path.splitext(filename)[1]
    # Use UUID for unique filename
    import uuid
    unique_filename = f"{uuid.uuid4()}{ext}"
    return f'structure/{instance.submission.job.system_id}/{unique_filename}'


def final_copy_upload_path(instance, filename):
    """Generate file path for final copy submissions - no duplicates"""
    # Extract file extension
    import os
    ext = os.path.splitext(filename)[1]
    # Use UUID for unique filename
    import uuid
    unique_filename = f"{uuid.uuid4()}{ext}"
    return f'final_copy/{instance.submission.job.system_id}/{unique_filename}'


class SubmissionFile(models.Model):
    """Model for submission files"""
    
    # Use Mongo ObjectId as primary key
    id = djongo_models.ObjectIdField(primary_key=True, db_column='_id')
    
    submission = models.ForeignKey(
        WriterSubmission,
        on_delete=models.CASCADE,
        related_name='files'
    )
    
    file = models.FileField(
        upload_to='submission_files/'
    )
    
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()  # in bytes
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'submission_files'
        ordering = ['uploaded_at']
    
    def save(self, *args, **kwargs):
        """Override save to set correct upload path based on submission type"""
        import os
        import uuid
        
        if self.file:
            # Generate the correct path based on submission type
            ext = os.path.splitext(self.file.name)[1]
            unique_filename = f"{uuid.uuid4()}{ext}"
            
            if self.submission.submission_type == 'structure':
                path = f'structure/{self.submission.job.system_id}/{unique_filename}'
            else:  # final_copy
                path = f'final_copy/{self.submission.job.system_id}/{unique_filename}'
            
            # Set the file name with the correct path
            self.file.name = path
        
        super().save(*args, **kwargs)
    

def payment_receipt_path(instance, filename):
    """Generate path for payment receipts"""
    import os
    ext = os.path.splitext(filename)[1]
    return f'payment_receipts/{instance.payment_id}{ext}'

class Payment(models.Model):
    """Payment entry model"""
    
    # Use Mongo ObjectId as primary key
    id = djongo_models.ObjectIdField(primary_key=True, db_column='_id')
    
    payment_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True
    )
    
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(1)]
    )
    
    payment_date = models.DateTimeField(
        help_text="Payment timestamp in IST"
    )
    
    bank_name = models.CharField(max_length=100)
    
    notes = models.TextField(blank=True, null=True)
    
    receipt = models.FileField(
        upload_to=payment_receipt_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'gif'])]
    )
    
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payments_recorded'
    )
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'marketing_payments'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['payment_id']),
            models.Index(fields=['payment_date']),
        ]
        
    def __str__(self):
        return f"{self.payment_id} - {self.customer.customer_name}"
        
    def save(self, *args, **kwargs):
        if not self.payment_id:
            # Generate ID: PAY-YYYYMMDDHHMMSS
            # Use current time in IST (UTC+5:30)
            now = timezone.now().astimezone(timezone.get_current_timezone())
            timestamp = now.strftime('%Y%m%d%H%M%S')
            self.payment_id = f"PAY-{timestamp}"
            
        if not self.payment_date:
            self.payment_date = timezone.now()
        super().save(*args, **kwargs)

    @property
    def amount_display(self):
        """Returns the amount as a float for display, handling Decimal128"""
        if hasattr(self.amount, 'to_decimal'):
            return float(self.amount.to_decimal())
        return float(self.amount)


