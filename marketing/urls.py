from django.urls import path
from . import views

urlpatterns = [
    # Marketing Dashboard
    path('dashboard/', views.marketing_dashboard, name='marketing_dashboard'),
    
    # Job Creation - Two Form System (with AI)
    path('jobs/create/', views.create_job, name='create_job'),
    path('jobs/check-job-id/', views.check_job_id_unique, name='check_job_id_unique'),
    path('jobs/save-initial/', views.save_initial_form, name='save_initial_form'),
    path('jobs/generate-summary/', views.generate_ai_summary, name='generate_ai_summary'),
    path('jobs/accept-summary/', views.accept_summary, name='accept_summary'),
    path('jobs/summary-versions/<str:system_id>/', views.get_summary_versions, name='get_summary_versions'),
    path('jobs/system-amount/', views.get_system_expected_amount, name='get_system_expected_amount'),
    
    # Manual Job Creation (without AI)
    path('jobs/create-manual/', views.create_manual_job, name='create_manual_job'),
    path('jobs/submit-manual/', views.submit_manual_job, name='submit_manual_job'),
    
    # Job Management
    path('jobs/my-jobs/', views.my_jobs, name='my_jobs'),
    path('jobs/hold/', views.hold_jobs, name='hold_jobs'),
    path('jobs/query/', views.query_jobs, name='query_jobs'),
    path('jobs/unallocated/', views.unallocated_jobs, name='unallocated_jobs'),
    path('jobs/completed/', views.completed_jobs, name='completed_jobs'),
    path('jobs/allocated/', views.allocated_jobs, name='allocated_jobs'),

    # Final Job Form (for AI flow)
    path('jobs/<str:system_id>/final-form/', views.final_job_form, name='final_job_form'),
    path('jobs/copy-summary/', views.copy_summary_to_final, name='copy_summary_to_final'),
    
    # Job View
    path('jobs/<str:system_id>/view/', views.view_job_details, name='view_job_details'),
    
    # Customer Management
    path('customers/', views.customer_management, name='customer_management'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/toggle-status/', views.toggle_customer_status, name='toggle_customer_status'),
    path('customers/<str:customer_id>/kpis/', views.get_customer_kpis, name='get_customer_kpis'),
    path('customers/payment-entry/', views.payment_entry, name='payment_entry'),
    path('customers/payment-history/', views.payment_history, name='payment_history'),
    
    # Your Business
    path('your-business/', views.your_business, name='your_business'),
]