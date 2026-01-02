# writer/views.py - Updated writer_dashboard function
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.http import JsonResponse
from allocator.models import JobAllocation
from marketing.models import Job, JobAttachment
from .models import WriterProject, ProjectIssue, ProjectComment, WriterStatistics
from accounts.models import CustomUser
import logging
import os
from django.db import transaction
from marketing.models import WriterSubmission, SubmissionFile
import time
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from datetime import timedelta

logger = logging.getLogger('writer')


def writer_required(view_func):
    """Decorator to ensure user is a writer"""
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'writer':
            messages.error(request, 'Access denied. Writer privileges required.')
            return redirect('home_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper



@login_required
@writer_required
def writer_dashboard(request):
    """Writer Dashboard View"""
    writer = request.user
    
    # Get or create writer statistics (djongo-safe)
    stats, created = WriterStatistics.fetch_or_create_single(writer)
    if created or (timezone.now() - stats.last_updated).seconds > 300:  # Update every 5 mins
        stats.update_stats()
		
		# Get all projects for the writer
    all_projects = WriterProject.objects.filter(writer=writer)
	
	 # Count by status
    total_projects = all_projects.count()
    pending_tasks = all_projects.filter(status='pending').count()
    in_progress = all_projects.filter(status='in_progress').count()
    completed = all_projects.filter(status='completed').count()
    issues = all_projects.filter(status='issues').count()
    hold = all_projects.filter(status='hold').count()
    
    # Recent projects for "My Tasks" table
    recent_projects = all_projects.exclude(status='completed').order_by('-created_at')[:5]
    
    # Calculate 24 hours ago from now
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    
    # Get today's allocated tasks (last 24 hours) from JobAllocation
    today_allocations = JobAllocation.objects.filter(
        allocated_to=writer,
        allocation_type='writer',
        status='active',
        marketing_job__status='allocated',  # Only allocated status
        allocated_at__gte=twenty_four_hours_ago  # Last 24 hours
    ).select_related('marketing_job').order_by('-allocated_at')[:5]
    
    # Build recent_projects list from allocations
    recent_projects = []
    for allocation in today_allocations:
        job = allocation.marketing_job
        recent_projects.append({
            'system_id': job.system_id,
            'topic': job.topic,
            'word_count': job.word_count,
            'deadline': allocation.end_date_time,
            'status': job.status,
        })
    
    # Get all projects for statistics (from JobAllocation)
    all_allocations = JobAllocation.objects.filter(
        allocated_to=writer,
        allocation_type='writer',
        status='active'
    ).select_related('marketing_job')
    
    # Count by job status
    total_projects = all_allocations.count()
    pending_tasks = all_allocations.filter(marketing_job__status='allocated').count()
    in_progress = all_allocations.filter(marketing_job__status='in_progress').count()
    completed = all_allocations.filter(marketing_job__status='completed').count()
    issues = 0  # You can add logic for issues if needed
    hold = all_allocations.filter(marketing_job__status='hold').count()
    
    # Calculate project status breakdown for chart
    status_breakdown = {
        'completed': completed,
        'in_progress': in_progress,
        'hold': hold,
        'pending': pending_tasks,
    }
    
    def percent(value, total):
        if not total:
            return 0
        return min(100, int(round((value / total) * 100)))
    
    progress_percent = {
        'completed': percent(completed, total_projects),
        'in_progress': percent(in_progress, total_projects),
        'hold': percent(hold, total_projects),
        'pending': percent(pending_tasks, total_projects),
    }
    
    context = {
        'total_projects': total_projects,
        'pending_tasks': pending_tasks,
        'in_progress': in_progress,
        'completed': completed,
        'issues': issues,
        'hold': hold,
        'recent_projects': recent_projects,
        'status_breakdown': status_breakdown,
        'stats': stats,
        'progress_percent': progress_percent,
    }
    
    return render(request, 'writer/writer_dashboard.html', context)

@login_required
@writer_required
def all_projects(request):
    """View all projects assigned to writer from allocator"""
    writer = request.user
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    # Allowed statuses
    allowed_statuses = ['allocated', 'completed', 'hold', 'in_progress', 'Review']
    
    # Base queryset - get allocations for this writer
    allocations = JobAllocation.objects.filter(
        allocated_to=writer,
        allocation_type='writer',
        status='active'
    ).select_related('marketing_job')
    
    # Filter by job status
    allocations = allocations.filter(marketing_job__status__in=allowed_statuses)
    
    # Apply status filter if provided
    if status_filter and status_filter in allowed_statuses:
        allocations = allocations.filter(marketing_job__status=status_filter)
    
    # Apply search filter
    if search_query:
        allocations = allocations.filter(
            Q(marketing_job__system_id__icontains=search_query) |
            Q(marketing_job__topic__icontains=search_query)
        )
    
    # Order by created date
    allocations = allocations.order_by('-allocated_at')
    
    # Build projects list with combined data
    projects = []
    for allocation in allocations:
        job = allocation.marketing_job
        projects.append({
            'system_id': job.system_id,
            'topic': job.topic,
            'word_count': job.word_count,
            'start_date': allocation.start_date_time,
            'end_date': allocation.end_date_time,
            'referencing_style': job.get_referencing_style_display() if job.referencing_style else None,
            'status': job.status,
        })
    
    # Status choices for filter dropdown
    STATUS_CHOICES = [
        ('allocated', 'Allocated'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('hold', 'Hold'),
        ('Review', 'Review'),
    ]
    
    context = {
        'projects': projects,
        'status_filter': status_filter,
        'search_query': search_query,
        'STATUS_CHOICES': STATUS_CHOICES,
    }
    
    return render(request, 'writer/all_projects.html', context)

@login_required
@writer_required
def project_detail_ajax(request, system_id):
    """AJAX view to fetch project details for modal"""
    writer = request.user
    
    try:
        # Get the allocation for this writer and job
        allocation = JobAllocation.objects.select_related(
            'marketing_job',
            'allocated_by'
        ).get(
            marketing_job__system_id=system_id,
            allocated_to=writer,
            allocation_type='writer'
        )
        
        job = allocation.marketing_job
        
        # Get attachments
        attachments = JobAttachment.objects.filter(job=job)
        
        # Format file size
        def format_file_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} MB"
        
        # Build response data
        data = {
            'success': True,
            'job': {
                'system_id': job.system_id,
                'job_id': job.job_id,
                'topic': job.topic,
                'word_count': job.word_count,
                'referencing_style_display': job.get_referencing_style_display() if job.referencing_style else None,
                'writing_style_display': job.get_writing_style_display() if job.writing_style else None,
                'level_display': job.get_level_display() if job.level else None,
                'job_summary': job.job_summary,
                'instruction': job.instruction,
                'category': job.get_category_display() if job.category else None,
                'software': job.software,
                'status': job.status,
                'status_display': job.get_status_display(),
                'expected_deadline': job.expected_deadline.strftime('%d %b %Y, %I:%M %p') if job.expected_deadline else None,
                'strict_deadline': job.strict_deadline.strftime('%d %b %Y, %I:%M %p') if job.strict_deadline else None,
            },
            'allocation': {
                'allocated_by_name': allocation.allocated_by.get_full_name() if allocation.allocated_by else 'System',
                'start_date': allocation.start_date_time.strftime('%d %b %Y, %I:%M %p'),
                'end_date': allocation.end_date_time.strftime('%d %b %Y, %I:%M %p'),
                'allocated_at': allocation.allocated_at.strftime('%d %b %Y, %I:%M %p'),
                'notes': allocation.notes,
            },
            'attachments': [
                {
                    'original_filename': att.original_filename,
                    'file_url': att.file.url if att.file else '#',
                    'file_size': format_file_size(att.file_size),
                }
                for att in attachments
            ]
        }
        
        return JsonResponse(data)
        
    except JobAllocation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Project not found or access denied.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error fetching project details: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while fetching project details.'
        }, status=500)

@login_required
@writer_required
def project_detail(request, system_id):
    """View project details from JobAllocation"""
    writer = request.user
    
    # Get the allocation for this writer and job
    allocation = get_object_or_404(
        JobAllocation,
        marketing_job__system_id=system_id,
        allocated_to=writer,
        allocation_type='writer'
    )
    
    job = allocation.marketing_job
    
    # Get comments and issues if WriterProject exists
    writer_project = WriterProject.objects.filter(job_id=job.job_id, writer=writer).first()
    
    comments = []
    issues = []
    if writer_project:
        comments = writer_project.comments.all().order_by('-created_at')
        issues = writer_project.issues.all().order_by('-created_at')
    
    context = {
        'allocation': allocation,
        'job': job,
        'project': writer_project,
        'comments': comments,
        'issues': issues,
    }
    
    return render(request, 'writer/project_detail.html', context)

# ... rest of your existing views remain the same ...


@login_required
@writer_required
def start_project(request, project_id):
    """Mark project as in progress"""
    writer = request.user
    project = get_object_or_404(WriterProject, id=project_id, writer=writer)
    
    if project.status == 'pending':
        project.mark_in_progress()
        messages.success(request, f'Project {project.job_id} marked as In Progress.')
        logger.info(f"Writer {writer.email} started project {project.job_id}")
    else:
        messages.warning(request, 'Project cannot be started from current status.')
    
    return redirect('project_detail', project_id=project.id)


@login_required
@writer_required
def submit_project(request, project_id):
    """Submit completed project"""
    writer = request.user
    project = get_object_or_404(WriterProject, id=project_id, writer=writer)
    
    if request.method == 'POST':
        submission_file = request.FILES.get('submission_file')
        submission_notes = request.POST.get('submission_notes', '')
        
        if not submission_file:
            messages.error(request, 'Please upload the submission file.')
            return redirect('project_detail', project_id=project.id)
        
        project.submission_file = submission_file
        project.submission_notes = submission_notes
        project.submitted_at = timezone.now()
        project.mark_completed()
        
        messages.success(request, f'Project {project.job_id} submitted successfully!')
        logger.info(f"Writer {writer.email} submitted project {project.job_id}")
        return redirect('all_projects')
    
    return redirect('project_detail', project_id=project.id)


@login_required
@writer_required
def writer_issues(request):
    """View all issues"""
    writer = request.user
    
    # Get all projects with issues
    projects_with_issues = WriterProject.objects.filter(
        writer=writer,
        status='issues'
    ).order_by('-updated_at')
    
    # Get all project issues reported by writer
    all_issues = ProjectIssue.objects.filter(
        reported_by=writer
    ).order_by('-created_at')
    
    context = {
        'projects_with_issues': projects_with_issues,
        'all_issues': all_issues,
    }
    
    return render(request, 'writer/writer_issues.html', context)


@login_required
@writer_required
def report_issue(request, project_id):
    """Report an issue for a project"""
    writer = request.user
    project = get_object_or_404(WriterProject, id=project_id, writer=writer)
    
    if request.method == 'POST':
        issue_type = request.POST.get('issue_type')
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        if not all([issue_type, title, description]):
            messages.error(request, 'All fields are required.')
            return redirect('project_detail', project_id=project.id)
        
        # Create issue
        ProjectIssue.objects.create(
            project=project,
            issue_type=issue_type,
            title=title,
            description=description,
            reported_by=writer,
            status='open'
        )
        
        # Update project status
        project.status = 'issues'
        project.save()
        
        messages.success(request, 'Issue reported successfully.')
        logger.info(f"Writer {writer.email} reported issue for project {project.job_id}")
        return redirect('writer_issues')
    
    return redirect('project_detail', project_id=project.id)


@login_required
@writer_required
def writer_hold(request):
    """View projects on hold"""
    writer = request.user
    
    hold_projects = WriterProject.objects.filter(
        writer=writer,
        status='hold'
    ).order_by('-updated_at')
    
    context = {
        'hold_projects': hold_projects,
    }
    
    return render(request, 'writer/writer_hold.html', context)


@login_required
@writer_required
def request_hold(request, project_id):
    """Request to put project on hold"""
    writer = request.user
    project = get_object_or_404(WriterProject, id=project_id, writer=writer)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        if not reason:
            messages.error(request, 'Please provide a reason for hold.')
            return redirect('project_detail', project_id=project.id)
        
        # Create issue for hold request
        ProjectIssue.objects.create(
            project=project,
            issue_type='other',
            title='Hold Request',
            description=f'Hold Reason: {reason}',
            reported_by=writer,
            status='open'
        )
        
        # Update project status
        project.status = 'hold'
        project.save()
        
        messages.success(request, 'Project put on hold. Admin will review your request.')
        logger.info(f"Writer {writer.email} put project {project.job_id} on hold")
        return redirect('writer_hold')
    
    return redirect('project_detail', project_id=project.id)


@login_required
@writer_required
def writer_close(request):
    """View closed/completed projects"""
    writer = request.user
    
    closed_projects = WriterProject.objects.filter(
        writer=writer,
        status__in=['completed', 'closed']
    ).order_by('-completed_at')
    
    context = {
        'closed_projects': closed_projects,
    }
    
    return render(request, 'writer/writer_close.html', context)


@login_required
@writer_required
def add_comment(request, project_id):
    """Add comment to a project"""
    writer = request.user
    project = get_object_or_404(WriterProject, id=project_id, writer=writer)
    
    if request.method == 'POST':
        comment_text = request.POST.get('comment', '')
        
        if not comment_text:
            messages.error(request, 'Comment cannot be empty.')
            return redirect('project_detail', project_id=project.id)
        
        ProjectComment.objects.create(
            project=project,
            user=writer,
            comment=comment_text
        )
        
        messages.success(request, 'Comment added successfully.')
        return redirect('project_detail', project_id=project.id)
    
    return redirect('project_detail', project_id=project.id)

@ensure_csrf_cookie
@login_required
@writer_required
def writer_tasks(request):
    """View all tasks assigned to writer - renders tasks.html with submission blocks"""
    writer = request.user
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    # Allowed statuses
    allowed_statuses = ['allocated', 'completed', 'hold', 'in_progress', 'Review']
    
    # Base queryset - get allocations for this writer
    allocations = JobAllocation.objects.filter(
        allocated_to=writer,
        allocation_type='writer',
        status='active'
    ).select_related('marketing_job')
    
    # Filter by job status
    allocations = allocations.filter(marketing_job__status__in=allowed_statuses)
    
    # Apply status filter if provided
    if status_filter and status_filter in allowed_statuses:
        allocations = allocations.filter(marketing_job__status=status_filter)
    
    # Apply search filter
    if search_query:
        allocations = allocations.filter(
            Q(marketing_job__system_id__icontains=search_query) |
            Q(marketing_job__topic__icontains=search_query)
        )
    
    # Order by created date
    allocations = allocations.order_by('-allocated_at')
    
    # Build projects list with combined data
    projects = []
    for allocation in allocations:
        job = allocation.marketing_job
        projects.append({
            'system_id': job.system_id,
            'topic': job.topic,
            'word_count': job.word_count,
            'start_date': allocation.start_date_time,
            'end_date': allocation.end_date_time,
            'referencing_style': job.get_referencing_style_display() if job.referencing_style else None,
            'status': job.status,
        })
    
    # Status choices for filter dropdown
    STATUS_CHOICES = [
        ('allocated', 'Allocated'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('hold', 'Hold'),
        ('Review', 'Review'),
    ]
    
    context = {
        'projects': projects,
        'status_filter': status_filter,
        'search_query': search_query,
        'STATUS_CHOICES': STATUS_CHOICES,
    }
    
    return render(request, 'writer/tasks.html', context)


@csrf_exempt  # TEMPORARY
@login_required
@writer_required
def select_task(request, system_id):
    """Writer selects a task to work on"""
    writer = request.user
    
    # Add logging
    logger.info(f"select_task called: method={request.method}, system_id={system_id}, writer={writer.email}")
    
    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method}")
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    try:
        # Get the allocation
        allocation = JobAllocation.objects.select_related('marketing_job').get(
            marketing_job__system_id=system_id,
            allocated_to=writer,
            allocation_type='writer',
            status='active'
        )
        
        job = allocation.marketing_job
        logger.info(f"Found job: {job.system_id}, current status: {job.status}")
        
        # Check if job is in correct status
        if job.status != 'allocated':
            logger.warning(f"Job {job.system_id} cannot be selected, status: {job.status}")
            return JsonResponse({
                'success': False,
                'error': f'Task cannot be selected. Current status: {job.status}'
            }, status=400)
        
        # Update job status to in_progress using update() instead of save()
        # This avoids the Decimal128 conversion issue
        Job.objects.filter(system_id=system_id).update(
            status='in_progress',
            writer_selected_at=timezone.now()
        )
        
        logger.info(f"Writer {writer.email} successfully selected task {job.system_id}")
        
        return JsonResponse({
            'success': True,
            'message': f'Task {job.system_id} selected successfully!'
        })
        
    except JobAllocation.DoesNotExist:
        logger.error(f"JobAllocation not found for system_id={system_id}, writer={writer.email}")
        return JsonResponse({
            'success': False,
            'error': 'Task not found or access denied'
        }, status=404)
    except Exception as e:
        logger.error(f"Error selecting task: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)

@login_required
@writer_required
def submit_structure(request, system_id):
    """Submit structure (Block 1) - FIXED VERSION"""
    writer = request.user
    
    logger.info(f"submit_structure called: method={request.method}, system_id={system_id}, writer={writer.email}")
    
    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method}")
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    try:
        # Get the allocation
        allocation = JobAllocation.objects.select_related('marketing_job').get(
            marketing_job__system_id=system_id,
            allocated_to=writer,
            allocation_type='writer'
        )
        
        job = allocation.marketing_job
        logger.info(f"Found job: {job.system_id}, current status: {job.status}")
        
        # Validate notes
        notes = request.POST.get('notes', '').strip()
        logger.info(f"Notes length: {len(notes)}")
        
        word_count = len(notes.split())
        
        if word_count > 250:
            logger.warning(f"Notes exceed 250 words: {word_count}")
            return JsonResponse({
                'success': False,
                'error': f'Notes exceed 250 words limit. Current: {word_count} words'
            }, status=400)
        
        if not notes:
            logger.warning("Notes are empty")
            return JsonResponse({
                'success': False,
                'error': 'Notes are required'
            }, status=400)
        
        # Get uploaded files - FIXED
        files = request.FILES.getlist('files')
        logger.info(f"Received {len(files)} file(s) from request.FILES.getlist('files')")
        logger.info(f"All request.FILES keys: {list(request.FILES.keys())}")
        logger.info(f"request.FILES contents: {dict(request.FILES)}")
        
        # Log each file
        for idx, file in enumerate(files):
            logger.info(f"File {idx}: name={file.name}, size={file.size}, content_type={file.content_type}")
        
        # ENFORCE 1 FILE LIMIT FOR STRUCTURE
        if len(files) != 1:
            logger.warning(f"Invalid file count: {len(files)}")
            return JsonResponse({
                'success': False,
                'error': f'Exactly 1 file is required for structure submission. You uploaded {len(files)} file(s).'
            }, status=400)
        
        file = files[0]
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            logger.warning(f"File too large: {file.size} bytes")
            return JsonResponse({
                'success': False,
                'error': f'File size exceeds 10MB limit. Your file: {file.size / (1024 * 1024):.2f}MB'
            }, status=400)
        
        # Validate file type
        allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
        file_ext = os.path.splitext(file.name)[1].lower()
        
        if file_ext not in allowed_extensions:
            logger.warning(f"Invalid file type: {file_ext}")
            return JsonResponse({
                'success': False,
                'error': f'Invalid file type: {file_ext}. Allowed: {", ".join(allowed_extensions)}'
            }, status=400)

        
        # Create submission with transaction
        with transaction.atomic():
            # Check if structure already exists
            existing_submission = WriterSubmission.objects.filter(
                job=job,
                submitted_by=writer,
                submission_type='structure'
            ).first()
            
            if existing_submission:
                logger.info(f"Updating existing structure submission for {job.system_id}")
                # Update existing submission
                existing_submission.notes = notes
                existing_submission.updated_at = timezone.now()
                existing_submission.save()
                
                # Delete old files
                old_files = existing_submission.files.all()
                logger.info(f"Deleting {old_files.count()} old file(s)")
                for old_file in old_files:
                    if old_file.file:
                        try:
                            default_storage.delete(old_file.file.name)
                        except Exception as e:
                            logger.error(f"Error deleting old file: {str(e)}")
                old_files.delete()                
                submission = existing_submission
            else:
                logger.info(f"Creating new structure submission for {job.system_id}")
                # Create new submission
                submission = WriterSubmission.objects.create(
                    job=job,
                    submitted_by=writer,
                    submission_type='structure',
                    notes=notes,
                    status='submitted'
                )
            
 # Save the file with ORIGINAL NAME
            from django.core.files.storage import default_storage
            
            # Create directory path: structure/system_id/
            dir_path = f'structure/{job.system_id}'
            
            # Ensure directory exists
            if not default_storage.exists(dir_path):
                logger.info(f"Creating directory: {dir_path}")
            
            # Use original filename directly
            full_path = f'{dir_path}/{file.name}'
            
            # If file already exists, delete it first
            if default_storage.exists(full_path):
                logger.info(f"Deleting existing file: {full_path}")
                default_storage.delete(full_path)
            
            # Save file using Django's storage
            logger.info(f"Saving file to: {full_path}")
            file_path = default_storage.save(full_path, file)
            logger.info(f"File saved successfully: {file_path}")
            
            # Create SubmissionFile record
            submission_file = SubmissionFile.objects.create(
                submission=submission,
                file=file_path,
                original_filename=file.name,
                file_size=file.size
            )
            logger.info(f"SubmissionFile record created: ID={submission_file.id}")
            
            # Update job status using update() to avoid Decimal128 issue
            updated_count = Job.objects.filter(id=job.id).update(
                structure_submitted=True,
                structure_submitted_at=timezone.now()
            )
            logger.info(f"Job updated: {updated_count} record(s)")
        
        logger.info(f"Writer {writer.email} successfully submitted structure for {job.system_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Structure submitted successfully!',
            'file_saved': file.name,
            'file_path': file_path
        })
        
    except JobAllocation.DoesNotExist:
        logger.error(f"JobAllocation not found for system_id={system_id}, writer={writer.email}")
        return JsonResponse({
            'success': False,
            'error': 'Task not found or access denied'
        }, status=404)
    except Exception as e:
        logger.error(f"Error submitting structure: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'An error occurred while submitting structure: {str(e)}'
        }, status=500)

@csrf_exempt  # TEMPORARY
@login_required
@writer_required
def submit_final_copy(request, system_id):
    """Submit final copy (Block 2)"""
    writer = request.user
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    try:
        # Get the allocation
        allocation = JobAllocation.objects.select_related('marketing_job').get(
            marketing_job__system_id=system_id,
            allocated_to=writer,
            allocation_type='writer'
        )
        
        job = allocation.marketing_job
        
        # Check if structure is submitted
        if not job.structure_submitted:
            return JsonResponse({
                'success': False,
                'error': 'Please submit structure first'
            }, status=400)
        
        # Validate notes
        notes = request.POST.get('notes', '').strip()
        word_count = len(notes.split())
        
        if word_count > 3000:
            return JsonResponse({
                'success': False,
                'error': f'Notes exceed 3000 words limit. Current: {word_count} words'
            }, status=400)
        
        if not notes:
            return JsonResponse({
                'success': False,
                'error': 'Notes are required'
            }, status=400)
        
        # Get uploaded files
        files = request.FILES.getlist('files')
        
        if len(files) > 10:
            return JsonResponse({
                'success': False,
                'error': 'Maximum 10 files allowed'
            }, status=400)
        
        # Create submission with transaction
        with transaction.atomic():
            # Create new submission
            submission = WriterSubmission.objects.create(
                job=job,
                submitted_by=writer,
                submission_type='final_copy',
                notes=notes,
                status='submitted'
            )
            
             # Save files with ORIGINAL NAMES
            import os
            from django.core.files.storage import default_storage
            
            for file in files:
                # Create directory path: final_copy/system_id/
                dir_path = f'final_copy/{job.system_id}'
                
                # Use original filename directly
                full_path = f'{dir_path}/{file.name}'
                
                # Save file using Django's storage
                file_path = default_storage.save(full_path, file)
                
                SubmissionFile.objects.create(
                    submission=submission,
                    file=file_path,
                    original_filename=file.name,
                    file_size=file.size
                )
            
            # Update job status to Review using update() to avoid Decimal128 issue
            Job.objects.filter(id=job.id).update(
                final_copy_submitted=True,
                final_copy_submitted_at=timezone.now(),
                status='Review'
            )
        
        logger.info(f"Writer {writer.email} submitted final copy for {job.system_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Final copy submitted successfully! Status changed to Review.'
        })
        
    except JobAllocation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Task not found or access denied'
        }, status=404)
    except Exception as e:
        logger.error(f"Error submitting final copy: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while submitting final copy'
        }, status=500)

@csrf_exempt 
@login_required
@writer_required
def get_submission_details(request, system_id):
    """Get submission details for a task"""
    writer = request.user
    
    try:
        allocation = JobAllocation.objects.select_related('marketing_job').get(
            marketing_job__system_id=system_id,
            allocated_to=writer,
            allocation_type='writer'
        )
        
        job = allocation.marketing_job
        
        # Get structure submission
        structure_submission = WriterSubmission.objects.filter(
            job=job,
            submitted_by=writer,
            submission_type='structure'
        ).first()
        
        structure_data = None
        if structure_submission:
            structure_files = structure_submission.files.all()
            structure_data = {
                'notes': structure_submission.notes,
                'submitted_at': structure_submission.submitted_at.strftime('%d %b %Y, %I:%M %p'),
                'files': [
                    {
                        'filename': f.original_filename,
                        'url': f.file.url if f.file else '#',
                        'size': f'{f.file_size / 1024:.1f} KB' if f.file_size < 1024 * 1024 else f'{f.file_size / (1024 * 1024):.1f} MB'
                    }
                    for f in structure_files
                ],
                'file_count': structure_files.count()
            }
        
        # Get final copy submission
        final_copy_submission = WriterSubmission.objects.filter(
            job=job,
            submitted_by=writer,
            submission_type='final_copy'
        ).first()
        
        final_copy_data = None
        if final_copy_submission:
            final_files = final_copy_submission.files.all()
            final_copy_data = {
                'notes': final_copy_submission.notes,
                'submitted_at': final_copy_submission.submitted_at.strftime('%d %b %Y, %I:%M %p'),
                'files': [
                    {
                        'filename': f.original_filename,
                        'url': f.file.url if f.file else '#',
                        'size': f'{f.file_size / 1024:.1f} KB' if f.file_size < 1024 * 1024 else f'{f.file_size / (1024 * 1024):.1f} MB'
                    }
                    for f in final_files
                ],
                'file_count': final_files.count()
            }
        
        return JsonResponse({
            'success': True,
            'structure': structure_data,
            'final_copy': final_copy_data,
            'job_status': job.status
        })
        
    except JobAllocation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Task not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error fetching submission details: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred'
        }, status=500)
