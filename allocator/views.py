# allocator/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.conf import settings
from django.urls import reverse
from datetime import timedelta
from functools import wraps
import json
import os
import logging

from marketing.models import Job, JobAttachment, JobActionLog
from accounts.models import CustomUser, ActivityLog
from .models import JobAllocation, AllocationActionLog, log_allocation_activity

logger = logging.getLogger('allocator')


def role_required(allowed_roles):
    """Decorator to restrict access based on user role - includes login check"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is logged in
            if not request.user.is_authenticated:
                return redirect('login')
            # Check if user has required role
            if request.user.role not in allowed_roles:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('home_dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@role_required(['allocator'])
def allocator_dashboard(request):
    """Allocator Dashboard - Shows unallocated jobs from last 24 hours"""
    
    user = request.user
    
    # Initialize default values
    stats = {
        'total_jobs': 0,
        'pending_allocation': 0,
        'assigned_jobs': 0,
        'new_jobs': 0,
        'in_progress': 0,
        'completed': 0,
        'hold': 0,
        'cancelled': 0,
        'total_writers': 0,
        'total_process_team': 0,
    }
    recent_jobs_display = []
    recent_activities = []
    
    try:
        # Calculate time threshold once
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        
        # Optimize queries with select_related and only needed fields
        try:
            # Get ALL unallocated jobs count (for statistics)
            all_unallocated_count = Job.objects.filter(status='unallocated').count()
            
            # Get unallocated jobs from LAST 24 HOURS (for dashboard table)
            recent_unallocated_jobs = Job.objects.filter(
                status='unallocated',
                final_form_submitted_at__gte=twenty_four_hours_ago
            ).select_related('created_by', 'project_group').only(
                'id', 'system_id', 'job_id', 'topic', 'word_count', 
                'expected_deadline', 'strict_deadline', 'category', 'status',
                'created_by__first_name', 'created_by__last_name', 'created_by__email',
                'project_group__id', 'project_group__project_group_name',
                'final_form_submitted_at'
            ).order_by('-final_form_submitted_at')
            
            # Get statistics efficiently - Filter in Python for is_active
            all_writers = list(CustomUser.objects.filter(role='writer'))
            active_writers = [w for w in all_writers if getattr(w, 'is_active', True)]
            
            all_process = list(CustomUser.objects.filter(role='process'))
            active_process = [p for p in all_process if getattr(p, 'is_active', True)]
            
            stats = {
                'total_jobs': Job.objects.count(),
                'pending_allocation': all_unallocated_count,
                'assigned_jobs': Job.objects.filter(status__in=['allocated', 'in_progress']).count(),
                'new_jobs': Job.objects.filter(created_at__gte=twenty_four_hours_ago).count(),
                'in_progress': Job.objects.filter(status='in_progress').count(),
                'completed': Job.objects.filter(status='completed').count(),
                'hold': Job.objects.filter(status='hold').count(),
                'cancelled': Job.objects.filter(status='cancelled').count(),
                'total_writers': len(active_writers),
                'total_process_team': len(active_process),
            }
            
        except Exception as db_error:
            logger.error(f"Database error in dashboard stats: {str(db_error)}", exc_info=True)
            # Stats already initialized with zeros above
        
        # Format unallocated jobs from last 24h for display
        try:
            for job in recent_unallocated_jobs:
                try:
                    recent_jobs_display.append({
                        'system_id': job.system_id if job.system_id else '--',
                        'job_id': job.job_id if job.job_id else '--',
                        'topic': job.topic if job.topic else 'No topic',
                        'word_count': job.word_count if job.word_count else '--',
                        'deadline': job.expected_deadline or job.strict_deadline,
                        'created_by': job.created_by.get_full_name() if job.created_by else 'Marketing',
                        'status_display': job.get_status_display() if hasattr(job, 'get_status_display') else 'Unknown',
                        'category': job.category if job.category else '--',
                        'view_url': f'/allocator/job/{job.system_id}/',
                    })
                except Exception as job_error:
                    logger.error(f"Error formatting job {job.id if hasattr(job, 'id') else 'unknown'}: {str(job_error)}")
                    continue
        except Exception as jobs_error:
            logger.error(f"Error processing recent jobs: {str(jobs_error)}", exc_info=True)
        
    except Exception as e:
        logger.error(f"Critical error fetching jobs for dashboard: {str(e)}", exc_info=True)
        messages.warning(request, 'Some job statistics may not be available.')
    
    # Get recent activities - Show all UNALLOCATED jobs from last 24 hours as activities
    try:
        recent_activity_jobs = Job.objects.filter(
            status='unallocated',
            final_form_submitted_at__gte=twenty_four_hours_ago
        ).select_related('created_by').only(
            'id', 'system_id', 'job_id', 'final_form_submitted_at', 'topic', 'category',
            'created_by__first_name', 'created_by__last_name', 'created_by__email'
        ).order_by('-final_form_submitted_at')[:15]
        
        for job in recent_activity_jobs:
            try:
                category_display = dict(Job.CATEGORY_CHOICES).get(job.category, 'N/A') if hasattr(job, 'CATEGORY_CHOICES') else (job.category or 'N/A')
                recent_activities.append({
                    'action_label': f'New job posted - {category_display}',
                    'job_masking_id': job.job_id if job.job_id else job.system_id,
                    'timestamp': job.final_form_submitted_at or job.created_at,
                    'changed_by_name': job.created_by.get_full_name() if job.created_by else 'Marketing',
                    'status_info': 'Waiting for allocation',
                })
            except Exception as job_error:
                logger.error(f"Error processing job for activities: {str(job_error)}")
                continue
                
    except Exception as e:
        logger.error(f"Error fetching recent activities: {str(e)}", exc_info=True)
    
    context = {
        'user': user,
        'stats': stats,
        'recent_jobs': recent_jobs_display,
        'recent_activities': recent_activities,
        'today_date': timezone.now(),
    }
    
    logger.info(f"Allocator dashboard accessed by: {user.email}")
    return render(request, 'allocator/allocator_dashboard.html', context)


@role_required(['allocator'])
def all_projects(request):
    """Show all projects/jobs"""
    
    # Prefetch the creator action so we can reliably show the marketing member
    created_log_prefetch = Prefetch(
        'action_logs',
        queryset=JobActionLog.objects.filter(action='created')
            .select_related('performed_by')
            .order_by('-timestamp'),
        to_attr='created_logs'
    )
    writer_alloc_prefetch = Prefetch(
        'allocations',
        queryset=JobAllocation.objects.filter(
            allocation_type='writer',
            status='active'
        ).select_related('allocated_to').order_by('-allocated_at'),
        to_attr='writer_allocs'
    )
    process_alloc_prefetch = Prefetch(
        'allocations',
        queryset=JobAllocation.objects.filter(
            allocation_type='process',
            status='active'
        ).select_related('allocated_to').order_by('-allocated_at'),
        to_attr='process_allocs'
    )

    jobs_queryset = Job.objects.exclude(status='draft').select_related(
        'created_by',
        'allocated_to',
        'allocated_to_process',
        'project_group'
    ).prefetch_related(
        created_log_prefetch,
        writer_alloc_prefetch,
        process_alloc_prefetch
    ).order_by('-created_at')

    jobs_page = Paginator(jobs_queryset, 25).get_page(request.GET.get('page'))

    for job in jobs_page:
        marketing_user = None
        assignees = []

        # Safely resolve the marketing creator (data may have null or missing relation)
        creator = None
        try:
            creator = job.created_by
        except ObjectDoesNotExist:
            creator = None

        if creator and getattr(creator, 'role', '') == 'marketing':
            marketing_user = creator
        elif getattr(job, 'created_logs', None):
            created_log = job.created_logs[0]
            marketing_user = getattr(created_log, 'performed_by', None)

        if marketing_user:
            job.marketing_member_name = marketing_user.get_full_name() or marketing_user.email
        else:
            job.marketing_member_name = '--'

        # Resolve writer and process assignees (prefer direct fields, fallback to active allocations)
        writer_user = job.allocated_to
        if not writer_user and getattr(job, 'writer_allocs', None):
            writer_user = job.writer_allocs[0].allocated_to

        process_user = getattr(job, 'allocated_to_process', None)
        if not process_user and getattr(job, 'process_allocs', None):
            process_user = job.process_allocs[0].allocated_to

        # Build assignee display based on status rules:
        # - Status 'process' or 'review' -> show process member
        # - Status 'allocated'/'in_progress' -> show writer
        status_lower = (job.status or '').lower()
        if status_lower in ['process', 'review']:
            if process_user:
                assignees.append(process_user.get_full_name() or process_user.email)
        elif status_lower in ['allocated', 'in_progress']:
            if writer_user:
                assignees.append(writer_user.get_full_name() or writer_user.email)

        job.assignees_display = ', '.join(assignees) if assignees else '--'
        # Show writer/process in dedicated columns (no cross-fallbacks)
        job.writer_display = (
            writer_user.get_full_name() if writer_user and writer_user.get_full_name()
            else (writer_user.email if writer_user else '--')
        )
        job.process_display = (
            process_user.get_full_name() if process_user and process_user.get_full_name()
            else (process_user.email if process_user else '--')
        )

        job.view_url = reverse('allocator_all_project_detail', args=[job.system_id])
    
    context = {
        'jobs': jobs_page,
        'total_jobs': jobs_queryset.count(),
        'status_options': [('', 'All Status')] + list(Job.STATUS_CHOICES),
        'status_filter': request.GET.get('status', '').strip(),
        'search': request.GET.get('search', '').strip(),
        'start_date': request.GET.get('start_date', '').strip(),
        'end_date': request.GET.get('end_date', '').strip(),
    }
    
    return render(request, 'allocator/all_projects.html', context)


@role_required(['allocator'])
def all_projects_detail(request, system_id):
    """Show detailed project information (marketing posted form)"""
    
    marketing_job = get_object_or_404(Job, system_id=system_id)
    
    # Get attachments
    attachments = marketing_job.attachments.all()
    
    context = {
        'job': marketing_job,
        'attachments': attachments,
    }
    
    return render(request, 'allocator/all_project_detail.html', context)


@role_required(['allocator'])
def pending_allocation(request):
    """Show ALL jobs pending allocation (no time filter)"""
    
    # Get ALL unallocated jobs (no time filter)
    pending_jobs = Job.objects.filter(
        status='unallocated'
    ).select_related('created_by', 'project_group').order_by('-created_at')
    
    # Calculate priority and format for display
    pending_jobs_display = []
    now = timezone.now()
    
    for job in pending_jobs:
        # Calculate priority based on deadline
        deadline = job.strict_deadline or job.expected_deadline
        priority = 'low'
        priority_label = 'Low'
        
        if deadline:
            time_diff = deadline - now
            if time_diff.total_seconds() < 0:
                priority = 'urgent'
                priority_label = 'Urgent (Overdue)'
            elif time_diff.days < 1:
                priority = 'urgent'
                priority_label = 'Urgent (< 24h)'
            elif time_diff.days < 3:
                priority = 'high'
                priority_label = 'High (< 3 days)'
            elif time_diff.days < 7:
                priority = 'medium'
                priority_label = 'Medium'
        
        pending_jobs_display.append({
            'id': str(job.id),
            'system_id': job.system_id,  # ✅ FIXED: Use system_id for URL
            'masking_id': job.job_id,    # Display job_id to user
            'topic': job.topic or 'No topic',
            'word_count': job.word_count,
            'deadline': deadline,
            'priority': priority,
            'priority_label': priority_label,
            'job_category': job.category or 'General',
            'created_by': job.created_by.get_full_name() if job.created_by else 'Marketing',
        })
    
    # Calculate statistics
    pending_stats = {
        'total': len(pending_jobs_display),
        'categories': len(set(j['job_category'] for j in pending_jobs_display)) if pending_jobs_display else 0,
        'high_priority': sum(1 for j in pending_jobs_display if j['priority'] in ['urgent', 'high']),
    }
    
    context = {
        'pending_jobs': pending_jobs_display,
        'pending_stats': pending_stats,
    }
    
    return render(request, 'allocator/pending_allocation.html', context)


@role_required(['allocator'])
def allocated_jobs(request):
    """Show all jobs that have been allocated to writers"""
    
    # Get all allocated jobs with their allocation details
    allocated_jobs_list = Job.objects.filter(
        status='allocated'
    ).select_related('created_by', 'allocated_to', 'project_group').order_by('-updated_at')
    
    # Format jobs with allocation details
    allocated_jobs_display = []
    
    for job in allocated_jobs_list:
        # Get the active allocation for this job
        allocation = JobAllocation.objects.filter(
            marketing_job=job,
            status='active'
        ).select_related('allocated_to').first()
        
        # Get deadline
        deadline = job.strict_deadline or job.expected_deadline
        
        allocated_jobs_display.append({
            'id': str(job.id),
            'system_id': job.system_id,
            'masking_id': job.job_id,
            'topic': job.topic or 'No topic',
            'word_count': job.word_count,
            'deadline': deadline,
            'job_category': job.category or 'General',
            'created_by': job.created_by.get_full_name() if job.created_by else 'Marketing',
            'status': job.status,
            'status_display': job.get_status_display(),
            'allocated_to': allocation.allocated_to.get_full_name() if allocation else 'N/A',
            'allocated_to_email': allocation.allocated_to.email if allocation else 'N/A',
            'start_datetime': allocation.start_date_time if allocation else None,
            'end_datetime': allocation.end_date_time if allocation else None,
            'allocation_notes': allocation.notes if allocation else '',
        })
    
    # Calculate statistics
    allocated_stats = {
        'total': len(allocated_jobs_display),
        'in_progress': len([j for j in allocated_jobs_display if j['status'] == 'in_progress']),
        'categories': len(set(j['job_category'] for j in allocated_jobs_display)) if allocated_jobs_display else 0,
    }
    
    context = {
        'allocated_jobs': allocated_jobs_display,
        'allocated_stats': allocated_stats,
    }
    
    return render(request, 'allocator/allocated_jobs.html', context)


@role_required(['allocator'])
def allocate_job(request, system_id):
    """Allocate job to writer or process team - GET shows form, POST processes allocation"""
    
    # Get the job
    job = get_object_or_404(Job, system_id=system_id)
    
    if request.method == 'POST':
        return _process_job_allocation(request, job)
    
    # GET request - show allocation form
    
    # Determine allocation type based on job status
    if job.status == 'Review':
        allocation_type = 'process'
        member_role = 'process'
    else:
        allocation_type = 'writer'
        member_role = 'writer'
    
    # Get available team members - simplified query for Djongo compatibility
    try:
        # Simple query without complex filtering
        all_members = CustomUser.objects.filter(role=member_role)
        
        # Filter in Python instead of in query
        available_members = [m for m in all_members if getattr(m, 'is_active', True)]
        
        # Sort in Python
        available_members.sort(key=lambda x: (x.first_name or '', x.last_name or ''))
        
    except Exception as e:
        logger.error(f"Error fetching {member_role}s: {str(e)}", exc_info=True)
        available_members = []
    
    # Set filter note based on allocation type and category
    if allocation_type == 'process':
        team_filter_note = "Showing all active process team members"
    elif job.category and job.category.upper() == 'IT':
        team_filter_note = "Showing all active writers. (IT-specific filtering to be implemented)"
    else:
        team_filter_note = "Showing all active writers"
    
    # Format members for dropdown
    members_list = []
    for member in available_members:
        members_list.append({
            'id': str(member.id),  # Convert to string for safety
            'name': member.get_full_name() or member.email,
            'email': member.email,
            'employee_id': getattr(member, 'employee_id', '') or '',
        })
    
    context = {
        'job': job,
        'allocation_type': allocation_type,
        'writers': members_list,
        'team_filter_note': team_filter_note,
        'expected_deadline': job.expected_deadline,
        'strict_deadline': job.strict_deadline,
        'job_category': job.category,
    }
    
    return render(request, 'allocator/allocate_job.html', context)


def _process_job_allocation(request, job):
    """Process job allocation form submission - handles both writer and process"""
    
    logger.info("="*50)
    logger.info("ALLOCATION FORM SUBMISSION DEBUG")
    logger.info("="*50)
    logger.info(f"Job System ID: {job.system_id}")
    logger.info(f"Job ID: {job.job_id}")
    logger.info(f"Job Status: {job.status}")
    logger.info(f"POST data: {dict(request.POST)}")
    
    try:
        member_id = request.POST.get('writer_id')  # Key is 'writer_id' but could be process member
        start_datetime_str = request.POST.get('start_datetime')
        end_datetime_str = request.POST.get('end_datetime')
        notes = request.POST.get('notes', '').strip()
        
        # Determine allocation type based on job status
        if job.status == 'Review':
            allocation_type = 'process'
            member_role = 'process'
            success_redirect = 'pending_allocation_process'
        else:
            allocation_type = 'writer'
            member_role = 'writer'
            success_redirect = 'pending_allocation'
        
        logger.info(f"Allocation type: {allocation_type}")
        
        # Validation
        errors = []
        
        if not member_id:
            errors.append(f'Please select a {allocation_type}.')
            logger.error(f"Validation failed: No {allocation_type} selected")
        
        if not start_datetime_str:
            errors.append('Start date/time is required.')
            logger.error("Validation failed: No start_datetime")
        
        if not end_datetime_str:
            errors.append('End date/time is required.')
            logger.error("Validation failed: No end_datetime")
        
        if errors:
            for error in errors:
                messages.error(request, error)
            logger.error(f"Validation errors: {errors}")
            return redirect('allocate_job', system_id=job.system_id)
        
        # Get team member
        logger.info(f"Attempting to fetch {allocation_type} with ID: {member_id}")
        try:
            member = CustomUser.objects.get(id=member_id, role=member_role)
            logger.info(f"{allocation_type.title()} found: {member.get_full_name()} ({member.email})")
        except CustomUser.DoesNotExist:
            logger.error(f"{allocation_type.title()} not found with ID: {member_id}")
            messages.error(request, f'Selected {allocation_type} not found.')
            return redirect('allocate_job', system_id=job.system_id)
        
        # Parse datetimes
        logger.info(f"Parsing datetimes...")
        try:
            start_dt = timezone.datetime.fromisoformat(start_datetime_str)
            end_dt = timezone.datetime.fromisoformat(end_datetime_str)
            
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt)
            
            logger.info(f"Start datetime parsed: {start_dt}")
            logger.info(f"End datetime parsed: {end_dt}")
            
        except ValueError as e:
            logger.error(f"Date parsing error: {str(e)}", exc_info=True)
            messages.error(request, 'Invalid date/time format.')
            return redirect('allocate_job', system_id=job.system_id)
        
        # Validate times
        now = timezone.now()
        
        if start_dt < now:
            logger.error(f"Start time {start_dt} is in the past")
            messages.error(request, 'Start date/time cannot be in the past.')
            return redirect('allocate_job', system_id=job.system_id)
        
        if end_dt <= start_dt:
            logger.error(f"End time {end_dt} is not after start time {start_dt}")
            messages.error(request, 'End date/time must be after start date/time.')
            return redirect('allocate_job', system_id=job.system_id)
        
        if job.expected_deadline and end_dt > job.expected_deadline:
            logger.error(f"End time exceeds expected deadline")
            messages.error(
                request,
                f'End date/time must be before expected deadline: '
                f'{job.expected_deadline.strftime("%d %b %Y %H:%M")}'
            )
            return redirect('allocate_job', system_id=job.system_id)
        
        logger.info("All validations passed. Creating allocation...")
        
        # Create allocation
        with transaction.atomic():
            try:
                allocation = JobAllocation.objects.create(
                    marketing_job=job,
                    allocated_to=member,
                    allocated_by=request.user,
                    allocation_type=allocation_type,
                    start_date_time=start_dt,
                    end_date_time=end_dt,
                    status='active',
                    notes=notes,
                    metadata={
                        'allocated_from': f'pending_allocation_{allocation_type}',
                        'job_category': job.category,
                    }
                )
                logger.info(f"Allocation created successfully: ID={allocation.id}")
                
                # Update job status and allocation details based on allocation type
                if allocation_type == 'process':
                    # Process team allocation
                    job.status = 'process'
                    job.allocated_to_process = member
                    job.allocated_to_process_at = now
                    update_fields = ['status', 'allocated_to_process', 'allocated_to_process_at', 'updated_at']
                    logger.info(f"Job updated: status='process', allocated_to_process={member.email}, allocated_to_process_at={now}")
                else:
                    # Writer allocation
                    job.status = 'allocated'
                    job.allocated_to = member
                    update_fields = ['status', 'allocated_to', 'updated_at']
                    logger.info(f"Job updated: status='allocated', allocated_to={member.email}")
                
                job.save(update_fields=update_fields)
                logger.info(f"Job status updated to: {job.status}")
                
                # Log action
                AllocationActionLog.objects.create(
                    allocation=allocation,
                    action='created',
                    performed_by=request.user,
                    details={
                        'member_id': str(member.id),
                        'member_name': member.get_full_name(),
                        'allocation_type': allocation_type,
                        'start_datetime': start_dt.isoformat(),
                        'end_datetime': end_dt.isoformat(),
                    }
                )
                
                # Log job action for process allocation
                if allocation_type == 'process':
                    JobActionLog.objects.create(
                        job=job,
                        action='allocated',
                        performed_by=request.user,
                        performed_by_type='user',
                        details={
                            'allocation_type': 'process',
                            'process_member_id': str(member.id),
                            'process_member_name': member.get_full_name(),
                            'process_member_email': member.email,
                            'start_datetime': start_dt.isoformat(),
                            'end_datetime': end_dt.isoformat(),
                            'old_status': 'Review',
                            'new_status': 'process',
                        }
                    )
                
                # System activity log
                try:
                    log_allocation_activity(
                        allocation,
                        f'job.allocated_to_{allocation_type}',
                        category='job_allocation',
                        performed_by=request.user,
                        metadata={
                            'member_name': member.get_full_name(),
                            'member_email': member.email,
                            'allocation_type': allocation_type,
                        }
                    )
                except Exception as log_error:
                    logger.error(f"Error logging activity: {str(log_error)}", exc_info=True)
                
                logger.info(f"✅ SUCCESS: Job {job.system_id} allocated to {allocation_type} {member.email}")
                
                messages.success(
                    request,
                    f'Job "{job.job_id}" successfully allocated to {member.get_full_name()} ({allocation_type})!'
                )
                
                return redirect(success_redirect)
                
            except Exception as create_error:
                logger.error(f"❌ ERROR CREATING ALLOCATION: {str(create_error)}", exc_info=True)
                messages.error(request, f'Error creating allocation: {str(create_error)}')
                return redirect('allocate_job', system_id=job.system_id)
        
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR: {str(e)}", exc_info=True)
        messages.error(request, f'Error allocating job: {str(e)}')
        return redirect('allocate_job', system_id=job.system_id)












@role_required(['allocator'])
def assigned_jobs(request):
    """Show jobs that have been assigned (status=allocated)"""
    
    # Get allocated jobs
    assigned_jobs_query = Job.objects.filter(
        status='allocated'
    ).select_related('created_by', 'allocated_to').order_by('-updated_at')
    
    # Format for display
    jobs_display = []
    for job in assigned_jobs_query:
        # Get allocation details
        allocation = JobAllocation.objects.filter(
            marketing_job=job,
            status='active'
        ).select_related('allocated_to').first()
        
        jobs_display.append({
            'id': job.id,
            'system_id': job.system_id,
            'job_id': job.job_id,
            'masking_id': job.job_id,
            'topic': job.topic,
            'word_count': job.word_count,
            'deadline': job.expected_deadline or job.strict_deadline,
            'status': job.get_status_display(),
            'category': job.category,
            'allocated_to': allocation.allocated_to.get_full_name() if allocation else job.allocated_to.get_full_name() if job.allocated_to else '--',
            'allocated_to_email': allocation.allocated_to.email if allocation else '--',
            'allocation_type': allocation.allocation_type if allocation else '--',
            'start_date_time': allocation.start_date_time if allocation else None,
            'end_date_time': allocation.end_date_time if allocation else None,
            'allocation_notes': allocation.notes if allocation else '',
            'allocated_by': allocation.allocated_by.get_full_name() if allocation and allocation.allocated_by else '--',
            'allocated_at': allocation.allocated_at if allocation else None,
        })
    
    context = {
        'assigned_jobs': jobs_display,
        'total_assigned': len(jobs_display),
    }
    
    return render(request, 'allocator/assigned_jobs.html', context)


@role_required(['allocator'])
def in_progress_jobs(request):
    """Show jobs that are in progress"""
    
    in_progress_jobs = Job.objects.filter(
        status='in_progress'
    ).select_related('created_by', 'allocated_to').order_by('-updated_at')
    
    jobs_display = []
    for job in in_progress_jobs:
        allocation = JobAllocation.objects.filter(
            marketing_job=job,
            status='active'
        ).select_related('allocated_to').first()
        
        jobs_display.append({

            'id': job.id,
            'system_id': job.system_id,
            'job_id': job.job_id,
            'masking_id': job.job_id,
            'topic': job.topic,
            'word_count': job.word_count,
            'deadline': job.expected_deadline or job.strict_deadline,
            'status': job.get_status_display(),
            'category': job.category,
            'allocated_to': allocation.allocated_to.get_full_name() if allocation else job.allocated_to.get_full_name() if job.allocated_to else '--',
            'allocated_to_email': allocation.allocated_to.email if allocation else '--',
            'allocation_type': allocation.allocation_type if allocation else '--',
            'start_date_time': allocation.start_date_time if allocation else None,
            'end_date_time': allocation.end_date_time if allocation else None,
            'allocation_notes': allocation.notes if allocation else '',
            'allocated_by': allocation.allocated_by.get_full_name() if allocation and allocation.allocated_by else '--',
            'allocated_at': allocation.allocated_at if allocation else None,
        })
    
    # Calculate stats
    total_jobs = len(jobs_display)
    
    # Simple count based on the display list
    from django.utils import timezone
    now = timezone.now()
    today = now.date()
    
    due_today_count = 0
    overdue_count = 0
    
    for item in jobs_display:
        if item['deadline']:
            # Check if deadline is datetime or date
            deadline_val = item['deadline']
            if hasattr(deadline_val, 'date'):
                deadline_date = deadline_val.date()
            else:
                deadline_date = deadline_val # assume date
                
            if deadline_date == today:
                due_today_count += 1
            elif deadline_val < now: # precise comparison for overdue
                overdue_count += 1

    context = {
        'jobs': jobs_display,
        'total_jobs': total_jobs,
        'due_today_count': due_today_count,
        'overdue_count': overdue_count,
        'today_date': now, # Added for template comparisons
    }
    
    return render(request, 'allocator/in_progress_jobs.html', context)


@role_required(['allocator'])
def cancel_jobs(request):
    """Show cancelled jobs"""
    
    cancelled_jobs = Job.objects.filter(
        status='cancelled'
    ).select_related('created_by', 'allocated_to').order_by('-updated_at')
    
    context = {
        'cancelled_jobs': cancelled_jobs,
        'total_cancelled': cancelled_jobs.count(),
    }
    
    return render(request, 'allocator/cancel_jobs.html', context)


@role_required(['allocator'])
def hold_jobs_allocator(request):
    """Show jobs on hold"""
    
    hold_jobs = Job.objects.filter(
        status='hold'
    ).select_related('created_by', 'allocated_to').order_by('-updated_at')
    
    context = {
        'hold_jobs': hold_jobs,
        'total_hold': hold_jobs.count(),
    }
    
    return render(request, 'allocator/hold_jobs.html', context)


@role_required(['allocator'])
def process_jobs(request):
    """Show jobs in process team stage - only 'process' and 'in_review' statuses"""
    
    # Filter jobs with status 'process' or 'in_review' and get their allocations
    process_jobs_query = Job.objects.filter(
        status__in=['process', 'in_review']
    ).select_related('created_by', 'allocated_to', 'allocated_to_process').order_by('-updated_at')
    
    # Map job status choices
    job_status_map = {
        'process': 'Process',
        'in_review': 'In Review',
    }
    
    tasks = []
    for job in process_jobs_query:
        # Get process allocation for allocation details
        allocation = JobAllocation.objects.filter(
            marketing_job=job,
            allocation_type='process',
            status='active'
        ).select_related('allocated_to').first()
        
        tasks.append({
            'id': str(job.id),
            'job': {
                'id': str(job.id),
                'system_id': job.system_id,
                'job_id': job.job_id,
                'topic': job.topic or 'Not specified',
                'word_count': job.word_count or 0,
                'category': job.category or 'NON-IT',
                'status': job.status,
                'expected_deadline': job.expected_deadline,
            },
            'allocated_to': allocation.allocated_to if allocation else job.allocated_to_process,
            'start_date_time': allocation.start_date_time if allocation else job.allocated_to_process_at,
            'end_date_time': allocation.end_date_time if allocation else job.strict_deadline,
            'status': job.status,  # Use job status, not allocation status
            'status_display': job_status_map.get(job.status, 'Unknown'),
            'temperature_score': None,  # To be filled by process team
            'temperature_matched': False,
            'writer_final_link': '',
            'summary_link': '',
            'process_final_link': '',
        })
    
    context = {
        'tasks': tasks,
        'total_process': len(tasks),
        'process_jobs': tasks,  # Keep for backward compatibility
    }
    
    return render(request, 'allocator/process_jobs.html', context)


@role_required(['allocator'])
def completed_jobs_allocator(request):
    """Show completed jobs"""
    
    
    # Self-heal: Ensure allocations for completed jobs are marked completed
    # This catches historical jobs where allocations weren't closed
    # NOTE: Djongo doesn't support joins in update(), so we must fetch IDs first
    try:
        completed_job_ids = list(Job.objects.filter(status='completed').values_list('id', flat=True))
        if completed_job_ids:
            JobAllocation.objects.filter(
                marketing_job_id__in=completed_job_ids,
                status='active'
            ).update(status='completed', completed_at=timezone.now())
    except Exception as e:
        logger.error(f"Error in self-healing allocations: {str(e)}")

    completed_jobs = Job.objects.filter(
        status='completed'
    ).select_related('created_by', 'allocated_to').prefetch_related('allocations').order_by('-updated_at')
    
    context = {
        'jobs': completed_jobs,
        'total_completed': completed_jobs.count(),
    }
    
    return render(request, 'allocator/completed_jobs.html', context)


@role_required(['allocator'])
def all_writers(request):
    """Show all active writers with engagement statistics"""
    
    try:
        # Fetch all active writers (include all, not just active=True since some might not have that field set)
        writers = CustomUser.objects.filter(role='writer').order_by('first_name', 'last_name')
        
        writer_data = []
        writer_stats = {
            'total_it': 0,
            'total_nonit': 0,
            'total_finance': 0,
            'available': 0,
            'engaged': 0,
        }
        
        for writer in writers:
            # Count engaged jobs (active allocations)
            engaged_jobs = JobAllocation.objects.filter(
                allocated_to=writer,
                allocation_type='writer',
                status='active'
            ).count()
            
            # Get writer statistics if available
            writer_stats_obj = getattr(writer, 'writer_stats', None)
            total_words = writer_stats_obj.total_words_written if writer_stats_obj else 0
            
            # Default capacity values
            max_jobs = 10
            max_words = 50000
            
            available_slots = max(0, max_jobs - engaged_jobs)
            available_words = max(0, max_words - total_words)
            
            # Check availability status - default to Available
            is_sunday_off = False
            is_on_holiday = False
            is_overloaded = (engaged_jobs >= max_jobs) or (total_words >= max_words)
            
            # Determine category from department field in database
            category = writer.department if writer.department else 'Non-IT'
            
            # Determine availability status
            if is_on_holiday:
                availability_status = 'Not Available'
            elif is_overloaded:
                availability_status = 'Not Available'
            else:
                availability_status = 'Available'
            
            # Update statistics
            category_upper = category.upper() if category else 'NON-IT'
            if 'NON-IT' in category_upper or 'NON IT' in category_upper:
                writer_stats['total_nonit'] += 1
            elif 'IT' in category_upper:
                writer_stats['total_it'] += 1
            elif 'FINANCE' in category_upper:
                writer_stats['total_finance'] += 1
            else:
                writer_stats['total_nonit'] += 1
            
            if availability_status == 'Available':
                writer_stats['available'] += 1
            
            if engaged_jobs > 0:
                writer_stats['engaged'] += 1
            
            writer_data.append({
                'user': writer,
                'profile': None,
                'engagement': {
                    'engaged_jobs': engaged_jobs,
                    'total_words': total_words,
                    'available_slots': available_slots,
                    'available_words': available_words,
                },
                'assigned_category': category,
                'availability_status': availability_status,
                'is_sunday_off': is_sunday_off,
                'is_on_holiday': is_on_holiday,
                'is_overloaded': is_overloaded,
            })
        
    except Exception as e:
        logger.error(f"Error fetching writers: {str(e)}", exc_info=True)
        writer_data = []
        writer_stats = {
            'total_it': 0,
            'total_nonit': 0,
            'total_finance': 0,
            'available': 0,
            'engaged': 0,
        }
    
    context = {
        'writer_data': writer_data,
        'writer_stats': writer_stats,
    }
    
    return render(request, 'allocator/all_writers.html', context)



@role_required(['allocator'])
def all_process_team(request):
    """Show all active process team members with engagement statistics"""
    
    try:
        # Fetch all process team members
        process_members = CustomUser.objects.filter(role='process').order_by('first_name', 'last_name')
        
        process_data = []
        
        for member in process_members:
            # Count active jobs
            current_jobs = JobAllocation.objects.filter(
                allocated_to=member,
                allocation_type='process',
                status='active'
            ).count()
            
            # Get process statistics if available
            process_stats_obj = getattr(member, 'process_stats', None)
            total_jobs_completed = process_stats_obj.total_jobs_completed if process_stats_obj else 0
            
            # Default capacity
            max_jobs = 10
            
            # Calculate load percentage
            load_percent = min(100, (current_jobs / max_jobs * 100)) if max_jobs > 0 else 0
            
            # Load color based on percentage
            if load_percent < 50:
                load_color_start = '#4CAF50'
                load_color_end = '#4CAF50'
            elif load_percent < 80:
                load_color_start = '#FF9800'
                load_color_end = '#FF9800'
            else:
                load_color_start = '#F44336'
                load_color_end = '#F44336'
            
            # Check availability
            is_sunday_off = False
            is_on_holiday = False
            is_overloaded = current_jobs >= max_jobs
            
            # Determine availability
            if is_on_holiday:
                availability = 'Not Available'
            elif is_overloaded:
                availability = 'Not Available'
            else:
                availability = 'Available'
            
            process_data.append({
                'user': member,
                'profile': {
                    'max_jobs': max_jobs,
                    'current_jobs': current_jobs,
                    'total_jobs_completed': total_jobs_completed,
                },
                'current_load': current_jobs,
                'load_percent': load_percent,
                'load_color_start': load_color_start,
                'load_color_end': load_color_end,
                'availability': availability,
                'is_sunday_off': is_sunday_off,
                'is_on_holiday': is_on_holiday,
                'is_overloaded': is_overloaded,
            })
        
    except Exception as e:
        logger.error(f"Error fetching process team: {str(e)}", exc_info=True)
        process_data = []
    
    context = {
        'process_data': process_data,
    }
    
    return render(request, 'allocator/all_process_team.html', context)

@role_required(['allocator'])
def switch_writer(request, allocation_id):
    """Switch writer for a job allocation"""
    
    allocation = get_object_or_404(JobAllocation, id=allocation_id)
    
    if request.method == 'POST':
        new_writer_id = request.POST.get('new_writer_id')
        
        if not new_writer_id:
            messages.error(request, 'Please select a new writer.')
            return redirect('view_job_details', system_id=allocation.marketing_job.system_id)
        
        new_writer = get_object_or_404(CustomUser, id=new_writer_id, role='writer')
        
        with transaction.atomic():
            old_writer = allocation.allocated_to
            
            # Update allocation
            allocation.allocated_to = new_writer
            allocation.save(update_fields=['allocated_to', 'updated_at'])
            
            # Update job
            job = allocation.marketing_job
            job.allocated_to = new_writer
            job.save(update_fields=['allocated_to', 'updated_at'])
            
            # Log action
            AllocationActionLog.objects.create(
                allocation=allocation,
                action='reassigned',
                performed_by=request.user,
                details={
                    'old_writer_id': str(old_writer.id),
                    'old_writer_name': old_writer.get_full_name(),
                    'new_writer_id': str(new_writer.id),
                    'new_writer_name': new_writer.get_full_name(),
                }
            )
            
            messages.success(
                request,
                f'Writer changed from {old_writer.get_full_name()} to {new_writer.get_full_name()}'
            )
        
        return redirect('allocator_view_job_details', system_id=allocation.marketing_job.system_id)
    
    # GET - show switch form
    try:
        all_writers = list(CustomUser.objects.filter(role='writer'))
        writers = [
            w for w in all_writers 
            if getattr(w, 'is_active', True) and str(w.id) != str(allocation.allocated_to.id)
        ]
        writers.sort(key=lambda x: (x.first_name or '', x.last_name or ''))
    except Exception as e:
        logger.error(f"Error fetching writers for switch: {str(e)}", exc_info=True)
        writers = []
    
    context = {
        'allocation': allocation,
        'writers': writers,
    }
    
    return render(request, 'allocator/switch_writer.html', context)



@role_required(['allocator'])
def view_job_details(request, system_id):
    """View detailed job information with allocation details"""
    
    # Get marketing job by system_id
    marketing_job = get_object_or_404(Job, system_id=system_id)
    
    # Create job object for template compatibility using a proper class
    class JobProxy:
        def __init__(self, marketing_job):
            self.masking_id = marketing_job.system_id
            self.status = marketing_job.status
            self.created_by = marketing_job.created_by
            self._marketing_job = marketing_job
        
        def get_status_display(self):
            return self._marketing_job.get_status_display()
    
    job = JobProxy(marketing_job)
    
    # Gather primary info
    primary_info = []
    
    if marketing_job.topic:
        primary_info.append({'label': 'Topic', 'value': marketing_job.topic})
    
    if marketing_job.word_count:
        primary_info.append({'label': 'Word Count', 'value': marketing_job.word_count})
    
    if marketing_job.category:
        primary_info.append({'label': 'Category', 'value': marketing_job.category})
    
    if marketing_job.level:
        primary_info.append({'label': 'Level', 'value': marketing_job.level.title()})
    
    if marketing_job.writing_style:
        primary_info.append({'label': 'Writing Style', 'value': marketing_job.writing_style.replace('_', ' ').title()})
    
    if marketing_job.referencing_style:
        primary_info.append({'label': 'Referencing Style', 'value': marketing_job.referencing_style.upper()})
    
    if marketing_job.expected_deadline:
        primary_info.append({
            'label': 'Expected Deadline',
            'value': marketing_job.expected_deadline.strftime("%d %b %Y %H:%M")
        })
    
    if marketing_job.strict_deadline:
        primary_info.append({
            'label': 'Strict Deadline',
            'value': marketing_job.strict_deadline.strftime("%d %b %Y %H:%M")
        })
    
    if marketing_job.customer_name:
        primary_info.append({'label': 'Customer', 'value': marketing_job.customer_name})
    
    if marketing_job.project_group:
        primary_info.append({'label': 'Project Group', 'value': marketing_job.project_group.project_group_name})
    
    # Get instruction
    instructions_text = marketing_job.instruction or 'No instruction provided.'
    
    # Get attachments
    attachments_display = []
    
    # Database attachments
    db_attachments = marketing_job.attachments.all()
    for att in db_attachments:
        url = None
        exists = False
        try:
            if att.file:
                try:
                    url = att.file.url
                    exists = True
                except:
                    if att.file.name:
                        exists = True
                        try:
                            url = att.file.url
                        except:
                            pass
        except:
            pass
        
        attachments_display.append({
            'name': att.original_filename,
            'source': 'Database',
            'uploaded_at': att.uploaded_at,
            'url': url,
            'exists': exists,
        })
    
    # Check media folder for additional files
    media_path = os.path.join(settings.MEDIA_ROOT, 'job_attachments', marketing_job.system_id)
    db_attachment_names = {att.original_filename for att in db_attachments}
    
    if os.path.exists(media_path):
        try:
            for filename in os.listdir(media_path):
                if filename in db_attachment_names:
                    continue
                
                file_path = os.path.join(media_path, filename)
                if os.path.isfile(file_path):
                    try:
                        file_url = f"{settings.MEDIA_URL}job_attachments/{marketing_job.system_id}/{filename}"
                        mtime = os.path.getmtime(file_path)
                        uploaded_at = timezone.datetime.fromtimestamp(mtime)
                        
                        attachments_display.append({
                            'name': filename,
                            'source': 'Disk',
                            'uploaded_at': uploaded_at,
                            'url': file_url,
                            'exists': True,
                        })
                    except Exception as e:
                        logger.error(f"Error processing disk file {filename}: {e}")
        except Exception as e:
            logger.error(f"Error scanning media folder for {marketing_job.system_id}: {e}")
    
    # Get allocation details if job is allocated
    show_task_allocations = marketing_job.status in ['allocated', 'in_progress', 'Review', 'completed', 'process', 'in_review']
    task_panels = []
    
    if show_task_allocations:
        # Get writer allocation
        writer_allocation = JobAllocation.objects.filter(
            marketing_job=marketing_job,
            allocation_type='writer'
        ).select_related('allocated_to').first()
        
        if writer_allocation:
            task_panels.append({
                'label': 'Writer Assignment',
                'allocations': [writer_allocation]
            })
        
        # Get process allocation if exists
        process_allocation = JobAllocation.objects.filter(
            marketing_job=marketing_job,
            allocation_type='process'
        ).select_related('allocated_to').first()
        
        if process_allocation:
            task_panels.append({
                'label': 'Process Team Assignment',
                'allocations': [process_allocation]
            })
    
    # Get writer submission files if job status is 'process' or 'in_review'
    writer_submissions = []
    if marketing_job.status in ['process', 'in_review']:
        from marketing.models import WriterSubmission
        submissions = WriterSubmission.objects.filter(
            job=marketing_job
        ).select_related('submitted_by').prefetch_related('files').order_by('-submitted_at')
        
        for submission in submissions:
            submission_data = {
                'id': str(submission.id),
                'type': submission.submission_type,
                'type_display': 'Structure' if submission.submission_type == 'structure' else 'Final Copy',
                'submitted_by': submission.submitted_by.get_full_name(),
                'submitted_at': submission.submitted_at,
                'status': submission.status,
                'files': []
            }
            
            for file in submission.files.all():
                submission_data['files'].append({
                    'id': str(file.id),
                    'name': file.original_filename,
                    'size': file.file_size,
                    'uploaded_at': file.uploaded_at,
                    'url': file.file.url if file.file else None,
                })
            
            writer_submissions.append(submission_data)
    
    context = {
        'job': job,
        'marketing_job': marketing_job,
        'primary_info': primary_info,
        'instructions_text': instructions_text,
        'attachments': attachments_display,
        'show_task_allocations': show_task_allocations,
        'task_panels': task_panels,
        'writer_submissions': writer_submissions,
    }
    
    return render(request, 'allocator/view_job_details.html', context)

@role_required(['allocator'])
def approve_comment(request, job_id):
    """Approve a comment or action on a job"""
    # Placeholder for comment approval functionality
    messages.info(request, 'Comment approval feature coming soon.')
    return redirect('allocator_view_job_details', system_id=job_id)


@role_required(['allocator'])
@require_http_methods(["GET"])
def get_job_status(request, masking_id):
    """AJAX endpoint to get current job status by job_id (masking_id)"""
    try:
        job = Job.objects.get(job_id=masking_id)
        return JsonResponse({
            'success': True,
            'marketing_status': job.get_status_display(),
            'status_code': job.status,
        })
    except Job.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Job not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error fetching job status: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@role_required(['allocator'])
def download_attachment(request, attachment_id):
    """Download job attachment"""
    
    attachment = get_object_or_404(JobAttachment, id=attachment_id)
    
    try:
        if attachment.file:
            response = FileResponse(attachment.file.open('rb'))
            response['Content-Disposition'] = f'attachment; filename="{attachment.original_filename}"'
            return response
    except Exception as e:
        logger.error(f"Error downloading attachment {attachment_id}: {str(e)}")
        raise Http404("File not found")



@role_required(['allocator'])
def pending_allocation_process(request):
    """Show jobs pending PROCESS allocation (status='Review')"""
    
    # Get jobs with status 'Review' - these need process team allocation
    review_jobs = Job.objects.filter(
        status='Review'
    ).select_related('created_by', 'project_group', 'allocated_to').order_by('-updated_at')
    
    # Calculate priority and format for display
    pending_jobs_display = []
    now = timezone.now()
    
    for job in review_jobs:
        # Calculate priority based on deadline
        deadline = job.strict_deadline or job.expected_deadline
        priority = 'low'
        priority_label = 'Low'
        
        if deadline:
            time_diff = deadline - now
            if time_diff.total_seconds() < 0:
                priority = 'urgent'
                priority_label = 'Urgent (Overdue)'
            elif time_diff.days < 1:
                priority = 'urgent'
                priority_label = 'Urgent (< 24h)'
            elif time_diff.days < 3:
                priority = 'high'
                priority_label = 'High (< 3 days)'
            elif time_diff.days < 7:
                priority = 'medium'
                priority_label = 'Medium'
        
        # Get writer info if allocated
        writer_name = 'N/A'
        if job.allocated_to:
            writer_name = job.allocated_to.get_full_name()
        
        pending_jobs_display.append({
            'id': str(job.id),
            'system_id': job.system_id,
            'masking_id': job.job_id,
            'topic': job.topic or 'No topic',
            'word_count': job.word_count,
            'deadline': deadline,
            'priority': priority,
            'priority_label': priority_label,
            'job_category': job.category or 'General',
            'created_by': job.created_by.get_full_name() if job.created_by else 'Marketing',
            'writer_name': writer_name,  # Show who completed the writing
        })
    
    # Calculate statistics
    pending_stats = {
        'total': len(pending_jobs_display),
        'categories': len(set(j['job_category'] for j in pending_jobs_display)) if pending_jobs_display else 0,
        'high_priority': sum(1 for j in pending_jobs_display if j['priority'] in ['urgent', 'high']),
    }
    
    context = {
        'pending_jobs': pending_jobs_display,
        'pending_stats': pending_stats,
    }
    
    return render(request, 'allocator/pending_allocation_process.html', context)


# Update allocate_job view to handle process allocation
@role_required(['allocator'])
def allocate_job(request, system_id):
    """Allocate job to writer OR process team - depending on job status"""
    
    # Get the job
    job = get_object_or_404(Job, system_id=system_id)
    
    if request.method == 'POST':
        return _process_job_allocation(request, job)
    
    # GET request - show allocation form
    
    # Determine allocation type based on job status
    if job.status == 'Review':
        # Process team allocation
        allocation_type = 'process'
        try:
            all_members = CustomUser.objects.filter(role='process')
            available_members = [m for m in all_members if getattr(m, 'is_active', True)]
            available_members.sort(key=lambda x: (x.first_name or '', x.last_name or ''))
        except Exception as e:
            logger.error(f"Error fetching process members: {str(e)}", exc_info=True)
            available_members = []
        
        team_filter_note = "Showing all active process team members"
        
    else:
        # Writer allocation (default)
        allocation_type = 'writer'
        try:
            all_members = CustomUser.objects.filter(role='writer')
            available_members = [w for w in all_members if getattr(w, 'is_active', True)]
            available_members.sort(key=lambda x: (x.first_name or '', x.last_name or ''))
        except Exception as e:
            logger.error(f"Error fetching writers: {str(e)}", exc_info=True)
            available_members = []
        
        if job.category and job.category.upper() == 'IT':
            team_filter_note = "Showing all active writers. (IT-specific filtering to be implemented)"
        else:
            team_filter_note = "Showing all active writers"
    
    # Format members for dropdown
    members_list = []
    for member in available_members:
        members_list.append({
            'id': str(member.id),
            'name': member.get_full_name() or member.email,
            'email': member.email,
            'employee_id': getattr(member, 'employee_id', '') or '',
        })
    
    context = {
        'job': job,
        'writers': members_list,  # Keep 'writers' key for template compatibility
        'allocation_type': allocation_type,
        'team_filter_note': team_filter_note,
        'expected_deadline': job.expected_deadline,
        'strict_deadline': job.strict_deadline,
        'job_category': job.category,
    }
    
    return render(request, 'allocator/allocate_job.html', context)


@role_required(['allocator'])
def pending_allocation_process(request):
    """Show jobs pending PROCESS allocation (status='Review')"""
    
    # Get jobs with status 'Review' - these need process team allocation
    review_jobs = Job.objects.filter(
        status='Review'
    ).select_related('created_by', 'project_group', 'allocated_to').order_by('-updated_at')
    
    # Calculate priority and format for display
    pending_jobs_display = []
    now = timezone.now()
    
    for job in review_jobs:
        # Calculate priority based on deadline
        deadline = job.strict_deadline or job.expected_deadline
        priority = 'low'
        priority_label = 'Low'
        
        if deadline:
            time_diff = deadline - now
            if time_diff.total_seconds() < 0:
                priority = 'urgent'
                priority_label = 'Urgent (Overdue)'
            elif time_diff.days < 1:
                priority = 'urgent'
                priority_label = 'Urgent (< 24h)'
            elif time_diff.days < 3:
                priority = 'high'
                priority_label = 'High (< 3 days)'
            elif time_diff.days < 7:
                priority = 'medium'
                priority_label = 'Medium'
        
        # Get writer info if allocated
        writer_name = 'N/A'
        if job.allocated_to:
            writer_name = job.allocated_to.get_full_name() or job.allocated_to.email
        
        # Get marketing team member name from created_by
        created_by_name = 'Unknown'
        if job.created_by:
            # Get full name, fallback to email if no name
            created_by_name = job.created_by.get_full_name() or job.created_by.email
            # If get_full_name() returns empty string, use email
            if not created_by_name.strip():
                created_by_name = job.created_by.email
        
        pending_jobs_display.append({
            'id': str(job.id),
            'system_id': job.system_id,
            'masking_id': job.job_id,
            'topic': job.topic or 'No topic',
            'word_count': job.word_count,
            'deadline': deadline,
            'priority': priority,
            'priority_label': priority_label,
            'job_category': job.category or 'General',
            'created_by': created_by_name,  # ✅ Now shows marketing team member name
            'created_by_email': job.created_by.email if job.created_by else 'N/A',  # Extra info
            'writer_name': writer_name,  # Show who completed the writing
        })
    
    # Calculate statistics
    pending_stats = {
        'total': len(pending_jobs_display),
        'categories': len(set(j['job_category'] for j in pending_jobs_display)) if pending_jobs_display else 0,
        'high_priority': sum(1 for j in pending_jobs_display if j['priority'] in ['urgent', 'high']),
    }
    
    context = {
        'pending_jobs': pending_jobs_display,
        'pending_stats': pending_stats,
    }
    
    return render(request, 'allocator/pending_allocation_process.html', context)


@role_required(['allocator'])
def allocator_view_job_json(request, job_id):
    """API endpoint to fetch complete job details for Allocator Modal"""
    from marketing.models import WriterSubmission
    from process.models import Job as ProcessJob, ProcessSubmission
    
    try:
        job = get_object_or_404(Job, system_id=job_id)
        
        # Build Job Data
        job_data = {
            'system_id': job.system_id,
            'job_id': job.job_id,
            'topic': job.topic,
            'status': job.get_status_display(),
            'category': job.category,
            'word_count': job.word_count,
            'referencing_style': job.referencing_style,
            'writing_style': job.writing_style,
            'instruction': job.instruction,
            'software': job.software,
            'deadline': job.strict_deadline.isoformat() if job.strict_deadline else (job.expected_deadline.isoformat() if job.expected_deadline else None),
        }
        
        # Attachments
        attachments = []
        for att in job.attachments.all():
            attachments.append({
                'name': att.original_filename or 'Document',
                'url': att.file.url if att.file else '',
                'uploaded_at': att.uploaded_at.isoformat() if att.uploaded_at else None
            })
            
        # Writer Submissions
        writer_subs = []
        for sub in WriterSubmission.objects.filter(job=job).order_by('-submitted_at'):
             files = []
             for f in sub.files.all():
                 files.append({
                     'name': f.original_filename,
                     'url': f.file.url if f.file else ''
                 })
             writer_subs.append({
                 'type': sub.get_submission_type_display(),
                 'submitted_by': sub.submitted_by.get_full_name(),
                 'submitted_at': sub.submitted_at.isoformat(),
                 'files': files
             })

        # Process Submissions
        process_subs = []
        p_job = ProcessJob.objects.filter(job_id=job.system_id).first()
        if p_job:
            for sub in ProcessSubmission.objects.filter(job=p_job).order_by('-submitted_at'):
                files = []
                if sub.final_file: files.append({'name': 'Final File', 'url': sub.final_file.url})
                if sub.ai_file: files.append({'name': 'AI Report', 'url': sub.ai_file.url})
                if sub.plag_file: files.append({'name': 'Plag Report', 'url': sub.plag_file.url})
                if sub.grammarly_report: files.append({'name': 'Grammarly', 'url': sub.grammarly_report.url})
                if sub.other_files: files.append({'name': 'Other', 'url': sub.other_files.url})
                
                process_subs.append({
                    'stage': sub.stage.title(),
                    'submitted_by': sub.process_member.get_full_name(),
                    'submitted_at': sub.submitted_at.isoformat() if sub.submitted_at else None,
                    'files': files
                })
        
        # Allocations
        allocations = []
        for alloc in job.allocations.all():
            allocations.append({
                'type': alloc.get_allocation_type_display(),
                'user': alloc.allocated_to.get_full_name() if alloc.allocated_to else 'Unassigned',
                'status': alloc.get_status_display()
            })
            
        return JsonResponse({
            'job': job_data,
            'attachments': attachments,
            'writer_submissions': writer_subs,
            'process_submissions': process_subs,
            'allocations': allocations
        })

    except Exception as e:
        logger.error(f"Error in allocator_view_job_json: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
