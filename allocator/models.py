# allocator/models.py
from django.db import models
from djongo import models as djongo_models
from django.utils import timezone
from django.core.validators import MinValueValidator
from accounts.models import CustomUser
from marketing.models import Job
import logging

logger = logging.getLogger('allocator')


class JobAllocation(models.Model):
    """Track job allocations to writers and process team members"""
    
    # Use Mongo ObjectId as primary key
    id = djongo_models.ObjectIdField(primary_key=True, db_column='_id')
    
    ALLOCATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Link to marketing job
    marketing_job = models.ForeignKey(
        'marketing.Job',
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    
    # Allocation details
    allocated_to = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='job_allocations'
    )
    
    allocated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='allocations_made'
    )
    
    # Allocation type: 'writer' or 'process'
    allocation_type = models.CharField(
        max_length=20,
        choices=[
            ('writer', 'Writer'),
            ('process', 'Process Team'),
        ],
        default='writer'
    )
    
    # Time tracking
    start_date_time = models.DateTimeField()
    end_date_time = models.DateTimeField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=ALLOCATION_STATUS_CHOICES,
        default='active'
    )
    
    # Timestamps
    allocated_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'job_allocations'
        ordering = ['-allocated_at']
        indexes = [
            models.Index(fields=['marketing_job']),
            models.Index(fields=['allocated_to']),
            models.Index(fields=['status']),
            models.Index(fields=['allocation_type']),
        ]
    
    def __str__(self):
        return f"{self.marketing_job.system_id} -> {self.allocated_to.get_full_name()} ({self.allocation_type})"
    
    def clean(self):
        """Validate allocation"""
        from django.core.exceptions import ValidationError
        
        # Validate end time is after start time
        if self.end_date_time <= self.start_date_time:
            raise ValidationError('End date/time must be after start date/time')
        
        # Validate against expected deadline if exists
        if self.marketing_job.expected_deadline:
            if self.end_date_time > self.marketing_job.expected_deadline:
                raise ValidationError(
                    f'End date/time must be before expected deadline: '
                    f'{self.marketing_job.expected_deadline.strftime("%d %b %Y %H:%M")}'
                )
        
        # Validate role matches allocation type
        if self.allocation_type == 'writer' and self.allocated_to.role not in ['writer']:
            logger.warning(
                f"Allocating to non-writer user {self.allocated_to.email} "
                f"for writer allocation in job {self.marketing_job.system_id}"
            )
        
        if self.allocation_type == 'process' and self.allocated_to.role not in ['process']:
            logger.warning(
                f"Allocating to non-process user {self.allocated_to.email} "
                f"for process allocation in job {self.marketing_job.system_id}"
            )
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)


class AllocationActionLog(models.Model):
    """Audit log for allocation actions"""
    
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('reassigned', 'Reassigned'),
    ]
    
    allocation = models.ForeignKey(
        JobAllocation,
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
        db_table = 'allocation_action_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['allocation']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.allocation.marketing_job.system_id} - {self.action} at {self.timestamp}"


# Utility function to log allocation activities
def log_allocation_activity(allocation, event_key, category='job_allocation', performed_by=None, metadata=None):
    """
    Logs allocation-related activities to the main ActivityLog table
    """
    from accounts.models import ActivityLog
    
    if metadata is None:
        metadata = {}
    
    # Add allocation-specific metadata
    metadata.update({
        'allocation_id': str(allocation.id),
        'job_system_id': allocation.marketing_job.system_id,
        'job_id': allocation.marketing_job.job_id,
        'allocated_to': allocation.allocated_to.email,
        'allocation_type': allocation.allocation_type,
    })
    
    ActivityLog.objects.create(
        event_key=event_key,
        category=category,
        subject_user=allocation.allocated_to,
        performed_by=performed_by,
        metadata=metadata,
    )