# process/views.py - COMPLETE FILE
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Job, ProcessSubmission, JobComment, DecorationTask
from accounts.models import CustomUser
import logging

logger = logging.getLogger(__name__)


def process_required(view_func):
    """Decorator to ensure only process team members can access"""
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'process':
            messages.error(request, 'Access denied. Process team members only.')
            return redirect('home_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@process_required
def process_dashboard(request):
    """Process Team Dashboard - Show jobs assigned in the last 24 hours"""
    
    # Import JobAllocation to query jobs assigned to this process member
    from allocator.models import JobAllocation
    from marketing.models import Job as MarketingJob
    from django.utils import timezone
    from datetime import timedelta
    
    # Calculate 24 hours ago
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    
    # Get allocations for this process member and fetch related jobs
    allocations = JobAllocation.objects.filter(
        allocated_to=request.user,
        allocation_type='process',
        status='active',
        allocated_at__gte=twenty_four_hours_ago  # Only last 24 hours
    ).select_related('marketing_job').order_by('-allocated_at')
    
    # Create a list of jobs with their allocation info
    my_jobs_list = []
    for allocation in allocations:
        job = allocation.marketing_job
        if job.status in ['process', 'in_review']:
            # Add allocation info to the job object for template access
            job.allocation_time = allocation.allocated_at
            job.allocation_deadline = allocation.end_date_time  # Deadline for process team
            my_jobs_list.append(job)
    
    # Sort by allocation time (most recent first)
    my_jobs_list.sort(key=lambda x: x.allocation_time if hasattr(x, 'allocation_time') and x.allocation_time else x.updated_at, reverse=True)
    
    # Create a queryset-like paginator
    from django.core.paginator import Paginator
    
    paginator = Paginator(my_jobs_list, 25)
    page_number = request.GET.get('page')
    jobs = paginator.get_page(page_number)
    
    context = {
        'jobs': jobs,
        'total_jobs': len(my_jobs_list),
        'process_member_name': request.user.get_full_name(),
    }
    
    return render(request, 'process/process_dashboard.html', context)


@login_required
@process_required
def my_jobs(request):
    """My Jobs - All jobs assigned to this process member"""
    
    from allocator.models import JobAllocation
    from marketing.models import Job as MarketingJob
    
    # Get all allocations for this process member (not just last 24 hours)
    allocations = JobAllocation.objects.filter(
        allocated_to=request.user,
        allocation_type='process',
        status='active'
    ).select_related('marketing_job').order_by('-allocated_at')
    
    # Extract the actual job objects and filter by status
    my_jobs_list = []
    for allocation in allocations:
        job = allocation.marketing_job
        if job.status in ['process', 'in_review', 'completed', 'submitted']:
            my_jobs_list.append(job)
    
    # Sort by updated_at
    my_jobs_list.sort(key=lambda x: x.updated_at, reverse=True)
    
    from django.core.paginator import Paginator
    
    paginator = Paginator(my_jobs_list, 25)
    page_number = request.GET.get('page')
    jobs_page = paginator.get_page(page_number)
    
    context = {
        'jobs': jobs_page,
        'page_title': 'My Jobs',
        'total_jobs': len(my_jobs_list),
    }
    
    return render(request, 'process/my_jobs.html', context)


@login_required
@process_required
def all_closed_jobs(request):
    """All Closed Jobs - Completed/Submitted jobs"""
    
    from allocator.models import JobAllocation
    
    # Get allocations for this user to identify relevant jobs
    allocations = JobAllocation.objects.filter(
        allocated_to=request.user,
        allocation_type='process'
    ).select_related('marketing_job')
    
    # Create list of closed jobs, self-healing missing records
    jobs_list = []
    
    for alloc in allocations:
        m_job = alloc.marketing_job
        if m_job and m_job.status in ['completed', 'submitted']:
            # Find existing Process Job or create it
            p_job = Job.objects.filter(job_id=m_job.system_id).first()
            
            if not p_job:
                # Self-healing: Create missing Process Job record
                p_job = Job.objects.create(
                    job_id=m_job.system_id,
                    topic=m_job.topic or 'N/A',
                    word_count=m_job.word_count or 0,
                    deadline=m_job.strict_deadline or m_job.expected_deadline or timezone.now(),
                    referencing=m_job.referencing_style or 'Other',
                    status=m_job.status,
                    process_member=request.user
                )
            else:
                # Sync status if needed
                if p_job.status != m_job.status:
                    p_job.status = m_job.status
                    p_job.save(update_fields=['status'])
            
            jobs_list.append(p_job)
            
    # Sort by updated_at (newest first)
    jobs_list.sort(key=lambda x: x.updated_at, reverse=True)
    
    # Count total closed jobs
    total_closed_jobs = len(jobs_list)
    
    # Pagination - 25 per page
    paginator = Paginator(jobs_list, 25)
    page_number = request.GET.get('page')
    jobs = paginator.get_page(page_number)
    
    context = {
        'jobs': jobs,
        'total_closed_jobs': total_closed_jobs,
    }
    
    return render(request, 'process/all_closed_jobs.html', context)


@login_required
@process_required
@login_required
@process_required
def view_job(request, system_id):
    """View Job Details - Process Team View"""
    
    from marketing.models import Job as MarketingJob
    from allocator.models import JobAllocation
    import os
    from django.conf import settings
    
    # Get marketing job by system_id
    marketing_job = get_object_or_404(MarketingJob, system_id=system_id)
    
    # Check if current user has access (is allocated to this job)
    allocation = JobAllocation.objects.filter(
        marketing_job=marketing_job,
        allocated_to=request.user,
        allocation_type='process',
        status='active'
    ).first()
    
    if not allocation:
        messages.error(request, 'You do not have access to this job.')
        return redirect('process_dashboard')
    
    # Create job proxy for template compatibility
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
                        from django.utils import timezone
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
    
    return render(request, 'process/view_job.html', context)


@login_required
@process_required
def submit_check_stage(request, job_id):
    """Submit Check Stage (AI & Plag files)"""
    
    if request.method != 'POST':
        return redirect('view_job', job_id=job_id)
    
    job = get_object_or_404(Job, job_id=job_id, process_member=request.user)
    
    ai_file = request.FILES.get('ai_file')
    plag_file = request.FILES.get('plag_file')
    
    if not ai_file or not plag_file:
        messages.error(request, 'Both AI and Plagiarism files are required for Check Stage.')
        return redirect('view_job', job_id=job_id)
    
    try:
        submission = ProcessSubmission.objects.create(
            job=job,
            process_member=request.user,
            stage='check',
            ai_file=ai_file,
            plag_file=plag_file
        )
        
        job.status = 'in_progress'
        job.save()
        
        logger.info(f"Check stage submitted by {request.user.email} for job {job_id}")
        messages.success(request, 'Check stage files uploaded successfully!')
        
    except Exception as e:
        logger.error(f"Error submitting check stage for job {job_id}: {str(e)}")
        messages.error(request, 'An error occurred while uploading files.')
    
    return redirect('view_job', job_id=job_id)


@login_required
@process_required
def submit_final_stage(request, job_id):
    """Submit Final Stage (Final File, AI, Plag, Grammarly, Other)"""
    
    if request.method != 'POST':
        return redirect('view_job', job_id=job_id)
    
    job = get_object_or_404(Job, job_id=job_id, process_member=request.user)
    
    final_file = request.FILES.get('final_file')
    ai_file = request.FILES.get('ai_file')
    plag_file = request.FILES.get('plag_file')
    grammarly_report = request.FILES.get('grammarly_report')
    other_files = request.FILES.get('other_files')
    
    if not all([final_file, ai_file, plag_file]):
        messages.error(request, 'Final File, AI File, and Plag File are required.')
        return redirect('view_job', job_id=job_id)
    
    try:
        submission = ProcessSubmission.objects.create(
            job=job,
            process_member=request.user,
            stage='final',
            final_file=final_file,
            ai_file=ai_file,
            plag_file=plag_file,
            grammarly_report=grammarly_report,
            other_files=other_files
        )
        
        job.status = 'submitted'
        job.save()
        
        logger.info(f"Final stage submitted by {request.user.email} for job {job_id}")
        messages.success(request, 'Final stage files uploaded successfully!')
        
    except Exception as e:
        logger.error(f"Error submitting final stage for job {job_id}: {str(e)}")
        messages.error(request, 'An error occurred while uploading files.')
    
    return redirect('view_job', job_id=job_id)


@login_required
@process_required
def submit_decoration(request, job_id):
    """Submit Decoration Stage"""
    
    if request.method != 'POST':
        return redirect('view_job', job_id=job_id)
    
    job = get_object_or_404(Job, job_id=job_id)
    
    # Check if user has decoration task for this job
    if not hasattr(job, 'decoration_task') or job.decoration_task.process_member != request.user:
        messages.error(request, 'You are not assigned to decoration for this job.')
        return redirect('process_dashboard')
    
    decoration_task = job.decoration_task
    
    final_file = request.FILES.get('final_file')
    ai_file = request.FILES.get('ai_file')
    plag_file = request.FILES.get('plag_file')
    other_files = request.FILES.get('other_files')
    
    if not all([final_file, ai_file, plag_file]):
        messages.error(request, 'Final File, AI File, and Plag File are required.')
        return redirect('view_job', job_id=job_id)
    
    try:
        decoration_task.final_file = final_file
        decoration_task.ai_file = ai_file
        decoration_task.plag_file = plag_file
        decoration_task.other_files = other_files
        decoration_task.is_completed = True
        decoration_task.completed_at = timezone.now()
        decoration_task.save()
        
        logger.info(f"Decoration submitted by {request.user.email} for job {job_id}")
        messages.success(request, 'Decoration files uploaded successfully!')
        
    except Exception as e:
        logger.error(f"Error submitting decoration for job {job_id}: {str(e)}")
        messages.error(request, 'An error occurred while uploading files.')
    
    return redirect('view_job', job_id=job_id)


@login_required
@process_required
def add_comment(request, job_id):
    """Add Comment to Job"""
    
    if request.method != 'POST':
        return redirect('view_job', job_id=job_id)
    
    job = get_object_or_404(Job, job_id=job_id)
    
    text = request.POST.get('comment_text', '').strip()
    attachment = request.FILES.get('attachment')
    link = request.POST.get('link', '').strip()
    
    if len(text) < 5 and not attachment:
        messages.error(request, 'Comment must be at least 5 characters or include an attachment.')
        return redirect('view_job', job_id=job_id)
    
    try:
        comment = JobComment.objects.create(
            job=job,
            user=request.user,
            text=text,
            attachment=attachment,
            link=link if link else None
        )
        
        logger.info(f"Comment added by {request.user.email} on job {job_id}")
        messages.success(request, 'Comment added successfully!')
        
    except Exception as e:
        logger.error(f"Error adding comment to job {job_id}: {str(e)}")
        messages.error(request, 'An error occurred while adding comment.')
    
    return redirect('view_job', job_id=job_id)


@login_required
@process_required
def edit_comment(request, comment_id):
    """Edit Comment"""
    
    if request.method != 'POST':
        return redirect('process_dashboard')
    
    comment = get_object_or_404(JobComment, id=comment_id, user=request.user)
    
    text = request.POST.get('comment_text', '').strip()
    
    if len(text) < 5:
        messages.error(request, 'Comment must be at least 5 characters.')
        return redirect('view_job', job_id=comment.job.job_id)
    
    try:
        comment.text = text
        comment.save()
        
        logger.info(f"Comment {comment_id} edited by {request.user.email}")
        messages.success(request, 'Comment updated successfully!')
        
    except Exception as e:
        logger.error(f"Error editing comment {comment_id}: {str(e)}")
        messages.error(request, 'An error occurred while updating comment.')
    
    return redirect('view_job', job_id=comment.job.job_id)


@login_required
@process_required
def delete_comment(request, comment_id):
    """Delete Comment"""
    
    comment = get_object_or_404(JobComment, id=comment_id, user=request.user)
    job_id = comment.job.job_id
    
    try:
        comment.delete()
        logger.info(f"Comment {comment_id} deleted by {request.user.email}")
        messages.success(request, 'Comment deleted successfully!')
        
    except Exception as e:
        logger.error(f"Error deleting comment {comment_id}: {str(e)}")
        messages.error(request, 'An error occurred while deleting comment.')
    
    return redirect('view_job', job_id=job_id)


@login_required
@process_required
def view_job_json(request, system_id):
    """API endpoint to fetch job details as JSON for modal popup"""
    from django.http import JsonResponse
    from django.core.serializers.json import DjangoJSONEncoder
    from marketing.models import Job as MarketingJob
    from allocator.models import JobAllocation
    import json
    
    try:
        # Get marketing job by system_id
        marketing_job = get_object_or_404(MarketingJob, system_id=system_id)
        
        # Check if current user has access (is allocated to this job)
        allocation = JobAllocation.objects.filter(
            marketing_job=marketing_job,
            allocated_to=request.user,
            allocation_type='process',
            status='active'
        ).first()
        
        if not allocation:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Build job data
        job_data = {
            'job_id': marketing_job.job_id,
            'system_id': marketing_job.system_id,
            'topic': marketing_job.topic,
            'status': marketing_job.status,
            'word_count': marketing_job.word_count,
            'referencing_style': marketing_job.referencing_style,
            'writing_style': marketing_job.writing_style,
            'category': marketing_job.category,
            'instruction': marketing_job.instruction,
            'software': marketing_job.software,
            'expected_deadline': marketing_job.expected_deadline.isoformat() if marketing_job.expected_deadline else None,
            'strict_deadline': marketing_job.strict_deadline.isoformat() if marketing_job.strict_deadline else None,
        }
        
        # Get attachments
        attachments = []
        for att in marketing_job.attachments.all():
            attachments.append({
                'file': att.file.url if att.file else '',
                'original_filename': att.original_filename or 'Document'
            })
        
        # Get writer submissions
        submissions = []
        for sub in marketing_job.writer_submissions.all():
            # Get the first file from this submission
            submission_file = sub.files.first()
            submissions.append({
                'submission_type': sub.submission_type,
                'submitted_at': submission_file.uploaded_at.isoformat() if submission_file and submission_file.uploaded_at else None,
                'file': submission_file.file.url if submission_file and submission_file.file else ''
            })
        
        # Get allocations
        allocations_data = []
        for alloc in JobAllocation.objects.filter(marketing_job=marketing_job, status='active'):
            allocations_data.append({
                'allocated_user': alloc.allocated_to.email if alloc.allocated_to else 'Unknown',
                'allocation_type': alloc.allocation_type,
                'status': alloc.status,
                'allocated_at': alloc.allocated_at.isoformat() if alloc.allocated_at else None
            })
        
        return JsonResponse({
            'job': job_data,
            'attachments': attachments,
            'submissions': submissions,
            'allocations': allocations_data
        })
    
    except Exception as e:
        logger.error(f"Error fetching job details JSON: {str(e)}")
        return JsonResponse({'error': 'Failed to load job details'}, status=500)


# =====================================
# PROCESS TASKS PAGE VIEWS (New Feature)
# =====================================

@login_required
@process_required
def process_tasks(request):
    """Process Tasks Page - Similar to Writer Tasks"""
    from marketing.models import Job as MarketingJob
    from allocator.models import JobAllocation
    
    # Get allocations for current user with status process or in_review
    allocations = JobAllocation.objects.filter(
        allocated_to=request.user,
        allocation_type='process',
        status='active'
    ).select_related('marketing_job')
    
    # Build project list
    projects = []
    for alloc in allocations:
        job = alloc.marketing_job
        if job and job.status in ['process', 'in_review']:
            projects.append({
                'system_id': job.system_id,
                'topic': job.topic,
                'word_count': job.word_count,
                'start_date': alloc.start_date_time,
                'end_date': alloc.end_date_time,
                'referencing_style': job.referencing_style,
                'status': job.status,
                'allocation': alloc
            })
    
    # Search filter
    search_query = request.GET.get('search', '')
    if search_query:
        projects = [p for p in projects if search_query.lower() in p['system_id'].lower() or 
                   (p['topic'] and search_query.lower() in p['topic'].lower())]
    
    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        projects = [p for p in projects if p['status'] == status_filter]
    
    STATUS_CHOICES = [
        ('process', 'Process'),
        ('in_review', 'In Review'),
        ('completed', 'Completed'),
    ]
    
    context = {
        'projects': projects,
        'search_query': search_query,
        'status_filter': status_filter,
        'STATUS_CHOICES': STATUS_CHOICES,
    }
    
    return render(request, 'process/process_tasks.html', context)


@login_required
@process_required
def select_process_task(request, system_id):
    """Select a process task - Update status to in_review"""
    from django.http import JsonResponse
    from marketing.models import Job as MarketingJob
    from allocator.models import JobAllocation
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        # Get the marketing job
        marketing_job = get_object_or_404(MarketingJob, system_id=system_id)
        
        # Check if user has allocation
        allocation = JobAllocation.objects.filter(
            marketing_job=marketing_job,
            allocated_to=request.user,
            allocation_type='process',
            status='active'
        ).first()
        
        if not allocation:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Only allow selection if status is 'process'
        if marketing_job.status != 'process':
            return JsonResponse({'error': 'Task already selected or completed'}, status=400)
        
        # Update status to in_review
        marketing_job.status = 'in_review'
        marketing_job.save(update_fields=['status'])
        
        logger.info(f"Process task {system_id} selected by {request.user.email}, status changed to in_review")
        
        return JsonResponse({'success': True, 'message': 'Task selected successfully'})
    
    except Exception as e:
        logger.error(f"Error selecting process task: {str(e)}")
        return JsonResponse({'error': 'Failed to select task'}, status=500)


@login_required
@process_required
def get_writer_submissions(request, system_id):
    """Get writer submissions for Block 1 and Block 2"""
    from django.http import JsonResponse
    from marketing.models import Job as MarketingJob
    from allocator.models import JobAllocation
    
    try:
        marketing_job = get_object_or_404(MarketingJob, system_id=system_id)
        
        # Check access
        allocation = JobAllocation.objects.filter(
            marketing_job=marketing_job,
            allocated_to=request.user,
            allocation_type='process',
            status='active'
        ).first()
        
        if not allocation:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get writer submissions
        structure_data = None
        final_copy_data = None
        
        for sub in marketing_job.writer_submissions.all():
            files = []
            for f in sub.files.all():
                files.append({
                    'file_url': f.file.url if f.file else '',
                    'filename': f.original_filename or 'Document',
                    'uploaded_at': f.uploaded_at.isoformat() if f.uploaded_at else None
                })
            
            if sub.submission_type == 'structure':
                structure_data = {
                    'notes': sub.notes,
                    'files': files,
                    'submitted_at': sub.submitted_at.isoformat() if sub.submitted_at else None
                }
            elif sub.submission_type == 'final_copy':
                final_copy_data = {
                    'notes': sub.notes,
                    'files': files,
                    'submitted_at': sub.submitted_at.isoformat() if sub.submitted_at else None
                }
        
        return JsonResponse({
            'success': True,
            'structure': structure_data,
            'final_copy': final_copy_data
        })
    
    except Exception as e:
        logger.error(f"Error getting writer submissions: {str(e)}")
        return JsonResponse({'error': 'Failed to load submissions'}, status=500)


@login_required
@process_required
def submit_process_file(request, system_id):
    """Submit process file - Block 3 and update status to completed"""
    from django.http import JsonResponse
    from marketing.models import Job as MarketingJob
    from allocator.models import JobAllocation
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        marketing_job = get_object_or_404(MarketingJob, system_id=system_id)
        
        # Check access
        allocation = JobAllocation.objects.filter(
            marketing_job=marketing_job,
            allocated_to=request.user,
            allocation_type='process',
            status='active'
        ).first()
        
        if not allocation:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Only allow submission if status is in_review
        if marketing_job.status != 'in_review':
            return JsonResponse({'error': 'Task must be in review status'}, status=400)
        
        # Get uploaded files
        uploaded_files = request.FILES.getlist('file')
        notes = request.POST.get('notes', '')
        
        if not uploaded_files:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        # Find or Create the Process Job instance linked to this Marketing Job
        process_job, created = Job.objects.get_or_create(
            job_id=marketing_job.system_id,
            defaults={
                'topic': marketing_job.topic or 'N/A',
                'word_count': marketing_job.word_count or 0,
                'deadline': marketing_job.strict_deadline or marketing_job.expected_deadline or timezone.now(),
                'referencing': marketing_job.referencing_style or 'Other'
            }
        )
        
        # Ensure process job has correct member and status
        process_job.process_member = request.user
        process_job.status = 'completed'
        process_job.save()
        
        # Create ProcessSubmission for EACH file
        for uploaded_file in uploaded_files:
            ProcessSubmission.objects.create(
                job=process_job,
                process_member=request.user,
                stage='final',
                final_file=uploaded_file
            )
        
        # Update marketing job status to completed
        marketing_job.status = 'completed'
        marketing_job.save(update_fields=['status'])
        
        # Close all active allocations
        JobAllocation.objects.filter(
            marketing_job=marketing_job,
            status='active'
        ).update(status='completed', completed_at=timezone.now())
        
        logger.info(f"Process file submitted for {system_id} by {request.user.email}, status changed to completed")
        
        return JsonResponse({'success': True, 'message': 'File submitted successfully'})
    
    except Exception as e:
        logger.error(f"Error submitting process file: {str(e)}")
        return JsonResponse({'error': 'Failed to submit file'}, status=500)