from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    path('dashboard/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('pending/', views.pending_items, name='pending_items'),
    
    # User Management Actions
    path('add-user/', views.add_user, name='add_user'),
    path('change-user-password/<int:user_id>/', views.change_user_password, name='change_user_password'),  # NEW ROUTE
    path('update-role/<int:user_id>/', views.update_user_role, name='update_user_role'),
    path('update-category/<int:user_id>/', views.update_user_category, name='update_user_category'),
    path('update-level/<int:user_id>/', views.update_user_level, name='update_user_level'),
    path('update-organisation/<int:user_id>/', views.update_user_organisation, name='update_user_organisation'),
    path('toggle-status/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    
    # Approval Actions
    path('approve-user/<int:user_id>/', views.approve_user, name='approve_user'),
    path('reject-user/<int:user_id>/', views.reject_user, name='reject_user'),
    path('profile-request/<int:request_id>/approve/', views.approve_profile_request, name='approve_profile_request'),
    path('profile-request/<int:request_id>/reject/', views.reject_profile_request, name='reject_profile_request'),
    
    # API Endpoints
    path('role-details/<str:role>/', views.role_details, name='role_details'),

    # Master Input
    path('master-input/', views.master_input, name='master_input'),
    
    # Holiday Master
    path('holiday-master/', views.holiday_master, name='holiday_master'),
    path('holiday-master/create/', views.create_holiday, name='create_holiday'),
    path('holiday-master/<int:holiday_id>/edit/', views.edit_holiday, name='edit_holiday'),
    path('holiday-master/delete/<int:holiday_id>/', views.delete_holiday, name='delete_holiday'),
    
    # Holiday Calendar - Accessible to all users
    path('holiday-calendar/', views.holiday_calendar, name='holiday_calendar'),

    # Price Master
    path('price-master/', views.price_master, name='price_master'),
    path('price-master/create/', views.create_price, name='create_price'),
    path('price-master/<int:price_id>/edit/', views.edit_price, name='edit_price'),
    path('price-master/delete/<int:price_id>/', views.delete_price, name='delete_price'),

    # Referencing Master
    path('referencing-master/', views.referencing_master, name='referencing_master'),
    path('referencing-master/create/', views.create_reference, name='create_reference'),
    path('referencing-master/<str:reference_id>/edit/', views.edit_reference, name='edit_reference'),
    path('referencing-master/delete/<str:reference_id>/', views.delete_reference, name='delete_reference'),

    # Academic Writing Style Master
    path('academic-writing-master/', views.academic_writing_master, name='academic_writing_master'),
    path('academic-writing-master/create/', views.create_writing, name='create_writing'),
    path('academic-writing-master/<str:writing_id>/edit/', views.edit_writing, name='edit_writing'),
    path('academic-writing-master/delete/<str:writing_id>/', views.delete_writing, name='delete_writing'),
    
    # Project Group Master
    path('project-group-master/', views.project_group_master, name='project_group_master'),
    path('project-group-master/create/', views.create_project_group, name='create_project_group'),
    path('project-group-master/<int:group_id>/edit/', views.edit_project_group, name='edit_project_group'),
    path('project-group-master/delete/<int:group_id>/', views.delete_project_group, name='delete_project_group'),
    # Specialisation Master
    path('specialisation-master/', views.specialisation_master, name='specialisation_master'),
    path('specialisation-master/create/', views.create_specialisation, name='create_specialisation'),
    path('specialisation-master/<str:specialisation_id>/edit/', views.edit_specialisation, name='edit_specialisation'),
    path('specialisation-master/delete/<str:specialisation_id>/', views.delete_specialisation, name='delete_specialisation'),
    path('update-specialisations/<int:user_id>/', views.update_user_specialisations, name='update_user_specialisations'),
    
    # Organisation Master
    path('organisation-master/', views.organisation_master, name='organisation_master'),
    path('organisation-master/create/', views.create_organisation, name='create_organisation'),
    path('organisation-master/<str:org_id>/edit/', views.edit_organisation, name='edit_organisation'),
    path('organisation-master/delete/<str:org_id>/', views.delete_organisation, name='delete_organisation'),
    
    # Marketing Job Drops
    path('marketing-job-drops/', views.marketing_job_drops, name='marketing_job_drops'),
    path('job-drop/<str:job_id>/', views.job_drop_details, name='job_drop_details'),
    path('job-drop/<str:job_id>/api/', views.job_drop_api, name='job_drop_api'),
    path('job-drops/search/', views.search_job_drops, name='search_job_drops'),
    
    # Marketing Manager Details
    path('marketing-manager-details/', views.marketing_manager_details, name='marketing_manager_details'),
    path('marketing-manager-details/customer/<str:customer_id>/toggle-active/', views.toggle_customer_active, name='toggle_customer_active'),
    path('marketing-manager-details/customer/<str:customer_id>/update-target/', views.update_customer_target, name='update_customer_target'),
    
    # Writer Insights
    path('writer-details/', views.all_writer_details, name='all_writer_details'),
    path('writer-details/<int:writer_id>/', views.writer_details, name='writer_details'),
    
    # All Letter Master
    path('all-letter-master/', views.all_letter_master, name='all_letter_master'),
    path('all-letter-master/create/', views.create_letter_template, name='create_letter_template'),
    path('all-letter-master/<int:template_id>/edit/', views.edit_letter_template, name='edit_letter_template'),
    path('all-letter-master/delete/<int:template_id>/', views.delete_letter_template, name='delete_letter_template'),

    # Generate Letter
    path('generate-letter/', views.generate_letter_selection, name='generate_letter_selection'),
    path('generate-letter/form/', views.generate_letter_form, name='generate_letter_form'),
    path('generate-letter/preview/', views.generate_letter_preview, name='generate_letter_preview'),

    # Admin My Letters
    path('my-letters/', views.admin_my_letters, name='admin_my_letters'),
    path('my-letters/<int:letter_id>/', views.admin_view_letter, name='admin_view_letter'),

]

