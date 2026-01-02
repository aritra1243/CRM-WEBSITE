# process/urls.py - COMPLETE AND UPDATED
from django.urls import path
from . import views

urlpatterns = [
    # =====================================
    # DASHBOARD & MAIN VIEWS
    # =====================================
    path('dashboard/', views.process_dashboard, name='process_dashboard'),
    
    # =====================================
    # TASKS PAGE (New feature)
    # =====================================
    path('tasks/', views.process_tasks, name='process_tasks'),
    path('task/<str:system_id>/select/', views.select_process_task, name='select_process_task'),
    path('task/<str:system_id>/writer-submissions/', views.get_writer_submissions, name='get_writer_submissions'),
    path('task/<str:system_id>/submit-process/', views.submit_process_file, name='submit_process_file'),
    
    # =====================================
    # JOBS MANAGEMENT
    # =====================================
    path('my-jobs/', views.my_jobs, name='process_my_jobs'),
    path('closed-jobs/', views.all_closed_jobs, name='process_closed_jobs'),
    path('job/<str:system_id>/', views.view_job, name='process_view_job'),
    path('job/<str:system_id>/json/', views.view_job_json, name='process_view_job_json'),
    
    # =====================================
    # SUBMISSIONS - CHECK, FINAL, DECORATION
    # =====================================
    path('job/<str:job_id>/submit-check/', views.submit_check_stage, name='submit_check_stage'),
    path('job/<str:job_id>/submit-final/', views.submit_final_stage, name='submit_final_stage'),
    path('job/<str:job_id>/submit-decoration/', views.submit_decoration, name='submit_decoration'),
    
    # =====================================
    # COMMENTS SYSTEM
    # =====================================
    path('job/<str:job_id>/add-comment/', views.add_comment, name='add_comment'),
    path('comment/<int:comment_id>/edit/', views.edit_comment, name='edit_comment'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
]
