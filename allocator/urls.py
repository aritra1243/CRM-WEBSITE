# allocator/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Allocator Dashboard
    path('dashboard/', views.allocator_dashboard, name='allocator_dashboard'),
    path('all-projects/', views.all_projects, name='allocator_all_projects'),
    path('all-projects/<str:system_id>/', views.all_projects_detail, name='allocator_all_project_detail'),
    
    # Job Allocation Management
    path('pending/', views.pending_allocation, name='pending_allocation'),
    
    # NEW: Process allocation page
    path('pending-process/', views.pending_allocation_process, name='pending_allocation_process'),
    
    path('allocate/<str:system_id>/', views.allocate_job, name='allocate_job'),
    path('assigned/', views.assigned_jobs, name='assigned_jobs'),
    path('in-progress/', views.in_progress_jobs, name='in_progress_jobs'),
    path('cancel/', views.cancel_jobs, name='cancel_jobs'),
    path('hold/', views.hold_jobs_allocator, name='hold_jobs_allocator'),
    path('process/', views.process_jobs, name='process_jobs'),
    path('completed/', views.completed_jobs_allocator, name='completed_jobs_allocator'),
    
    # Team Management
    path('writers/', views.all_writers, name='all_writers'),
    path('process-team/', views.all_process_team, name='all_process_team'),
    
    # Actions
    path('switch-writer/<int:allocation_id>/', views.switch_writer, name='switch_writer'),
    path('job/<str:system_id>/', views.view_job_details, name='allocator_view_job_details'),
    path('job/<str:job_id>/json-details/', views.allocator_view_job_json, name='allocator_view_job_json'),
    path('approve-comment/<int:job_id>/', views.approve_comment, name='approve_comment'),
    path('job-status/<str:masking_id>/', views.get_job_status, name='get_job_status'),
    path('download/<int:attachment_id>/', views.download_attachment, name='download_attachment'),
]