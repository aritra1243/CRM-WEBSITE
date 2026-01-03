import logging
import json
import random
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from bson import ObjectId
from bson.errors import InvalidId
import logging

from accounts.models import CustomUser
from accounts.services import log_activity_event
from marketing.models import Job
from .models import (
    Holiday,
    PriceMaster,
    ReferencingMaster,
    AcademicWritingMaster,
    ProjectGroupMaster,
    SpecialisationMaster,
    OrganisationMaster,
    JobDrop,
    LetterTemplate,
)
from .utils import extract_template_variables, get_user_field_value
from accounts.models import CustomUser
from . import user_services as portal_services

logger = logging.getLogger('superadmin')


def _filter_not_deleted(iterable):
    """Return only items that are not soft-deleted."""
    return [
        item for item in iterable
        if not getattr(item, 'is_deleted', False)
    ]

from datetime import datetime


def superadmin_required(view_func):
    """Decorator to check if user is superadmin"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('login')
        if request.user.role != 'superadmin':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('home_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ========================================
# USER MANAGEMENT VIEWS
# ========================================

@login_required
@superadmin_required
def superadmin_dashboard(request):
    """SuperAdmin Dashboard"""
    context = portal_services.get_dashboard_context()
    return render(request, 'superadmin_dashboard.html', context)


@login_required
@superadmin_required
def role_details(request, role):
    """Return JSON list of today's active users for role"""
    users_data = portal_services.get_role_details_data(role)
    return JsonResponse({'users': users_data})


@login_required
@superadmin_required
def manage_users(request):
    """Manage all users"""
    context = portal_services.get_manage_users_context(performed_by=request.user)

    # Add specialisations to context
    from common.pymongo_utils import pymongo_filter
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        all_specs = pymongo_filter(SpecialisationMaster, sort=[('specialisation_name', 1)])
        context['all_specialisations'] = _filter_not_deleted(all_specs)
    except Exception as e:
        logger.exception(f"Error loading specialisations via PyMongo: {str(e)}")
        context['all_specialisations'] = []
    
    # Add organisations to context
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        all_orgs = pymongo_filter(OrganisationMaster, sort=[('organisation_name', 1)])
        context['all_organisations'] = _filter_not_deleted(all_orgs)
    except Exception as e:
        logger.exception(f"Error loading organisations via PyMongo: {str(e)}")
        context['all_organisations'] = []
    
    return render(request, 'manage_users.html', context)


@login_required
@superadmin_required
def update_user_role(request, user_id):
    """Update user role"""
    portal_services.update_user_role(request, user_id)
    return redirect('superadmin:manage_users')


@login_required
@superadmin_required
def update_user_category(request, user_id):
    """Update user category/department"""
    portal_services.update_user_category(request, user_id)
    return redirect('superadmin:manage_users')


@login_required
@superadmin_required
def update_user_level(request, user_id):
    """Update user level"""
    portal_services.update_user_level(request, user_id)
    return redirect('superadmin:manage_users')


@login_required
@superadmin_required
def update_user_organisation(request, user_id):
    """Update user's organisation assignment"""
    if request.method == 'POST':
        try:
            user = CustomUser.objects.get(id=user_id)
            org_name = request.POST.get('organisation', '').strip()
            
            if org_name:
                # Find organisation by name using PyMongo
                all_orgs = pymongo_filter(OrganisationMaster)
                org = next(
                    (o for o in all_orgs 
                     if o.organisation_name == org_name 
                     and not getattr(o, 'is_deleted', False)),
                    None
                )
                if org:
                    # Use PyMongo for update
                    pymongo_update(CustomUser, {'id': user.id}, organisation_id=org.id)
                    messages.success(request, f'Organisation updated for {user.get_full_name()}')
                else:
                    messages.error(request, 'Organisation not found.')
            else:
                # Clear organisation using PyMongo
                pymongo_update(CustomUser, {'id': user.id}, organisation_id=None)
                messages.success(request, f'Organisation cleared for {user.get_full_name()}')
        except CustomUser.DoesNotExist:
            messages.error(request, 'User not found.')
        except Exception as e:
            logger.exception(f"Error updating user organisation: {str(e)}")
            messages.error(request, 'An error occurred while updating the organisation.')
    
    return redirect('superadmin:manage_users')

@login_required
@superadmin_required
def toggle_user_status(request, user_id):
    """Toggle user active status"""
    portal_services.toggle_user_status(request, user_id)
    return redirect('superadmin:manage_users')


# @login_required
# @superadmin_required
# def edit_user(request, user_id):
#     """Edit user profile"""
#     edit_target = get_object_or_404(CustomUser, id=user_id)
    
#     if request.method == 'POST':
#         portal_services.process_edit_user_form(request, edit_target)
#         return redirect('manage_users')
    
#     context = {
#         'edit_user': edit_target,
#     }
#     return render(request, 'edit_user.html', context)

@login_required
@superadmin_required
def edit_user(request, user_id):
    """Edit user profile"""
    edit_target = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        portal_services.process_edit_user_form(request, edit_target)
        return redirect('superadmin:manage_users')
    
    try:
        all_specs = SpecialisationMaster.objects.all().order_by('specialisation_name')
        all_specialisations = _filter_not_deleted(all_specs)
    except Exception as e:
        logger.exception(f"Error loading specialisations: {str(e)}")
        all_specialisations = []
    
    context = {
        'edit_user': edit_target,
        'all_specialisations': all_specialisations,
    }
    return render(request, 'edit_user.html', context)


@login_required
@superadmin_required
def pending_items(request):
    """Pending approvals page"""
    context = portal_services.get_pending_items_context()
    return render(request, 'pending_items.html', context)


@login_required
@superadmin_required
def approve_user(request, user_id):
    """Approve user registration"""
    portal_services.approve_user(request, user_id)
    return redirect('superadmin:pending_items')


@login_required
@superadmin_required
def reject_user(request, user_id):
    """Reject user registration"""
    portal_services.reject_user(request, user_id)
    return redirect('superadmin:pending_items')


@login_required
@superadmin_required
def approve_profile_request(request, request_id):
    """Approve profile change request"""
    portal_services.approve_profile_request(request, request_id)
    return redirect('superadmin:pending_items')


@login_required
@superadmin_required
def reject_profile_request(request, request_id):
    """Reject profile change request"""
    portal_services.reject_profile_request(request, request_id)
    return redirect('superadmin:pending_items')


# ========================================
# MASTER INPUT VIEWS
# ========================================

@login_required
@superadmin_required
def master_input(request):
    """Master Input Dashboard"""
    return render(request, 'master_input.html')


# ========================================
# HOLIDAY MASTER VIEWS
# ========================================

@login_required
@superadmin_required
def holiday_master(request):
    """Holiday Master - List all holidays"""
    from common.pymongo_utils import pymongo_filter
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        raw_holidays = pymongo_filter(Holiday, sort=[('created_at', -1)])
        holidays = [
            holiday for holiday in raw_holidays
            if not getattr(holiday, 'is_deleted', False)
        ]
        context = {
            'holidays': holidays,
            'total_holidays': len(holidays),
        }
        return render(request, 'holiday_master.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading holiday master: {str(e)}")
        messages.error(request, 'Error loading holidays.')
        return render(request, 'holiday_master.html', {'holidays': []})


@login_required
def holiday_calendar(request):
    """Holiday Calendar View - Accessible to all authenticated users"""
    try:
        # Get all non-deleted holidays
        raw_holidays = list(Holiday.objects.all().order_by('date', 'from_date'))
        holidays = [
            holiday for holiday in raw_holidays
            if not getattr(holiday, 'is_deleted', False)
        ]
        
        # Build events list for calendar
        events = []
        for holiday in holidays:
            if holiday.date_type == 'single':
                events.append({
                    'id': holiday.id,
                    'title': holiday.holiday_name,
                    'start': holiday.date.isoformat(),
                    'end': holiday.date.isoformat(),
                    'type': holiday.holiday_type,
                    'description': holiday.description or '',
                    'date_display': holiday.date.strftime('%d %b %Y'),
                    'is_consecutive': False,
                })
            else:  # consecutive
                events.append({
                    'id': holiday.id,
                    'title': holiday.holiday_name,
                    'start': holiday.from_date.isoformat(),
                    'end': holiday.to_date.isoformat(),
                    'type': holiday.holiday_type,
                    'description': holiday.description or '',
                    'date_display': f"{holiday.from_date.strftime('%d %b %Y')} - {holiday.to_date.strftime('%d %b %Y')}",
                    'is_consecutive': True,
                })
        
        context = {
            'holidays': holidays,
            'total_holidays': len(holidays),
            'events_json': json.dumps(events),
            'current_year': timezone.now().year,
        }
        
        return render(request, 'holiday_calendar.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading holiday calendar: {str(e)}")
        messages.error(request, 'Error loading holiday calendar.')
        return render(request, 'holiday_calendar.html', {
            'holidays': [],
            'total_holidays': 0,
            'events_json': '[]',
        })


@login_required
@superadmin_required
def create_holiday(request):
    """Create a new holiday"""
    if request.method == 'POST':
        try:
            # Get form data
            holiday_name = request.POST.get('holiday_name', '').strip()
            holiday_type = request.POST.get('holiday_type', 'full_day')
            date_type = request.POST.get('date_type', 'single')
            description = request.POST.get('description', '').strip()
            
            # Validation
            if not holiday_name:
                messages.error(request, 'Holiday name is required.')
                return redirect('superadmin:holiday_master')
            
            # Create holiday object
            with transaction.atomic():
                holiday = Holiday()
                holiday.holiday_name = holiday_name
                holiday.holiday_type = holiday_type
                holiday.date_type = date_type
                holiday.description = description
                holiday.created_by = request.user
                holiday.created_at = timezone.now()
                
                # Handle dates based on type
                if date_type == 'single':
                    date_str = request.POST.get('date')
                    if not date_str:
                        messages.error(request, 'Date is required.')
                        return redirect('superadmin:holiday_master')
                    
                    holiday.date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    start_date = holiday.date
                    end_date = holiday.date
                    
                else:  # consecutive
                    from_date_str = request.POST.get('from_date')
                    to_date_str = request.POST.get('to_date')
                    
                    if not from_date_str or not to_date_str:
                        messages.error(request, 'From date and To date are required.')
                        return redirect('superadmin:holiday_master')
                    
                    holiday.from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                    holiday.to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                    
                    if holiday.from_date > holiday.to_date:
                        messages.error(request, 'From date must be before To date.')
                        return redirect('superadmin:holiday_master')
                    
                    start_date = holiday.from_date
                    end_date = holiday.to_date
                
                # Save to database first
                holiday.save()
                
                # Log activity
                log_activity_event(
                    'holiday.created_at',
                    subject_user=None,
                    performed_by=request.user,
                    metadata={
                        'holiday_id': holiday.id,
                        'holiday_name': holiday_name,
                        'date_type': date_type,
                    },
                )
                
                logger.info(f"Holiday '{holiday_name}' created successfully")
                messages.success(request, f'Holiday "{holiday_name}" created successfully!')
            
            return redirect('superadmin:holiday_master')
            
        except Exception as e:
            logger.exception(f"Error creating holiday: {str(e)}")
            messages.error(request, 'An error occurred while creating the holiday.')
            return redirect('superadmin:holiday_master')
    
    return redirect('superadmin:holiday_master')


@login_required
@superadmin_required
def edit_holiday(request, holiday_id):
    """Update an existing holiday"""
    if request.method != 'POST':
        return redirect('superadmin:holiday_master')
    
    holiday = next(
        (
            item for item in Holiday.objects.all()
            if item.id == holiday_id and not getattr(item, 'is_deleted', False)
        ),
        None
    )
    
    if not holiday:
        messages.error(request, 'Holiday not found.')
        return redirect('superadmin:holiday_master')
    
    try:
        holiday_name = request.POST.get('holiday_name', '').strip()
        holiday_type = request.POST.get('holiday_type', 'full_day')
        date_type = request.POST.get('date_type', 'single')
        description = request.POST.get('description', '').strip()
        
        if not holiday_name:
            messages.error(request, 'Holiday name is required.')
            return redirect('superadmin:holiday_master')
        
        if date_type == 'single':
            date_str = request.POST.get('date')
            if not date_str:
                messages.error(request, 'Date is required for single-day holiday.')
                return redirect('superadmin:holiday_master')
            start_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            end_date = start_date
        else:
            from_date_str = request.POST.get('from_date')
            to_date_str = request.POST.get('to_date')
            
            if not from_date_str or not to_date_str:
                messages.error(request, 'Both From and To dates are required for consecutive holidays.')
                return redirect('superadmin:holiday_master')
            
            start_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            
            if start_date > end_date:
                messages.error(request, 'From date must be before To date.')
                return redirect('superadmin:holiday_master')
        
        with transaction.atomic():
            holiday.holiday_name = holiday_name
            holiday.holiday_type = holiday_type
            holiday.date_type = date_type
            holiday.description = description
            holiday.updated_by = request.user
            holiday.updated_at = timezone.now()
            
            if date_type == 'single':
                holiday.date = start_date
                holiday.from_date = None
                holiday.to_date = None
            else:
                holiday.date = None
                holiday.from_date = start_date
                holiday.to_date = end_date
            
            holiday.save()
            
            log_activity_event(
                'holiday.updated_at',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'holiday_id': holiday.id,
                    'holiday_name': holiday.holiday_name,
                },
            )
            
            messages.success(request, f'Holiday "{holiday.holiday_name}" updated successfully.')
    
    except Exception as e:
        logger.exception(f"Error updating holiday: {str(e)}")
        messages.error(request, 'An error occurred while updating the holiday.')
    
    return redirect('superadmin:holiday_master')


@login_required
@superadmin_required
def delete_holiday(request, holiday_id):
    """Permanently delete a holiday"""
    if request.method != 'POST':
        return redirect('superadmin:holiday_master')
    
    holiday = Holiday.objects.filter(id=holiday_id).first()
    
    if not holiday:
        messages.error(request, 'Holiday not found.')
        return redirect('superadmin:holiday_master')
    
    holiday_id_ref = holiday.id
    holiday_name_ref = holiday.holiday_name
    
    try:
        with transaction.atomic():
            holiday.delete()
            
            log_activity_event(
                'holiday.deleted',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'holiday_id': holiday_id_ref,
                    'holiday_name': holiday_name_ref,
                },
            )
        
        messages.success(request, f'Holiday "{holiday_name_ref}" deleted successfully.')
    
    except Exception as e:
        logger.exception(f"Error deleting holiday: {str(e)}")
        messages.error(request, 'An error occurred while deleting the holiday.')
    
    return redirect('superadmin:holiday_master')


# This is continuation of views.py - PRICE and REFERENCING MASTER sections
# Copy this after Holiday Master views

# ========================================
# PRICE MASTER VIEWS
# ========================================

@login_required
@superadmin_required
def price_master(request):
    """Price Master - List all prices"""
    from common.pymongo_utils import pymongo_filter
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        raw_prices = pymongo_filter(PriceMaster, sort=[('created_at', -1)])
        prices = [
            price for price in raw_prices
            if not getattr(price, 'is_deleted', False)
        ]
        context = {
            'prices': prices,
            'total_prices': len(prices),
        }
        return render(request, 'price_master.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading price master: {str(e)}")
        messages.error(request, 'Error loading prices.')
        return render(request, 'price_master.html', {'prices': [], 'total_prices': 0})


@login_required
@superadmin_required
def create_price(request):
    """Create a new price entry"""
    if request.method == 'POST':
        try:
            category = request.POST.get('category', '').strip()
            level = request.POST.get('level', '').strip()
            price_per_word = request.POST.get('price_per_word', '').strip()
            
            # Validation
            if not category or not level or not price_per_word:
                messages.error(request, 'All fields are required.')
                return redirect('superadmin:price_master')
            
            try:
                price_per_word = float(price_per_word)
                if price_per_word <= 0:
                    messages.error(request, 'Price per word must be greater than 0.')
                    return redirect('superadmin:price_master')
            except ValueError:
                messages.error(request, 'Invalid price format.')
                return redirect('superadmin:price_master')
            
            # Check for existing combination
            all_matching = list(PriceMaster.objects.filter(
                category=category,
                level=level
            ))
            
            existing = next(
                (item for item in all_matching if not getattr(item, 'is_deleted', False)),
                None
            )
            
            if existing:
                messages.error(request, f'Price already exists for {category} - {level}.')
                return redirect('superadmin:price_master')
            
            with transaction.atomic():
                price_obj = PriceMaster()
                price_obj.category = category
                price_obj.level = level
                price_obj.price_per_word = price_per_word
                price_obj.created_by = request.user
                price_obj.created_at = timezone.now()
                price_obj.save()
                
                log_activity_event(
                    'price.created_at',
                    subject_user=None,
                    performed_by=request.user,
                    metadata={
                        'price_id': str(price_obj.id),
                        'category': category,
                        'level': level,
                        'price_per_word': str(price_per_word),
                    },
                )
                
                logger.info(f"Price created for {category} - {level} by {request.user.email}")
                messages.success(request, f'Price for {category} - {level} created successfully!')
            
            return redirect('superadmin:price_master')
            
        except Exception as e:
            logger.exception(f"Error creating price: {str(e)}")
            messages.error(request, 'An error occurred while creating the price.')
            return redirect('superadmin:price_master')
    
    return redirect('superadmin:price_master')


@login_required
@superadmin_required
def edit_price(request, price_id):
    """Update an existing price entry"""
    if request.method != 'POST':
        return redirect('superadmin:price_master')
    
    all_prices = list(PriceMaster.objects.filter(id=price_id))
    price_obj = next(
        (item for item in all_prices if not getattr(item, 'is_deleted', False)),
        None
    )
    
    if not price_obj:
        messages.error(request, 'Price entry not found.')
        return redirect('superadmin:price_master')
    
    try:
        category = request.POST.get('category', '').strip()
        level = request.POST.get('level', '').strip()
        price_per_word = request.POST.get('price_per_word', '').strip()
        
        if not category or not level or not price_per_word:
            messages.error(request, 'All fields are required.')
            return redirect('superadmin:price_master')
        
        try:
            price_per_word = float(price_per_word)
            if price_per_word <= 0:
                messages.error(request, 'Price per word must be greater than 0.')
                return redirect('superadmin:price_master')
        except ValueError:
            messages.error(request, 'Invalid price format.')
            return redirect('superadmin:price_master')
        
        # Check for duplicate combination (excluding current record)
        all_matching = list(PriceMaster.objects.filter(
            category=category,
            level=level
        ))
        
        existing = next(
            (item for item in all_matching 
             if item.id != price_id and not getattr(item, 'is_deleted', False)),
            None
        )
        
        if existing:
            messages.error(request, f'Price already exists for {category} - {level}.')
            return redirect('superadmin:price_master')
        
        with transaction.atomic():
            price_obj.category = category
            price_obj.level = level
            price_obj.price_per_word = price_per_word
            price_obj.updated_by = request.user
            price_obj.updated_at = timezone.now()
            price_obj.save()
            
            log_activity_event(
                'price.updated_at',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'price_id': str(price_obj.id),
                    'category': category,
                    'level': level,
                    'price_per_word': str(price_per_word),
                },
            )
        
        messages.success(request, f'Price for {category} - {level} updated successfully.')
    
    except Exception as e:
        logger.exception(f"Error updating price: {str(e)}")
        messages.error(request, 'An error occurred while updating the price.')
    
    return redirect('superadmin:price_master')


@login_required
@superadmin_required
def delete_price(request, price_id):
    """Delete a price entry"""
    if request.method != 'POST':
        return redirect('superadmin:price_master')
    
    price_obj = None
    try:
        price_obj = PriceMaster.objects.get(id=price_id)
    except PriceMaster.DoesNotExist:
        messages.error(request, 'Price entry not found.')
        return redirect('superadmin:price_master')
    
    price_id_ref = str(price_obj.id)
    category_ref = price_obj.category
    level_ref = price_obj.level
    
    try:
        with transaction.atomic():
            price_obj.delete()
            
            log_activity_event(
                'price.deleted',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'price_id': price_id_ref,
                    'category': category_ref,
                    'level': level_ref,
                },
            )
        
        messages.success(request, f'Price for {category_ref} - {level_ref} deleted successfully.')
    
    except Exception as e:
        logger.exception(f"Error deleting price: {str(e)}")
        messages.error(request, 'An error occurred while deleting the price.')
    
    return redirect('superadmin:price_master')


# ========================================
# REFERENCING MASTER VIEWS
# ========================================

@login_required
@superadmin_required
def referencing_master(request):
    """Referencing Master - List all references"""
    from common.pymongo_utils import pymongo_filter
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        raw_references = pymongo_filter(ReferencingMaster, sort=[('created_at', -1)])
        references = [
            ref for ref in raw_references
            if not getattr(ref, 'is_deleted', False)
        ]
        context = {
            'references': references,
            'total_references': len(references),
        }
        return render(request, 'referencing_master.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading referencing master: {str(e)}")
        messages.error(request, 'Error loading references.')
        return render(request, 'referencing_master.html', {'references': [], 'total_references': 0})


# ========================================
# ALL LETTER MASTER VIEWS
# ========================================

@login_required
@superadmin_required
def all_letter_master(request):
    """Letter Master - List all letter templates"""
    from common.pymongo_utils import pymongo_filter
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        raw_templates = pymongo_filter(LetterTemplate, sort=[('created_at', -1)])
        templates = [
            t for t in raw_templates
            if not getattr(t, 'is_deleted', False)
        ]
        context = {
            'templates': templates,
            'total_templates': len(templates),
        }
        return render(request, 'all_letter_master.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading letter master: {str(e)}")
        messages.error(request, 'Error loading letter templates.')
        return render(request, 'all_letter_master.html', {'templates': [], 'total_templates': 0})


@login_required
@superadmin_required
@login_required
@superadmin_required
def create_letter_template(request):
    """Create a new letter template"""
    if request.method == 'POST':
        try:
            from common.pymongo_utils import pymongo_filter, get_mongo_db
            
            letter_type = request.POST.get('letter_type', '').strip()
            template_content = request.POST.get('template_content', '').strip()
            is_trigger = request.POST.get('is_trigger') == 'on'
            
            if not letter_type or not template_content:
                messages.error(request, 'Letter Type and Content are required.')
                return redirect('superadmin:all_letter_master')
            
            # Check if this type already exists (active) using PyMongo
            query = {
                'letter_type': letter_type,
                'is_deleted': False
            }
            existing = pymongo_filter(LetterTemplate, query=query)
            
            if existing:
                # get_letter_type_display might not work on dict/incomplete obj, but let's try or map manually
                # For simplicity, we just say "A template for this type..."
                messages.error(request, f'A template for {letter_type} already exists.')
                return redirect('superadmin:all_letter_master')
            
            # Use direct MongoDB insertion
            db = get_mongo_db()
            collection = db[LetterTemplate._meta.db_table]
            
            new_template = {
                'letter_type': letter_type,
                'template_content': template_content,
                'is_trigger': is_trigger,
                'created_by_id': request.user.id,
                'created_at': timezone.now(),
                'updated_at': timezone.now(),
                'is_deleted': False
            }
            
            result = collection.insert_one(new_template)
            new_id = result.inserted_id
            collection.update_one({'_id': new_id}, {'$set': {'id': new_id}})
            
            log_activity_event(
                'letter_template.created',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'letter_type': letter_type,
                },
            )
            
            logger.info(f"Letter Template '{letter_type}' created successfully")
            messages.success(request, f'Template for {letter_type} created successfully!')
            
            return redirect('superadmin:all_letter_master')
            
        except Exception as e:
            logger.exception(f"Error creating letter template: {str(e)}")
            messages.error(request, 'An error occurred while creating the template.')
            return redirect('superadmin:all_letter_master')
    
    return redirect('superadmin:all_letter_master')


@login_required
@superadmin_required
@login_required
@superadmin_required
def edit_letter_template(request, template_id):
    """Update an existing letter template"""
    if request.method != 'POST':
        return redirect('superadmin:all_letter_master')
    
    from common.pymongo_utils import pymongo_filter, get_mongo_db
    from bson import ObjectId

    # Find using PyMongo
    try:
        # Try finding by ObjectId first
        if isinstance(template_id, str) and len(template_id) == 24:
             query = {'_id': ObjectId(template_id), 'is_deleted': False}
        else:
             query = {'id': template_id, 'is_deleted': False}
             
        matches = pymongo_filter(LetterTemplate, query=query)
        if not matches:
             query = {'id': str(template_id), 'is_deleted': False}
             matches = pymongo_filter(LetterTemplate, query=query)
             
        template = matches[0] if matches else None
    except Exception:
        template = None
    
    if not template:
        messages.error(request, 'Template not found.')
        return redirect('superadmin:all_letter_master')
    
    try:
        letter_type = request.POST.get('letter_type', '').strip()
        template_content = request.POST.get('template_content', '').strip()
        is_trigger = request.POST.get('is_trigger') == 'on'
        
        if not letter_type or not template_content:
            messages.error(request, 'Letter Type and Content are required.')
            return redirect('superadmin:all_letter_master')
        
        # Check duplicate if type changed
        if letter_type != template.letter_type:
             query = {
                'letter_type': letter_type,
                'id': {'$ne': template.id},
                'is_deleted': False
             }
             existing = pymongo_filter(LetterTemplate, query=query)
             
             if existing:
                messages.error(request, f'A template for {letter_type} already exists.')
                return redirect('superadmin:all_letter_master')
        
        # Update via PyMongo
        db = get_mongo_db()
        collection = db[LetterTemplate._meta.db_table]
        
        update_fields = {
            'letter_type': letter_type,
            'template_content': template_content,
            'is_trigger': is_trigger,
            'updated_by_id': request.user.id,
            'updated_at': timezone.now()
        }
        
        if hasattr(template, '_id'):
            collection.update_one({'_id': template._id}, {'$set': update_fields})
        else:
            collection.update_one({'id': template.id}, {'$set': update_fields})
        
        log_activity_event(
            'letter_template.updated',
            subject_user=None,
            performed_by=request.user,
            metadata={
                'letter_type': letter_type,
            },
        )
        
        messages.success(request, f'Template for {letter_type} updated successfully.')
    
    except Exception as e:
        logger.exception(f"Error updating letter template: {str(e)}")
        messages.error(request, 'An error occurred while updating the template.')
    
    return redirect('superadmin:all_letter_master')


@login_required
@superadmin_required
@login_required
@superadmin_required
def delete_letter_template(request, template_id):
    """Permanently delete a letter template"""
    if request.method != 'POST':
        return redirect('superadmin:all_letter_master')
    
    from common.pymongo_utils import pymongo_filter, get_mongo_db
    from bson import ObjectId
    
    # Find using PyMongo
    try:
        if isinstance(template_id, str) and len(template_id) == 24:
             query = {'_id': ObjectId(template_id)}
        else:
             query = {'id': template_id}
             
        matches = pymongo_filter(LetterTemplate, query=query)
        if not matches:
             query = {'id': str(template_id)}
             matches = pymongo_filter(LetterTemplate, query=query)
             
        template = matches[0] if matches else None
    except Exception:
        template = None
    
    if not template:
        messages.error(request, 'Template not found.')
        return redirect('superadmin:all_letter_master')
    
    type_ref = getattr(template, 'letter_type', 'Unknown')
    
    try:
        # Use PyMongo for delete
        db = get_mongo_db()
        collection = db[LetterTemplate._meta.db_table]
        
        # Soft delete is cleaner
        if hasattr(template, '_id'):
            collection.update_one({'_id': template._id}, {'$set': {'is_deleted': True, 'deleted_at': timezone.now()}})
        else:
            collection.update_one({'id': template.id}, {'$set': {'is_deleted': True, 'deleted_at': timezone.now()}})
        
        log_activity_event(
            'letter_template.deleted',
            subject_user=None,
            performed_by=request.user,
            metadata={
                'letter_type': type_ref,
            },
        )
    
        messages.success(request, f'Template for {type_ref} deleted successfully.')
    
    except Exception as e:
        logger.exception(f"Error deleting letter template: {str(e)}")
        messages.error(request, 'An error occurred while deleting the template.')
    
    return redirect('superadmin:all_letter_master')


# ========================================
# GENERATE LETTER VIEWS
# ========================================

@login_required
@superadmin_required
def generate_letter_selection(request):
    """Step 1: Select Template and User"""
    
    # Fetch active templates
    # Djongo 1.3.7 issue: filter + order_by causes SQLDecodeError
    # Fix: Fetch list first, then filter/sort in Python
    # Even simpler: Fetch ALL, then filter in python to be ultra-safe
    all_raw_templates = list(LetterTemplate.objects.all())
    templates = [
        t for t in all_raw_templates 
        if not getattr(t, 'is_deleted', False)
    ]
    templates.sort(key=lambda x: x.letter_type)

    
    # Fetch active users (only APPROVED users)
    # Fix: Fetch list first, then sort in Python
    all_raw_users = list(CustomUser.objects.all())
    users = [
        u for u in all_raw_users 
        if u.is_active and getattr(u, 'is_approved', False)
    ]
    users.sort(key=lambda x: (x.first_name or '').lower())
    
    context = {
        'templates': templates,
        'users': users
    }
    return render(request, 'generate_letter_selection.html', context)


@login_required
@superadmin_required
def generate_letter_form(request):
    """Step 2: Render Dynamic Form based on Template Variables"""
    if request.method != 'POST':
        return redirect('superadmin:generate_letter_selection')
    
    template_id = request.POST.get('template_id')
    user_id = request.POST.get('user_id')
    
    if not template_id or not user_id:
        messages.error(request, "Please select both a template and a user.")
        return redirect('superadmin:generate_letter_selection')
    
    try:
        template = LetterTemplate.objects.get(id=template_id)
        user = CustomUser.objects.get(id=user_id)
        
        # Extract variables from template content
        variables = extract_template_variables(template.template_content)
        
        # Helper for special fields
        # Fetch organization choices safely
        try:
             # Djongo issue: filter queries failing. Use Fetch All + Python Filter
             all_orgs = list(OrganisationMaster.objects.all())
             child_orgs = [
                 o.organisation_name for o in all_orgs 
                 if o.org_type == 'child' and o.is_active
             ]
             mother_orgs = [
                 o.organisation_name for o in all_orgs 
                 if o.org_type == 'mother' and o.is_active
             ]
        except Exception as e:
             logger.error(f"Error fetching orgs: {e}")
             child_orgs = []
             mother_orgs = []

        designations = ['Writer', 'Admin', 'Allocator', 'Process', 'Marketing']
        
        # If this is a Joining Letter or Appointment Letter, fetch data from user's Offer Letter
        offer_letter_data = {}
        if template.letter_type in ['joining', 'appointment']:
            try:
                from .models import GeneratedLetter
                # Find user's most recent offer letter
                all_gen_letters = list(GeneratedLetter.objects.all())
                user_offer_letters = [
                    l for l in all_gen_letters 
                    if l.user_id == user.id and l.letter_type == 'offer' and not l.is_deleted
                ]
                if user_offer_letters:
                    # Get the most recent offer letter
                    user_offer_letters.sort(key=lambda x: x.generated_at, reverse=True)
                    offer_letter = user_offer_letters[0]
                    
                    # Parse field_data JSON if available
                    if offer_letter.field_data:
                        offer_letter_data = json.loads(offer_letter.field_data)
                        # Remove fields that should be fresh for joining letter
                        offer_letter_data.pop('issue_date', None)
                        offer_letter_data.pop('letter_id', None)
                        logger.info(f"Found offer letter {offer_letter.letter_id} with {len(offer_letter_data)} fields for user {user.email}")
            except Exception as e:
                logger.error(f"Error fetching offer letter: {e}")
        
        # Classify variables
        auto_filled_fields = []
        manual_fields = []
        
        for var in variables:
            # Special Handling for specific variables
            if var == 'letter_id':
                # Auto-generate Letter ID: LT-YYYYMMDD-XXXX
                val = f"LT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
                auto_filled_fields.append({
                    'name': var,
                    'value': val,
                    'label': 'Letter ID (Auto)',
                    'readonly': True
                })
                continue
                
            if var == 'child_org_name':
                # Check if user has organisation set in profile (ForeignKey relationship)
                user_org = None
                if hasattr(user, 'organisation') and user.organisation:
                    user_org = user.organisation.organisation_name
                elif hasattr(user, 'child_organisation') and user.child_organisation:
                    user_org = user.child_organisation
                
                if user_org:
                    # Organisation is set in profile, auto-fill
                    auto_filled_fields.append({
                        'name': var,
                        'value': user_org,
                        'label': 'Child Organisation (From Profile)'
                    })
                else:
                    # Show dropdown for admin to fill
                    manual_fields.append({
                        'name': var,
                        'label': 'Child Organisation',
                        'type': 'select',
                        'choices': child_orgs
                    })
                continue

            if var == 'mother_org_name':
                # Check if we have a child_org_name to find its parent
                child_org_name = None
                
                # Check offer letter data first
                if offer_letter_data and offer_letter_data.get('child_org_name'):
                    child_org_name = offer_letter_data.get('child_org_name')
                # Then check user profile
                elif hasattr(user, 'organisation') and user.organisation:
                    child_org_name = user.organisation.organisation_name
                elif hasattr(user, 'child_organisation') and user.child_organisation:
                    child_org_name = user.child_organisation
                
                # If we have child org, look up its parent organisation
                if child_org_name:
                    mother_org_name = None
                    for o in all_orgs:
                        if o.organisation_name == child_org_name and o.parent_organisation:
                            mother_org_name = o.parent_organisation.organisation_name
                            break
                    
                    if mother_org_name:
                        auto_filled_fields.append({
                            'name': var,
                            'value': mother_org_name,
                            'label': 'Mother Organisation (From Child Org)'
                        })
                        continue
                
                # Fallback to dropdown
                manual_fields.append({
                    'name': var,
                    'label': 'Mother Organisation',
                    'type': 'select',
                    'choices': mother_orgs
                })
                continue

            if var == 'designation':
                # Check if user has a role set in profile
                user_role = user.role if hasattr(user, 'role') and user.role else None
                if user_role and user_role != 'user':
                    # Role is set and is not generic 'user', auto-fill
                    auto_filled_fields.append({
                        'name': var,
                        'value': user_role.title(),
                        'label': 'Designation (From Profile)'
                    })
                else:
                    # Show dropdown for admin to fill
                    manual_fields.append({
                        'name': var,
                        'label': 'Designation',
                        'type': 'select',
                        'choices': designations
                    })
                continue

            # Department - check profile first
            if var == 'department':
                user_dept = user.department if hasattr(user, 'department') and user.department else None
                if user_dept:
                    # Department is set in profile, auto-fill
                    auto_filled_fields.append({
                        'name': var,
                        'value': user_dept.title(),
                        'label': 'Department (From Profile)'
                    })
                else:
                    # Show dropdown for admin to fill
                    departments = ['Writer', 'Allocator', 'Process', 'Marketing']
                    manual_fields.append({
                        'name': var,
                        'label': 'Department',
                        'type': 'select',
                        'choices': departments
                    })
                continue

            # Reporting Manager dropdown - users with role allocator or admin
            if var == 'reporting_manager':
                try:
                    all_users_for_rm = list(CustomUser.objects.all())
                    reporting_managers = [
                        u.get_full_name() for u in all_users_for_rm 
                        if u.role in ['allocator', 'admin'] and u.is_active
                    ]
                except Exception:
                    reporting_managers = []
                manual_fields.append({
                    'name': var,
                    'label': 'Reporting Manager',
                    'type': 'select',
                    'choices': reporting_managers
                })
                continue

            # Annual CTC - auto-calculate from monthly salary (monthly * 12)
            if var == 'annual_ctc':
                # Check multiple sources for salary
                monthly_sal = None
                
                # 1. Check offer letter data first
                if offer_letter_data:
                    monthly_sal = offer_letter_data.get('monthly_salary') or offer_letter_data.get('salary')
                
                # 2. Check already processed auto_filled_fields
                if not monthly_sal:
                    for field in auto_filled_fields:
                        if field['name'] in ['monthly_salary', 'salary']:
                            monthly_sal = field['value']
                            break
                
                # 3. Check user profile directly (user.salary is a DecimalField)
                if not monthly_sal and hasattr(user, 'salary') and user.salary:
                    monthly_sal = user.salary
                
                if monthly_sal:
                    try:
                        from decimal import Decimal
                        # Handle Decimal, string, or float
                        if isinstance(monthly_sal, Decimal):
                            annual = float(monthly_sal) * 12
                        else:
                            annual = float(str(monthly_sal).replace(',', '')) * 12
                        
                        auto_filled_fields.append({
                            'name': var,
                            'value': f"{annual:.2f}",
                            'label': 'Annual CTC (Auto-Calculated)',
                            'readonly': True
                        })
                        continue
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error calculating CTC: {e}")
                
                # Fallback to manual input
                manual_fields.append({
                    'name': var,
                    'label': 'Annual CTC',
                    'type': 'text'
                })
                continue

            # Special handling for work_location - auto-fill from child org if available
            if var == 'work_location':
                # Check if we have a child_org_name (from profile, offer letter, or already auto-filled)
                child_org_name = None
                
                # Check offer letter data first
                if offer_letter_data and offer_letter_data.get('child_org_name'):
                    child_org_name = offer_letter_data.get('child_org_name')
                # Then check user profile
                elif hasattr(user, 'organisation') and user.organisation:
                    child_org_name = user.organisation.organisation_name
                elif hasattr(user, 'child_organisation') and user.child_organisation:
                    child_org_name = user.child_organisation
                
                # If we have org name, look up its address
                if child_org_name:
                    org_address = None
                    for o in all_orgs:
                        if o.organisation_name == child_org_name and o.address:
                            org_address = o.address
                            break
                    
                    if org_address:
                        auto_filled_fields.append({
                            'name': var,
                            'value': org_address,
                            'label': 'Work Location (From Organisation)'
                        })
                        continue
                
                # Fallback to dropdown
                work_location_choices = [
                    o.address for o in all_orgs 
                    if o.org_type == 'child' and o.is_active and o.address
                ]
                manual_fields.append({
                    'name': var,
                    'label': 'Work Location',
                    'type': 'select',
                    'choices': work_location_choices
                })
                continue

            # Default logic for generic variables
            # First check offer_letter_data (for joining letters from offer letters)
            offer_val = offer_letter_data.get(var) if offer_letter_data else None
            if offer_val:
                auto_filled_fields.append({
                    'name': var,
                    'value': offer_val,
                    'label': var.replace('_', ' ').title() + ' (From Offer Letter)'
                })
                continue
            
            # Then check user profile
            val = get_user_field_value(user, var)
            if val is not None:
                auto_filled_fields.append({
                    'name': var,
                    'value': val,
                    'label': var.replace('_', ' ').title()
                })
            else:
                # Detect date fields by name containing 'date'
                field_type = 'date' if 'date' in var.lower() else 'text'
                manual_fields.append({
                    'name': var,
                    'label': var.replace('_', ' ').title(),
                    'type': field_type
                })
        
        # Build org name to address mapping for JavaScript
        org_address_map = {
            o.organisation_name: o.address or ''
            for o in all_orgs 
            if o.org_type == 'child' and o.is_active
        }
        
        context = {
            'template': template,
            'target_user': user,
            'auto_filled_fields': auto_filled_fields,
            'manual_fields': manual_fields,
            'org_address_map': org_address_map,
        }
        return render(request, 'generate_letter_form.html', context)
        
    except LetterTemplate.DoesNotExist:
        messages.error(request, "Template not found.")
        return redirect('superadmin:generate_letter_selection')
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('superadmin:generate_letter_selection')
    except Exception as e:
        logger.exception(f"Error preparing letter form: {e}")
        messages.error(request, "An error occurred.")
        return redirect('superadmin:generate_letter_selection')


@login_required
@superadmin_required
def generate_letter_preview(request):
    """Step 3: Generate Final Letter with Substitutions and Save to DB"""
    if request.method != 'POST':
        return redirect('superadmin:generate_letter_selection')
        
    template_id = request.POST.get('template_id')
    user_id = request.POST.get('user_id')
    
    try:
        template = LetterTemplate.objects.get(id=template_id)
        target_user = CustomUser.objects.get(id=user_id)
        content = template.template_content
        
        # Get letter_id from form (auto-generated)
        letter_id = request.POST.get('letter_id', f"LT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}")
        
        # Replace variables with form data and collect field values
        variables = extract_template_variables(content)
        field_values = {}  # Store all field values for reuse
        
        for var in variables:
            value = request.POST.get(var, '')
            field_values[var] = value  # Save for JSON storage
            content = content.replace(f'{{{{ {var} }}}}', value)
            content = content.replace(f'{{{{{var}}}}}', value)
        
        # Save to database with field_data JSON
        from .models import GeneratedLetter
        generated_letter = GeneratedLetter.objects.create(
            letter_id=letter_id,
            user=target_user,
            template=template,
            letter_type=template.letter_type,
            rendered_content=content,
            generated_by=request.user,
            field_data=json.dumps(field_values)  # Store as JSON
        )
        
        logger.info(f"Letter {letter_id} generated for user {target_user.email} by {request.user.email}")
            
        context = {
            'final_content': content,
            'template': template,
            'generated_letter': generated_letter,
            'target_user': target_user,
        }
        return render(request, 'generate_letter_preview.html', context)
        
    except Exception as e:
        logger.exception(f"Error generating letter preview: {e}")
        messages.error(request, "Error generating letter.")
        return redirect('superadmin:generate_letter_selection')


@login_required
@superadmin_required
def create_reference(request):
    """Create a new reference entry"""
    if request.method == 'POST':
        try:
            referencing_style = request.POST.get('referencing_style', '').strip()
            used_in = request.POST.get('used_in', '').strip()
            
            # Validation
            if not referencing_style or not used_in:
                messages.error(request, 'All fields are required.')
                return redirect('superadmin:referencing_master')
            
            # Check for existing combination
            all_matching = list(ReferencingMaster.objects.filter(
                referencing_style=referencing_style,
                used_in=used_in
            ))
            
            existing = next(
                (item for item in all_matching if not getattr(item, 'is_deleted', False)),
                None
            )
            
            if existing:
                messages.error(request, f'Reference already exists for {referencing_style} - {used_in}.')
                return redirect('superadmin:referencing_master')
            
            with transaction.atomic():
                reference_obj = ReferencingMaster()
                reference_obj.referencing_style = referencing_style
                reference_obj.used_in = used_in
                reference_obj.created_by = request.user
                reference_obj.created_at = timezone.now()
                reference_obj.save()
                
                log_activity_event(
                    'reference.created_at',
                    subject_user=None,
                    performed_by=request.user,
                    metadata={
                        'reference_id': str(reference_obj.id),
                        'referencing_style': referencing_style,
                        'used_in': used_in,
                    },
                )
                
                logger.info(f"Reference created for {referencing_style} - {used_in} by {request.user.email}")
                messages.success(request, f'Reference for {referencing_style} - {used_in} created successfully!')
            
            return redirect('superadmin:referencing_master')
            
        except Exception as e:
            logger.exception(f"Error creating reference: {str(e)}")
            messages.error(request, 'An error occurred while creating the reference.')
            return redirect('superadmin:referencing_master')
    
    return redirect('superadmin:referencing_master')


@login_required
@superadmin_required
def edit_reference(request, reference_id):
    """Update an existing reference entry"""
    if request.method != 'POST':
        return redirect('superadmin:referencing_master')
    
    reference_obj = _find_reference_by_id(reference_id)
    
    if not reference_obj:
        messages.error(request, 'Reference entry not found.')
        return redirect('superadmin:referencing_master')
    
    try:
        referencing_style = request.POST.get('referencing_style', '').strip()
        used_in = request.POST.get('used_in', '').strip()
        
        if not referencing_style or not used_in:
            messages.error(request, 'All fields are required.')
            return redirect('superadmin:referencing_master')
        
        # Check for duplicate combination (excluding current record)
        all_matching = list(ReferencingMaster.objects.filter(
            referencing_style=referencing_style,
            used_in=used_in
        ))
        
        existing = next(
            (item for item in all_matching 
             if str(item.id) != str(reference_id) and not getattr(item, 'is_deleted', False)),
            None
        )
        
        if existing:
            messages.error(request, f'Reference already exists for {referencing_style} - {used_in}.')
            return redirect('superadmin:referencing_master')
        
        with transaction.atomic():
            reference_obj.referencing_style = referencing_style
            reference_obj.used_in = used_in
            reference_obj.updated_by = request.user
            reference_obj.updated_at = timezone.now()
            reference_obj.save()
            
            log_activity_event(
                'reference.updated_at',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'reference_id': str(reference_obj.id),
                    'referencing_style': referencing_style,
                    'used_in': used_in,
                },
            )
        
        messages.success(request, f'Reference for {referencing_style} - {used_in} updated successfully.')
    
    except Exception as e:
        logger.exception(f"Error updating reference: {str(e)}")
        messages.error(request, 'An error occurred while updating the reference.')
    
    return redirect('superadmin:referencing_master')


@login_required
@superadmin_required
def delete_reference(request, reference_id):
    """Delete a reference entry"""
    if request.method != 'POST':
        return redirect('superadmin:referencing_master')
    
    reference_obj = _find_reference_by_id(reference_id)
    
    if not reference_obj:
        messages.error(request, 'Reference entry not found.')
        return redirect('superadmin:referencing_master')
    
    reference_id_ref = str(reference_obj.id)
    referencing_style_ref = reference_obj.referencing_style
    used_in_ref = reference_obj.used_in
    
    try:
        with transaction.atomic():
            reference_obj.delete()
            
            log_activity_event(
                'reference.deleted',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'reference_id': reference_id_ref,
                    'referencing_style': referencing_style_ref,
                    'used_in': used_in_ref,
                },
            )
        
        messages.success(request, f'Reference for {referencing_style_ref} - {used_in_ref} deleted successfully.')
    
    except Exception as e:
        logger.exception(f"Error deleting reference: {str(e)}")
        messages.error(request, 'An error occurred while deleting the reference.')
    
    return redirect('superadmin:referencing_master')


def _find_reference_by_id(reference_id):
    """Helper function to find reference by ID (supports ObjectId and int)"""
    if not reference_id:
        return None
    
    candidates = []
    try:
        candidates = list(ReferencingMaster.objects.filter(id=reference_id))
    except Exception:
        candidates = []
    
    if not candidates and isinstance(reference_id, str) and reference_id.isdigit():
        try:
            candidates = list(ReferencingMaster.objects.filter(id=int(reference_id)))
        except Exception:
            candidates = []
    
    if not candidates:
        try:
            object_id = ObjectId(str(reference_id))
            candidates = list(ReferencingMaster.objects.filter(id=object_id))
        except (InvalidId, Exception):
            candidates = []
    
    return next(
        (item for item in candidates if not getattr(item, 'is_deleted', False)),
        None
    )



# This is continuation of views.py - ACADEMIC WRITING MASTER section
# Copy this after Referencing Master views

# ========================================
# ACADEMIC WRITING MASTER VIEWS
# ========================================

@login_required
@superadmin_required
def academic_writing_master(request):
    """Academic Writing Master - List all writing styles"""
    from common.pymongo_utils import pymongo_filter
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        raw_writing = pymongo_filter(AcademicWritingMaster, sort=[('created_at', -1)])
        writings = [
            writing for writing in raw_writing
            if not getattr(writing, 'is_deleted', False)
        ]
        context = {
            'writings': writings,
            'total_writings': len(writings),
        }
        return render(request, 'academic_writing_master.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading academic writing master: {str(e)}")
        messages.error(request, 'Error loading writing styles.')
        return render(request, 'academic_writing_master.html', {'writings': [], 'total_writings': 0})


@login_required
@superadmin_required
def create_writing(request):
    """Create a new writing style entry"""
    if request.method == 'POST':
        try:
            writing_style = request.POST.get('writing_style', '').strip()
            
            # Validation
            if not writing_style:
                messages.error(request, 'Writing style is required.')
                return redirect('superadmin:academic_writing_master')
            
            # Check for existing writing style
            all_matching = list(AcademicWritingMaster.objects.filter(
                writing_style=writing_style
            ))
            
            existing = next(
                (item for item in all_matching if not getattr(item, 'is_deleted', False)),
                None
            )
            
            if existing:
                messages.error(request, f'Writing style "{writing_style}" already exists.')
                return redirect('superadmin:academic_writing_master')
            
            with transaction.atomic():
                writing_obj = AcademicWritingMaster()
                writing_obj.writing_style = writing_style
                writing_obj.created_by = request.user
                writing_obj.created_at = timezone.now()
                writing_obj.save()
                
                log_activity_event(
                    'writing.created_at',
                    subject_user=None,
                    performed_by=request.user,
                    metadata={
                        'writing_id': str(writing_obj.id),
                        'writing_style': writing_style,
                    },
                )
                
                logger.info(f"Writing style '{writing_style}' created by {request.user.email}")
                messages.success(request, f'Writing style "{writing_style}" created successfully!')
            
            return redirect('superadmin:academic_writing_master')
            
        except Exception as e:
            logger.exception(f"Error creating writing style: {str(e)}")
            messages.error(request, 'An error occurred while creating the writing style.')
            return redirect('superadmin:academic_writing_master')
    
    return redirect('superadmin:academic_writing_master')


@login_required
@superadmin_required
def edit_writing(request, writing_id):
    """Update an existing writing style entry"""
    if request.method != 'POST':
        return redirect('superadmin:academic_writing_master')
    
    writing_obj = _find_writing_by_id(writing_id)
    
    if not writing_obj:
        messages.error(request, 'Writing style not found.')
        return redirect('superadmin:academic_writing_master')
    
    try:
        writing_style = request.POST.get('writing_style', '').strip()
        
        if not writing_style:
            messages.error(request, 'Writing style is required.')
            return redirect('superadmin:academic_writing_master')
        
        # Check for duplicate (excluding current record)
        all_matching = list(AcademicWritingMaster.objects.filter(
            writing_style=writing_style
        ))
        
        existing = next(
            (item for item in all_matching 
             if str(item.id) != str(writing_id) and not getattr(item, 'is_deleted', False)),
            None
        )
        
        if existing:
            messages.error(request, f'Writing style "{writing_style}" already exists.')
            return redirect('superadmin:academic_writing_master')
        
        with transaction.atomic():
            writing_obj.writing_style = writing_style
            writing_obj.updated_by = request.user
            writing_obj.updated_at = timezone.now()
            writing_obj.save()
            
            log_activity_event(
                'writing.updated_at',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'writing_id': str(writing_obj.id),
                    'writing_style': writing_style,
                },
            )
        
        messages.success(request, f'Writing style "{writing_style}" updated successfully.')
    
    except Exception as e:
        logger.exception(f"Error updating writing style: {str(e)}")
        messages.error(request, 'An error occurred while updating the writing style.')
    
    return redirect('superadmin:academic_writing_master')


@login_required
@superadmin_required
def delete_writing(request, writing_id):
    """Delete a writing style entry"""
    if request.method != 'POST':
        return redirect('superadmin:academic_writing_master')
    
    writing_obj = _find_writing_by_id(writing_id)
    
    if not writing_obj:
        messages.error(request, 'Writing style not found.')
        return redirect('superadmin:academic_writing_master')
    
    writing_id_ref = str(writing_obj.id)
    writing_style_ref = writing_obj.writing_style
    
    try:
        with transaction.atomic():
            writing_obj.delete()
            
            log_activity_event(
                'writing.deleted',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'writing_id': writing_id_ref,
                    'writing_style': writing_style_ref,
                },
            )
        
        messages.success(request, f'Writing style "{writing_style_ref}" deleted successfully.')
    
    except Exception as e:
        logger.exception(f"Error deleting writing style: {str(e)}")
        messages.error(request, 'An error occurred while deleting the writing style.')
    
    return redirect('superadmin:academic_writing_master')


def _find_writing_by_id(writing_id):
    """Helper function to find writing by ID (supports ObjectId and int)"""
    if not writing_id:
        return None
    
    candidates = []
    try:
        candidates = list(AcademicWritingMaster.objects.filter(id=writing_id))
    except Exception:
        candidates = []
    
    if not candidates and isinstance(writing_id, str) and writing_id.isdigit():
        try:
            candidates = list(AcademicWritingMaster.objects.filter(id=int(writing_id)))
        except Exception:
            candidates = []
    
    if not candidates:
        try:
            object_id = ObjectId(str(writing_id))
            candidates = list(AcademicWritingMaster.objects.filter(id=object_id))
        except (InvalidId, Exception):
            candidates = []
    
    return next(
        (item for item in candidates if not getattr(item, 'is_deleted', False)),
        None
    )

@login_required
@superadmin_required
def project_group_master(request):
    """Project Group Master - List all project groups (Djongo-safe)"""
    from common.pymongo_utils import pymongo_filter
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        raw_groups = pymongo_filter(ProjectGroupMaster, sort=[('created_at', -1)])
        project_groups = [
            group for group in raw_groups
            if not getattr(group, 'is_deleted', False)
        ]
        context = {
            'project_groups': project_groups,
            'total_groups': len(project_groups),
        }
        return render(request, 'project_group_master.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading project group master: {str(e)}")
        messages.error(request, 'Error loading project groups.')
        return render(request, 'project_group_master.html', {
            'project_groups': [],
            'total_groups': 0
        })


@login_required
@superadmin_required
def create_project_group(request):
    """Create a new project group (Djongo-safe)"""
    if request.method == 'POST':
        try:
            project_group_name = request.POST.get('project_group_name', '').strip()
            project_group_prefix = request.POST.get('project_group_prefix', '').strip().upper()
            
            # Validation
            if not project_group_name or not project_group_prefix:
                messages.error(request, 'All fields are required.')
                return redirect('superadmin:project_group_master')
            
            # Validate prefix format (alphanumeric only)
            if not project_group_prefix.isalnum():
                messages.error(request, 'Project Group Prefix must contain only letters and numbers.')
                return redirect('superadmin:project_group_master')
            
            # Check for existing prefix (Djongo-safe approach)
            all_matching = list(ProjectGroupMaster.objects.filter(
                project_group_prefix=project_group_prefix
            ))
            
            # Filter in Python to avoid Djongo NOT operator issues
            existing = next(
                (item for item in all_matching if not getattr(item, 'is_deleted', False)),
                None
            )
            
            if existing:
                messages.error(request, f'Project Group with prefix "{project_group_prefix}" already exists.')
                return redirect('superadmin:project_group_master')
            
            with transaction.atomic():
                group = ProjectGroupMaster()
                group.project_group_name = project_group_name
                group.project_group_prefix = project_group_prefix
                group.created_by = request.user
                group.created_at = timezone.now()
                group.save()
                
                log_activity_event(
                    'project_group.created_at',
                    subject_user=None,
                    performed_by=request.user,
                    metadata={
                        'project_group_id': str(group.id),
                        'project_group_name': project_group_name,
                        'project_group_prefix': project_group_prefix,
                    },
                )
                
                logger.info(f"Project Group '{project_group_name}' created by {request.user.email}")
                messages.success(request, f'Project Group "{project_group_name}" created successfully!')
            
            return redirect('superadmin:project_group_master')
            
        except Exception as e:
            logger.exception(f"Error creating project group: {str(e)}")
            messages.error(request, 'An error occurred while creating the project group.')
            return redirect('superadmin:project_group_master')
    
    return redirect('superadmin:project_group_master')


@login_required
@superadmin_required
def edit_project_group(request, group_id):
    """Update an existing project group (Djongo-safe)"""
    if request.method != 'POST':
        return redirect('superadmin:project_group_master')
    
    # Djongo-safe lookup
    all_groups = list(ProjectGroupMaster.objects.filter(id=group_id))
    group = next(
        (item for item in all_groups if not getattr(item, 'is_deleted', False)),
        None
    )
    
    if not group:
        messages.error(request, 'Project Group not found.')
        return redirect('superadmin:project_group_master')
    
    try:
        project_group_name = request.POST.get('project_group_name', '').strip()
        project_group_prefix = request.POST.get('project_group_prefix', '').strip().upper()
        
        if not project_group_name or not project_group_prefix:
            messages.error(request, 'All fields are required.')
            return redirect('superadmin:project_group_master')
        
        # Validate prefix format
        if not project_group_prefix.isalnum():
            messages.error(request, 'Project Group Prefix must contain only letters and numbers.')
            return redirect('superadmin:project_group_master')
        
        # Check for duplicate prefix (excluding current record) - Djongo-safe
        all_matching = list(ProjectGroupMaster.objects.filter(
            project_group_prefix=project_group_prefix
        ))
        
        # Filter in Python to avoid Djongo issues
        existing = next(
            (item for item in all_matching 
             if item.id != group_id and not getattr(item, 'is_deleted', False)),
            None
        )
        
        if existing:
            messages.error(request, f'Project Group with prefix "{project_group_prefix}" already exists.')
            return redirect('superadmin:project_group_master')
        
        with transaction.atomic():
            group.project_group_name = project_group_name
            group.project_group_prefix = project_group_prefix
            group.updated_by = request.user
            group.updated_at = timezone.now()
            group.save()
            
            log_activity_event(
                'project_group.updated_at',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'project_group_id': str(group.id),
                    'project_group_name': project_group_name,
                    'project_group_prefix': project_group_prefix,
                },
            )
        
        messages.success(request, f'Project Group "{project_group_name}" updated successfully.')
    except Exception as e:
        logger.exception(f"Error updating project group: {str(e)}")
        messages.error(request, 'An error occurred while updating the project group.')
    
    return redirect('superadmin:project_group_master')


@login_required
@superadmin_required
def delete_project_group(request, group_id):
    """Delete a project group (Djongo-safe)"""
    if request.method != 'POST':
        return redirect('superadmin:project_group_master')
    
    # Safe lookup
    group = None
    try:
        group = ProjectGroupMaster.objects.get(id=group_id)
    except ProjectGroupMaster.DoesNotExist:
        messages.error(request, 'Project Group not found.')
        return redirect('superadmin:project_group_master')
    
    group_id_ref = str(group.id)
    group_name_ref = group.project_group_name
    group_prefix_ref = group.project_group_prefix
    
    try:
        with transaction.atomic():
            group.delete()
            
            log_activity_event(
                'project_group.deleted',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'project_group_id': group_id_ref,
                    'project_group_name': group_name_ref,
                    'project_group_prefix': group_prefix_ref,
                },
            )
        
        messages.success(request, f'Project Group "{group_name_ref}" deleted successfully.')
    except Exception as e:
        logger.exception(f"Error deleting project group: {str(e)}")
        messages.error(request, 'An error occurred while deleting the project group.')
    
    return redirect('superadmin:project_group_master')



@login_required
@superadmin_required
def add_user(request):
    """Add a new user directly by superadmin"""
    if request.method == 'POST':
        try:
            full_name = request.POST.get('full_name', '').strip()
            email = request.POST.get('email', '').strip().lower()
            whatsapp_number = request.POST.get('whatsapp_number', '').strip()
            role = request.POST.get('role', 'user')
            password1 = request.POST.get('password1', '')
            password2 = request.POST.get('password2', '')
            
            errors = []
            
            # Validation
            if not all([full_name, email, whatsapp_number, password1, password2]):
                errors.append('All fields are required.')
            
            # Split full name
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            if not first_name:
                errors.append('Please enter a valid full name.')
            
            # Email validation
            import re
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                errors.append('Please enter a valid email address.')
            
            # Check if email already exists
            if CustomUser.objects.filter(email=email).exists():
                errors.append('Email is already registered.')
            
            # WhatsApp validation
            if not whatsapp_number.isdigit() or len(whatsapp_number) != 10:
                errors.append('WhatsApp number must be exactly 10 digits.')
            
            # Role validation
            valid_roles = [choice[0] for choice in CustomUser.ROLE_CHOICES]
            if role not in valid_roles:
                errors.append('Invalid role selected.')
            
            # Password validation
            if len(password1) < 8:
                errors.append('Password must be at least 8 characters long.')
            
            if password1 != password2:
                errors.append('Passwords do not match.')
            
            # Return errors
            if errors:
                for error in errors:
                    messages.error(request, error)
                return redirect('manage_users')
            
            # Create user
            with transaction.atomic():
                # Generate unique username
                username = email.split('@')[0]
                base_username = username
                counter = 1
                
                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Create timestamp
                now = timezone.now()
                
                # Create user
                user = CustomUser.objects.create(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    whatsapp_number=whatsapp_number,
                    phone=whatsapp_number,  # Auto-fill phone
                    role=role,
                    department=role,  # Set department same as role
                    is_approved=True,  # Auto-approve
                    approval_status='approved',
                    is_active=True,
                    registered_at=now,
                    approved_by=request.user,
                    approved_at=now,
                    role_assigned_at=now,
                )
                user.set_password(password1)
                
                # Generate employee ID
                user.employee_id = user.generate_employee_id()
                user.employee_id_generated_at = now
                user.employee_id_assigned_at = now
                
                user.save()
                
                # Log activity
                log_activity_event(
                    'user.created_by_superadmin',
                    subject_user=user,
                    performed_by=request.user,
                    metadata={
                        'role': role,
                        'employee_id': user.employee_id,
                        'created_via': 'add_user_form'
                    },
                )
                
                log_activity_event(
                    'user.approved_at',
                    subject_user=user,
                    performed_by=request.user,
                    metadata={'auto_approved': True},
                )
                
                log_activity_event(
                    'employee_id.generated_at',
                    subject_user=user,
                    metadata={
                        'employee_id': user.employee_id,
                        'source': 'add_user_form',
                        'performed_by': 'superadmin',
                    },
                )
                
                logger.info(f"User created by superadmin: {user.email} with role {role}")
                messages.success(request, f'User "{user.get_full_name()}" created successfully with Employee ID: {user.employee_id}')
            
            return redirect('manage_users')
            
        except Exception as e:
            logger.exception(f"Error creating user: {str(e)}")
            messages.error(request, 'An error occurred while creating the user.')
            return redirect('superadmin:manage_users')
    
    return redirect('superadmin:manage_users')

# superadminpanel/views.py - Add this view function

@login_required
@superadmin_required
def change_user_password(request, user_id):
    """Change password for any user by superadmin with comprehensive validation"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('superadmin:manage_users')
    
    # Get the target user
    try:
        target_user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('manage_users')
    
    # Get form data
    new_password = request.POST.get('new_password', '').strip()
    copy_confirmed = request.POST.get('copy_confirmed', 'false').lower() == 'true'
    
    logger.info(f"Password change attempt (generated) for user: {target_user.email}")
    
    if not new_password:
        messages.error(request, 'Generated password is missing. Please try again.')
        return redirect('manage_users')
    
    if len(new_password) < 8:
        messages.error(request, 'Generated password must be at least 8 characters long.')
        return redirect('manage_users')
    
    if not copy_confirmed:
        messages.error(request, 'Please copy the generated password before saving.')
        return redirect('manage_users')
    
    # All validations passed - change the password
    try:
        with transaction.atomic():
            change_timestamp = timezone.now()
            
            target_user.set_password(new_password)
            target_user.password_changed_at = change_timestamp
            target_user.save()
            
            logger.info(f"Password successfully changed for user: {target_user.email}")
            
            log_activity_event(
                'user.password_changed_at',
                subject_user=target_user,
                performed_by=request.user,
                metadata={
                    'changed_by_superadmin': True,
                    'superadmin_email': request.user.email,
                    'superadmin_name': request.user.get_full_name(),
                    'initiated_from': 'manage_users',
                    'target_user_email': target_user.email,
                    'timestamp': change_timestamp.isoformat(),
                },
            )
            
            messages.success(
                request,
                f'Password changed successfully for <strong>{target_user.get_full_name()}</strong>. '
                f'Share the copied password with the user.'
            )
            
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                
                send_mail(
                    subject='Password Changed - CRM System',
                    message=f'''
Dear {target_user.get_full_name()},

Your password has been reset by the system administrator.

If you did not request this change, please contact the administrator immediately.

Changed by: {request.user.get_full_name()}
Time: {change_timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Best regards,
CRM System Team
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[target_user.email],
                    fail_silently=True,
                )
                logger.info(f"Password change notification email sent to {target_user.email}")
            except Exception as email_error:
                logger.warning(f"Failed to send password change email: {str(email_error)}")
    
    except Exception as e:
        logger.exception(f"Error changing password for user {user_id}: {str(e)}")
        messages.error(
            request,
            f' An unexpected error occurred while changing the password: {str(e)}. '
            'Please try again or contact technical support.'
        )
    
    return redirect('superadmin:manage_users')


# ========================================
# SPECIALISATION MASTER VIEWS
# ========================================
@login_required
@superadmin_required
def specialisation_master(request):
    """Specialisation Master - List all specialisations"""
    from common.pymongo_utils import pymongo_filter
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        raw_specialisations = pymongo_filter(SpecialisationMaster, sort=[('specialisation_name', 1)])
        specialisations = [
            specialisation for specialisation in raw_specialisations
            if not getattr(specialisation, 'is_deleted', False)
        ]
        context = {
            'specialisations': specialisations,
            'total_specialisations': len(specialisations),
        }
        return render(request, 'specialisation_master.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading specialisation master: {str(e)}")
        messages.error(request, 'Error loading specialisations.')
        return render(request, 'specialisation_master.html', {'specialisations': [], 'total_specialisations': 0})

@login_required
@superadmin_required
def create_specialisation(request):
    """Create a new specialisation entry"""
    if request.method == 'POST':
        try:
            specialisation_name = request.POST.get('specialisation_name', '').strip()
            
            # Validation
            if not specialisation_name:
                messages.error(request, 'Specialisation name is required.')
                return redirect('superadmin:specialisation_master')
            
            # Check for existing specialisation
            all_matching = list(SpecialisationMaster.objects.filter(
                specialisation_name=specialisation_name
            ))
            
            existing = next(
                (item for item in all_matching if not getattr(item, 'is_deleted', False)),
                None
            )
            
            if existing:
                messages.error(request, f'Specialisation "{specialisation_name}" already exists.')
                return redirect('superadmin:specialisation_master')
            
            with transaction.atomic():
                specialisation_obj = SpecialisationMaster()
                specialisation_obj.specialisation_name = specialisation_name
                specialisation_obj.created_by = request.user
                specialisation_obj.created_at = timezone.now()
                specialisation_obj.save()
                
                log_activity_event(
                    'specialisation.created_at',
                    subject_user=None,
                    performed_by=request.user,
                    metadata={
                        'specialisation_id': str(specialisation_obj.id),
                        'specialisation_name': specialisation_name,
                    },
                )
                
                logger.info(f"Specialisation '{specialisation_name}' created by {request.user.email}")
                messages.success(request, f'Specialisation "{specialisation_name}" created successfully!')
            
            return redirect('superadmin:specialisation_master')
            
        except Exception as e:
            logger.exception(f"Error creating specialisation: {str(e)}")
            messages.error(request, 'An error occurred while creating the specialisation.')
            return redirect('superadmin:specialisation_master')
    
    return redirect('superadmin:specialisation_master')

@login_required
@superadmin_required
def edit_specialisation(request, specialisation_id):
    """Update an existing specialisation entry"""
    if request.method != 'POST':
        return redirect('superadmin:specialisation_master')
    
    specialisation_obj = _find_specialisation_by_id(specialisation_id)
    
    if not specialisation_obj:
        messages.error(request, 'Specialisation not found.')
        return redirect('superadmin:specialisation_master')
    
    try:
        specialisation_name = request.POST.get('specialisation_name', '').strip()
        
        if not specialisation_name:
            messages.error(request, 'Specialisation name is required.')
            return redirect('superadmin:specialisation_master')
        
        # Check for duplicate (excluding current record)
        all_matching = list(SpecialisationMaster.objects.filter(
            specialisation_name=specialisation_name
        ))
        
        existing = next(
            (item for item in all_matching 
             if str(item.id) != str(specialisation_id) and not getattr(item, 'is_deleted', False)),
            None
        )
        
        if existing:
            messages.error(request, f'Specialisation "{specialisation_name}" already exists.')
            return redirect('superadmin:specialisation_master')
        
        with transaction.atomic():
            specialisation_obj.specialisation_name = specialisation_name
            specialisation_obj.updated_by = request.user
            specialisation_obj.updated_at = timezone.now()
            specialisation_obj.save()
            
            log_activity_event(
                'specialisation.updated_at',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'specialisation_id': str(specialisation_obj.id),
                    'specialisation_name': specialisation_name,
                },
            )
        
        messages.success(request, f'Specialisation "{specialisation_name}" updated successfully.')
    
    except Exception as e:
        logger.exception(f"Error updating specialisation: {str(e)}")
        messages.error(request, 'An error occurred while updating the specialisation.')
    
    return redirect('superadmin:specialisation_master')

@login_required
@superadmin_required
def delete_specialisation(request, specialisation_id):
    """Delete a specialisation entry"""
    if request.method != 'POST':
        return redirect('superadmin:specialisation_master')
    
    specialisation_obj = _find_specialisation_by_id(specialisation_id)
    
    if not specialisation_obj:
        messages.error(request, 'Specialisation not found.')
        return redirect('superadmin:specialisation_master')
    
    specialisation_id_ref = str(specialisation_obj.id)
    specialisation_name_ref = specialisation_obj.specialisation_name
    
    try:
        with transaction.atomic():
            specialisation_obj.delete()
            
            log_activity_event(
                'specialisation.deleted',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'specialisation_id': specialisation_id_ref,
                    'specialisation_name': specialisation_name_ref,
                },
            )
        
        messages.success(request, f'Specialisation "{specialisation_name_ref}" deleted successfully.')
    
    except Exception as e:
        logger.exception(f"Error deleting specialisation: {str(e)}")
        messages.error(request, 'An error occurred while deleting the specialisation.')
    
    return redirect('superadmin:specialisation_master')

def _find_specialisation_by_id(specialisation_id):
    """Helper function to find specialisation by ID (supports ObjectId and int)"""
    if not specialisation_id:
        return None
    
    candidates = []
    try:
        candidates = list(SpecialisationMaster.objects.filter(id=specialisation_id))
    except Exception:
        candidates = []
    
    if not candidates and isinstance(specialisation_id, str) and specialisation_id.isdigit():
        try:
            candidates = list(SpecialisationMaster.objects.filter(id=int(specialisation_id)))
        except Exception:
            candidates = []
    
    if not candidates:
        try:
            object_id = ObjectId(str(specialisation_id))
            candidates = list(SpecialisationMaster.objects.filter(id=object_id))
        except (InvalidId, Exception):
            candidates = []
    
    return next(
        (item for item in candidates if not getattr(item, 'is_deleted', False)),
        None
    )

@login_required
@superadmin_required
def update_user_specialisations(request, user_id):
    """Update user specialisations"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('superadmin:manage_users')
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    # Check admin restrictions
    if request.user.role == 'admin' and user.role in ['superadmin', 'admin']:
        messages.error(request, 'You do not have permission to manage Super Admin or Admin accounts.')
        return redirect('manage_users')
    
    # Check if user is writer
    if user.role != 'writer':
        messages.error(request, 'Specialisations can only be updated for Writer role.')
        return redirect('superadmin:manage_users')
    
    try:
        specialisation_ids = request.POST.getlist('specialisations')
        
        # Clear existing specialisations
        user.specialisations.clear()
        
        # Add new specialisations
        if specialisation_ids:
            specialisations = _filter_not_deleted(
                SpecialisationMaster.objects.filter(id__in=specialisation_ids)
            )
            user.specialisations.set(specialisations)
        
        logger.info("User %s specialisations updated by %s", user.email, request.user.email)
        
        log_activity_event(
            'manage_user.specialisations_updated_at',
            subject_user=user,
            performed_by=request.user,
            metadata={
                'specialisation_ids': specialisation_ids,
                'count': len(specialisation_ids)
            },
        )
        
        messages.success(request, f'Specialisations updated successfully for {user.get_full_name()}.')
    
    except Exception as e:
        logger.exception(f"Error updating specialisations: {str(e)}")
        messages.error(request, 'An error occurred while updating specialisations.')
    
    return redirect('superadmin:manage_users')


# ========================================
# ORGANISATION MASTER VIEWS
# ========================================

@login_required
@superadmin_required
def organisation_master(request):
    """Organisation Master - List all organisations"""
    from common.pymongo_utils import pymongo_filter
    try:
        # Use PyMongo to bypass broken ORM SQL parsing
        raw_organisations = pymongo_filter(OrganisationMaster, sort=[('organisation_name', 1)])
        organisations = [
            org for org in raw_organisations
            if not getattr(org, 'is_deleted', False)
        ]
        
        # Get mother organisations for the dropdown
        mother_organisations = [org for org in organisations if org.org_type == 'mother']
        
        context = {
            'organisations': organisations,
            'mother_organisations': mother_organisations,
            'total_organisations': len(organisations),
        }
        return render(request, 'organisation_master.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading organisation master: {str(e)}")
        messages.error(request, 'Error loading organisations.')
        return render(request, 'organisation_master.html', {
            'organisations': [],
            'mother_organisations': [],
            'total_organisations': 0
        })


@login_required
@superadmin_required
@login_required
@superadmin_required
def create_organisation(request):
    """Create a new organisation"""
    if request.method == 'POST':
        try:
            from common.pymongo_utils import pymongo_filter, get_mongo_db
            
            organisation_code = request.POST.get('organisation_code', '').strip()
            organisation_name = request.POST.get('organisation_name', '').strip()
            email = request.POST.get('email', '').strip()
            address = request.POST.get('address', '').strip()
            org_type = request.POST.get('org_type', 'mother').strip()
            parent_org_name = request.POST.get('parent_organisation', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            
            if not organisation_code or not organisation_name:
                messages.error(request, 'Organisation code and name are required.')
                return redirect('superadmin:organisation_master')
            
            # Check for existing organisation using PyMongo
            existing_query = {
                'organisation_code': {'$regex': f'^{organisation_code}$', '$options': 'i'},
                'is_deleted': False
            }
            existing = pymongo_filter(OrganisationMaster, query=existing_query)
            
            if existing:
                messages.error(request, f'Organisation with code "{organisation_code}" already exists.')
                return redirect('superadmin:organisation_master')
            
            # Get parent organisation ID if child type
            parent_org_id = None
            if org_type == 'child' and parent_org_name:
                parent_query = {
                    'organisation_name': parent_org_name,
                    'is_deleted': False
                }
                parents = pymongo_filter(OrganisationMaster, query=parent_query)
                if parents:
                    parent_org_id = parents[0].id
                else:
                    messages.error(request, 'Selected parent organisation not found.')
                    return redirect('superadmin:organisation_master')
            
            # Use direct MongoDB insertion to bypass ORM problems
            db = get_mongo_db()
            collection = db[OrganisationMaster._meta.db_table]
            
            new_org = {
                'organisation_code': organisation_code,
                'organisation_name': organisation_name,
                'email': email if email else None,
                'address': address if address else None,
                'org_type': org_type,
                'parent_organisation_id': parent_org_id,
                'is_active': is_active,
                'created_by_id': request.user.id,
                'created_at': timezone.now(),
                'updated_at': timezone.now(),
                'is_deleted': False
            }
            
            result = collection.insert_one(new_org)
            new_org_id = result.inserted_id
            
            # Update the ID field to match Django's expectation (often needed for consistency)
            collection.update_one({'_id': new_org_id}, {'$set': {'id': new_org_id}})
            
            log_activity_event(
                'organisation.created',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'organisation_code': organisation_code,
                    'organisation_name': organisation_name,
                    'org_type': org_type,
                },
            )
            
            messages.success(request, f'Organisation "{organisation_name}" created successfully!')
            
            return redirect('superadmin:organisation_master')
            
        except Exception as e:
            logger.exception(f"Error creating organisation: {str(e)}")
            messages.error(request, 'An error occurred while creating the organisation.')
            return redirect('superadmin:organisation_master')
    
    return redirect('superadmin:organisation_master')


@login_required
@superadmin_required
@login_required
@superadmin_required
def edit_organisation(request, org_id):
    """Update an existing organisation"""
    if request.method != 'POST':
        return redirect('superadmin:organisation_master')
    
    from common.pymongo_utils import pymongo_filter, pymongo_update, get_mongo_db
    from bson import ObjectId
    
    # Find organisation by ID using PyMongo
    try:
        # Try finding by ObjectId first, usually passed as string
        if isinstance(org_id, str) and len(org_id) == 24:
             query = {'_id': ObjectId(org_id), 'is_deleted': False}
        else:
             # Fallback for integer IDs if migrated from SQL
             query = {'id': org_id, 'is_deleted': False}
             
        org_matches = pymongo_filter(OrganisationMaster, query=query)
        if not org_matches:
             # Try fallback to string ID in 'id' field
             query = {'id': str(org_id), 'is_deleted': False}
             org_matches = pymongo_filter(OrganisationMaster, query=query)
             
        org = org_matches[0] if org_matches else None
    except Exception:
        org = None

    if not org:
        messages.error(request, 'Organisation not found.')
        return redirect('superadmin:organisation_master')
    
    try:
        organisation_code = request.POST.get('organisation_code', '').strip()
        organisation_name = request.POST.get('organisation_name', '').strip()
        email = request.POST.get('email', '').strip()
        address = request.POST.get('address', '').strip()
        org_type = request.POST.get('org_type', 'mother').strip()
        parent_org_name = request.POST.get('parent_organisation', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not organisation_code or not organisation_name:
            messages.error(request, 'Organisation code and name are required.')
            return redirect('superadmin:organisation_master')
        
        # Check for duplicate code (excluding current record)
        # Using PyMongo for check
        existing_query = {
            'organisation_code': {'$regex': f'^{organisation_code}$', '$options': 'i'},
            'id': {'$ne': org.id}, # Exclude current
            'is_deleted': False
        }
        existing = pymongo_filter(OrganisationMaster, query=existing_query)
        
        if existing:
            messages.error(request, f'Organisation with code "{organisation_code}" already exists.')
            return redirect('superadmin:organisation_master')
        
        # Get parent organisation ID if child type
        parent_org_id = None
        if org_type == 'child' and parent_org_name:
            parent_query = {
                'organisation_name': parent_org_name,
                'is_deleted': False
            }
            parents = pymongo_filter(OrganisationMaster, query=parent_query)
            if parents:
                parent_org_id = parents[0].id
        
        # Update using direct MongoDB update
        db = get_mongo_db()
        collection = db[OrganisationMaster._meta.db_table]
        
        update_fields = {
            'organisation_code': organisation_code,
            'organisation_name': organisation_name,
            'email': email if email else None,
            'address': address if address else None,
            'org_type': org_type,
            'parent_organisation_id': parent_org_id,
            'is_active': is_active,
            'updated_by_id': request.user.id,
            'updated_at': timezone.now()
        }
        
        # Update by _id if possible, or id field
        if hasattr(org, '_id'):
            collection.update_one({'_id': org._id}, {'$set': update_fields})
        else:
            collection.update_one({'id': org.id}, {'$set': update_fields})
            
        log_activity_event(
            'organisation.updated',
            subject_user=None,
            performed_by=request.user,
            metadata={
                'organisation_code': organisation_code,
                'organisation_name': organisation_name,
            },
        )
        
        messages.success(request, f'Organisation "{organisation_name}" updated successfully.')
    except Exception as e:
        logger.exception(f"Error updating organisation: {str(e)}")
        messages.error(request, 'An error occurred while updating the organisation.')
    
    return redirect('superadmin:organisation_master')


@login_required
@superadmin_required
def delete_organisation(request, org_id):
    """Delete an organisation"""
    if request.method != 'POST':
        return redirect('superadmin:organisation_master')
    
    from common.pymongo_utils import pymongo_filter, get_mongo_db
    from bson import ObjectId
    
    # Find organisation by ID using PyMongo
    try:
        # Try finding by ObjectId first, usually passed as string
        if isinstance(org_id, str) and len(org_id) == 24:
             query = {'_id': ObjectId(org_id), 'is_deleted': False}
        else:
             # Fallback for integer IDs if migrated from SQL
             query = {'id': org_id, 'is_deleted': False}
             
        org_matches = pymongo_filter(OrganisationMaster, query=query)
        if not org_matches:
             # Try fallback to string ID in 'id' field
             query = {'id': str(org_id), 'is_deleted': False}
             org_matches = pymongo_filter(OrganisationMaster, query=query)
             
        org = org_matches[0] if org_matches else None
    except Exception:
        org = None
    
    if not org:
        messages.error(request, 'Organisation not found.')
        return redirect('superadmin:organisation_master')
    
    org_name = org.organisation_name
    
    # Check if this is a mother org with children using PyMongo
    if org.org_type == 'mother':
        child_query = {'parent_organisation_id': org.id, 'is_deleted': False}
        children = pymongo_filter(OrganisationMaster, query=child_query)
        if children:
            messages.error(request, f'Cannot delete "{org_name}" because it has {len(children)} child organisation(s).')
            return redirect('superadmin:organisation_master')
    
    try:
        # Hard delete or soft delete using PyMongo
        # Since logic was "delete()", Djongo might hard-delete if it's not soft-delete model
        # But this model has is_deleted field, so we soft delete.
        
        db = get_mongo_db()
        collection = db[OrganisationMaster._meta.db_table]
        
        # Soft Delete
        if hasattr(org, '_id'):
            collection.update_one({'_id': org._id}, {'$set': {'is_deleted': True, 'deleted_at': timezone.now()}})
        else:
            collection.update_one({'id': org.id}, {'$set': {'is_deleted': True, 'deleted_at': timezone.now()}})

        log_activity_event(
            'organisation.deleted',
            subject_user=None,
            performed_by=request.user,
            metadata={'organisation_name': org_name},
        )
    
        messages.success(request, f'Organisation "{org_name}" deleted successfully.')
    
    except Exception as e:
        logger.exception(f"Error deleting organisation: {str(e)}")
        messages.error(request, 'An error occurred while deleting the organisation.')
    
    return redirect('superadmin:organisation_master')


# ========================================
# MARKETING JOB DROP VIEWS
# ========================================

@login_required
@superadmin_required
def marketing_job_drops(request):
    """
    SuperAdmin view for Marketing Details (pulls from marketing jobs, with filters).
    Mirrors Marketing dashboard recent activities but across all marketing users.
    """
    from marketing.models import Job
    from .models import JobDrop
    from django.db.models import Q
    from datetime import datetime, time
    
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', 'all')
    filter_category = request.GET.get('category', 'all')
    from_date_raw = (request.GET.get('from') or '').strip()
    to_date_raw = (request.GET.get('to') or '').strip()

    def _parse_date(val):
        """Parse incoming date in either yyyy-mm-dd or dd-mm-yyyy."""
        for fmt in ('%Y-%m-%d', '%d-%m-%Y'):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
        return None

    try:
        jobs_qs = Job.objects.select_related('created_by').prefetch_related('job_drop').order_by('-created_at')

        if search_query:
            jobs_qs = jobs_qs.filter(
                Q(system_id__icontains=search_query) |
                Q(job_id__icontains=search_query) |
                Q(topic__icontains=search_query) |
                Q(customer_name__icontains=search_query) |
                Q(customer_id__icontains=search_query) |
                Q(created_by__email__icontains=search_query)
            )

        if filter_status != 'all':
            jobs_qs = jobs_qs.filter(status=filter_status)

        if filter_category != 'all':
            jobs_qs = jobs_qs.filter(category=filter_category)

        # Handle date range filtering (accept both yyyy-mm-dd and dd-mm-yyyy)
        from_date_obj = _parse_date(from_date_raw) if from_date_raw else None
        to_date_obj = _parse_date(to_date_raw) if to_date_raw else None
        start_dt = None
        end_dt = None

        if from_date_obj:
            try:
                start_dt = timezone.make_aware(datetime.combine(from_date_obj, time.min))
                jobs_qs = jobs_qs.filter(created_at__gte=start_dt)
            except Exception as parse_err:
                logger.warning(f"Could not apply from_date filter ({from_date_raw}): {parse_err}")
        elif from_date_raw:
            logger.warning(f"Invalid from_date format: {from_date_raw}")

        if to_date_obj:
            try:
                end_dt = timezone.make_aware(datetime.combine(to_date_obj, time.max))
                jobs_qs = jobs_qs.filter(created_at__lte=end_dt)
            except Exception as parse_err:
                logger.warning(f"Could not apply to_date filter ({to_date_raw}): {parse_err}")
        elif to_date_raw:
            logger.warning(f"Invalid to_date format: {to_date_raw}")

        # Evaluate once to avoid Djongo aggregate errors
        jobs = list(jobs_qs)
        total_filtered = len(jobs)
        new_filtered = sum(1 for job in jobs if str(getattr(job, 'status', '')).lower() in ('pending', 'unallocated', 'draft'))
        edited_filtered = 0
        for job in jobs:
            jd = getattr(job, 'job_drop', None)
            if jd and getattr(jd, 'status', '') == 'edited':
                edited_filtered += 1

        context = {
            'jobs': jobs,
            'job_drops': jobs,  # reuse existing template loop
            'total_drops': total_filtered,
            'new_drops': new_filtered,
            'edited_drops': edited_filtered,
            'search_query': search_query,
            'filter_status': filter_status,
            'filter_category': filter_category,
            # Normalized values back to template (keep yyyy-mm-dd for flatpickr input)
            'from_date': from_date_obj.strftime('%Y-%m-%d') if from_date_obj else '',
            'to_date': to_date_obj.strftime('%Y-%m-%d') if to_date_obj else '',
            'status_choices': Job.STATUS_CHOICES,
            'category_choices': Job.CATEGORY_CHOICES,
        }

        logger.info(f"SuperAdmin {request.user.email} accessed marketing job list")

    except Exception as e:
        logger.exception(f"Error loading marketing job drops: {str(e)}")
        context = {
            'jobs': [],
            'total_drops': 0,
            'new_drops': 0,
            'edited_drops': 0,
            'search_query': search_query,
            'filter_status': filter_status,
            'filter_category': filter_category,
            'from_date': from_date_raw,
            'to_date': to_date_raw,
            'status_choices': [],
            'category_choices': [],
            'error': 'Failed to load job drops'
        }
    
    return render(request, 'marketing_job_drops.html', context)


@login_required
@superadmin_required
def job_drop_details(request, job_id):
    """Display job details for editing by superadmin"""
    from marketing.models import Job
    from .models import JobDrop
    from django.utils import timezone
    
    try:
        # Get job information
        job = get_object_or_404(Job, system_id=job_id)
        
        # Try to get or create job drop, but don't fail if there are issues
        try:
            # Use first() to handle multiple JobDrop records (MongoDB issue)
            job_drop = JobDrop.objects.filter(job=job).first()
            if not job_drop:
                job_drop = JobDrop.objects.create(
                    job=job,
                    submitted_by=getattr(job, 'created_by', request.user)
                )
            
            # Try to mark as viewed (but don't fail if this doesn't work due to MongoDB issues)
            if not job_drop.viewed_at:
                try:
                    job_drop.viewed_at = timezone.now()
                    job_drop.status = 'viewed'
                    job_drop.save()
                except Exception as view_error:
                    logger.warning(f"Could not mark job as viewed: {str(view_error)}")
        except Exception as drop_error:
            logger.warning(f"Could not create job drop record: {str(drop_error)}")
            job_drop = None
        
        if request.method == 'POST':
            # Handle job details update
            return update_job_drop_details(request, job, job_drop)
        
        context = {
            'job': job,
            'job_drop': job_drop,
            'category_choices': Job.CATEGORY_CHOICES,
            'status_choices': Job.STATUS_CHOICES,
            'referencing_choices': Job.REFERENCING_STYLE_CHOICES,
            'writing_choices': Job.WRITING_STYLE_CHOICES,
            'level_choices': Job.LEVEL_CHOICES,
        }
        
        logger.info(f"SuperAdmin {request.user.email} viewed job drop: {job_id}")
        
    except Exception as e:
        logger.exception(f"Error loading job details: {str(e)}")
        messages.error(request, 'Failed to load job details')
        return redirect('superadmin:marketing_job_drops')
    
    return render(request, 'job_drop_details.html', context)


@login_required
@superadmin_required
@transaction.atomic
def update_job_drop_details(request, job, job_drop):
    """Handle job details updates from superadmin"""
    from django.utils import timezone
    from decimal import Decimal
    from .models import JobDrop
    
    try:
        changes = {}
        
        # Fields that can be edited
        editable_fields = [
            'instruction',
            'category',
            'topic',
            'word_count',
            'referencing_style',
            'writing_style',
            'level',
            'amount',
            'status',
            'customer_id',
            'customer_name',
            'deadline',
            'software',
        ]
        
        # Update job fields
        for field in editable_fields:
            new_value = request.POST.get(field)
            if new_value is not None:
                old_value = getattr(job, field, None)
                
                # Special handling for amount field - convert to Decimal
                if field == 'amount' and new_value:
                    try:
                        new_value = Decimal(str(new_value))
                    except Exception:
                        logger.warning(f"Could not convert amount to Decimal: {new_value}")
                        continue
                
                if str(old_value) != str(new_value):
                    setattr(job, field, new_value)
                    changes[field] = {
                        'old': str(old_value),
                        'new': str(new_value),
                        'changed_at': timezone.now().isoformat()
                    }
        
        # Save job changes
        if changes:
            try:
                job.save()
            except Exception as save_error:
                logger.error(f"Error saving job changes: {str(save_error)}")
                messages.error(request, f"Error saving changes: {str(save_error)}")
                return redirect('superadmin:job_drop_details', job_id=job.system_id)
            
            # Update job drop tracking
            if job_drop:
                try:
                    job_drop.status = 'edited'
                    job_drop.edited_by = request.user
                    job_drop.edited_at = timezone.now()
                    job_drop.is_new = False
                    job_drop.changes_history = job_drop.changes_history or {}
                    job_drop.changes_history[request.user.email] = changes
                    job_drop.save()
                except Exception as drop_save_error:
                    logger.warning(f"Could not update job drop tracking: {str(drop_save_error)}")
            
            # Log the activity
            log_activity_event(
                'marketing.job_edited_by_superadmin',
                subject_user=job.created_by,
                performed_by=request.user,
                metadata={
                    'job_id': job.system_id,
                    'changes': changes,
                    'field_count': len(changes)
                },
            )
            
            messages.success(request, 'Job details updated successfully!')
            logger.info(f"SuperAdmin {request.user.email} edited job: {job.system_id}")
        else:
            messages.info(request, 'No changes made.')
        
    except Exception as e:
        logger.exception(f"Error updating job details: {str(e)}")
        messages.error(request, 'Failed to update job details')
    
    return redirect('superadmin:job_drop_details', job_id=job.system_id)


@login_required
@superadmin_required
def search_job_drops(request):
    """Wrapper to reuse marketing_job_drops filtering logic"""
    return marketing_job_drops(request)


@login_required
@superadmin_required
def job_drop_api(request, job_id):
    """API endpoint to get job drop details as JSON"""
    from .models import JobDrop
    
    try:
        job = get_object_or_404(Job, system_id=job_id)
        job_drop = get_object_or_404(JobDrop, job=job)
        
        data = {
            'success': True,
            'job': {
                'system_id': job.system_id,
                'job_id': job.job_id,
                'instruction': job.instruction,
                'topic': job.topic,
                'category': job.category,
                'level': job.level,
                'status': job.status,
                'word_count': job.word_count,
                'amount': str(job.amount) if job.amount else None,
                'referencing_style': job.referencing_style,
                'writing_style': job.writing_style,
                'customer_name': job.customer_name,
                'deadline': str(job.deadline) if job.deadline else None,
            },
            'job_drop': {
                'status': job_drop.status,
                'submitted_by': job_drop.submitted_by.email,
                'submitted_at': job_drop.submitted_at.isoformat(),
                'viewed_at': job_drop.viewed_at.isoformat() if job_drop.viewed_at else None,
                'edited_by': job_drop.edited_by.email if job_drop.edited_by else None,
                'edited_at': job_drop.edited_at.isoformat() if job_drop.edited_at else None,
                'changes_history': job_drop.changes_history,
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        logger.exception(f"Error fetching job drop API: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to load job drop details'
        }, status=400)


@login_required
@superadmin_required
def marketing_manager_details(request):
    """
    SuperAdmin view to see marketing managers' jobs within a date range,
    including totals and per-job breakdown.
    """
    from marketing.models import Job, Customer
    from datetime import datetime, time

    from_date_raw = (request.GET.get('from') or '').strip()
    to_date_raw = (request.GET.get('to') or '').strip()

    from_dt = None
    to_dt = None
    try:
        if from_date_raw:
            parsed_from = datetime.strptime(from_date_raw, "%d-%m-%Y").date()
            from_dt = timezone.make_aware(datetime.combine(parsed_from, time.min))
    except Exception:
        from_dt = None
    try:
        if to_date_raw:
            parsed_to = datetime.strptime(to_date_raw, "%d-%m-%Y").date()
            to_dt = timezone.make_aware(datetime.combine(parsed_to, time.max))
    except Exception:
        to_dt = None

    jobs_qs = Job.objects.filter(created_by__role='marketing').select_related('created_by').order_by('-created_at')

    # Apply date filters
    if from_dt:
        jobs_qs = jobs_qs.filter(created_at__gte=from_dt)
    if to_dt:
        jobs_qs = jobs_qs.filter(created_at__lte=to_dt)

    jobs = list(jobs_qs)
    customer_map = {
        c.customer_id: c for c in Customer.objects.filter(
            customer_id__in=[j.customer_id for j in jobs if getattr(j, 'customer_id', None)]
        )
    }

    # Group by marketing manager
    managers = {}
    for job in jobs:
        key = job.created_by_id
        mgr = managers.setdefault(key, {
            'manager': job.created_by,
            'jobs': [],
            'total_amount': 0,
            'target_amount': 0,
            'job_count': 0,
            'customers': {},  # temp dict keyed by customer_id
        })
        mgr['jobs'].append(job)
        mgr['job_count'] += 1
        # Actual amount
        try:
            mgr['total_amount'] += float(str(job.amount)) if job.amount is not None else 0
        except Exception:
            pass
        # Target/system expected amount
        try:
            mgr['target_amount'] += float(str(job.system_expected_amount)) if job.system_expected_amount is not None else 0
        except Exception:
            pass
        # Customer aggregation
        cust = getattr(job, 'customer', None)
        cust_id = None
        cust_name = None
        cust_email = None
        cust_phone = None
        cust_target = None
        cust_current = None
        cust_active = True
        if cust:
            cust_id = cust.customer_id
            cust_name = cust.customer_name
            cust_email = cust.customer_email
            cust_phone = cust.customer_phone
            cust_target = cust.targeted_amount
            cust_current = cust.current_amount
            cust_active = cust.is_active
        else:
            cust_id = getattr(job, 'customer_id', None)
            cust_name = getattr(job, 'customer_name', None)
            if cust_id and cust_id in customer_map:
                found = customer_map[cust_id]
                cust_name = found.customer_name
                cust_email = found.customer_email
                cust_phone = found.customer_phone
                cust_target = found.targeted_amount
                cust_current = found.current_amount
                cust_active = found.is_active

        if cust_id:
            cdict = mgr['customers'].setdefault(cust_id, {
                'customer_id': cust_id,
                'customer_name': cust_name or '—',
                'customer_email': cust_email or '—',
                'customer_phone': cust_phone or '—',
                'targeted_amount': float(str(cust_target)) if cust_target not in (None, '') else 0.0,
                'current_amount': 0.0,
                'jobs': [],
                'job_amount': 0.0,
                'is_active': cust_active,
            })
            cdict['jobs'].append(job)
            try:
                amt = float(str(job.amount)) if job.amount is not None else 0.0
                cdict['job_amount'] += amt
                cdict['current_amount'] = cdict['job_amount']
            except Exception:
                pass

    # Finalize manager list and customer lists
    manager_list = []
    for mgr in managers.values():
        cust_list = list(mgr['customers'].values())
        mgr['customers'] = cust_list
        manager_list.append(mgr)

    context = {
        'from_date': from_date_raw,
        'to_date': to_date_raw,
        'manager_data': manager_list,
    }
    return render(request, 'marketing_manager_details.html', context)


@login_required
@superadmin_required
def toggle_customer_active(request, customer_id):
    """Toggle active status for a marketing customer."""
    from marketing.models import Customer

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('superadmin:marketing_manager_details')

    from_date = request.POST.get('from', '')
    to_date = request.POST.get('to', '')

    try:
        customer = get_object_or_404(Customer, customer_id=customer_id)
        desired_state_raw = request.POST.get('active_state')
        if desired_state_raw is not None:
            desired_state = str(desired_state_raw).lower() in ['true', '1', 'on', 'yes']
        else:
            desired_state = not customer.is_active

        # Use queryset update to bypass full_clean on legacy decimals
        Customer.objects.filter(customer_id=customer_id).update(
            is_active=desired_state,
            updated_at=timezone.now()
        )

        state = 'activated' if desired_state else 'deactivated'
        log_activity_event(
            f'customer.{state}',
            subject_user=None,
            performed_by=request.user,
            metadata={'customer_id': customer.customer_id, 'state': desired_state},
        )
        messages.success(request, f'Customer {customer.customer_id} set to {state}.')
    except Exception as e:
        logger.exception(f"Error toggling customer active: {str(e)}")
        messages.error(request, 'Failed to update customer status.')

    redirect_url = f"{reverse('superadmin:marketing_manager_details')}?from={from_date}&to={to_date}"
    return redirect(redirect_url)


@login_required
@superadmin_required
def update_customer_target(request, customer_id):
    """Allow superadmin to edit customer target amount."""
    from marketing.models import Customer
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('superadmin:marketing_manager_details')

    from_date = request.POST.get('from', '')
    to_date = request.POST.get('to', '')
    new_target = request.POST.get('target_amount', '').strip()

    try:
        customer = get_object_or_404(Customer, customer_id=customer_id)
        if not new_target:
            messages.error(request, 'Target amount is required.')
            return redirect(f"{reverse('superadmin:marketing_manager_details')}?from={from_date}&to={to_date}")

        try:
            from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
            new_target_dec = Decimal(str(new_target))
            # Enforce positive target (model has MinValueValidator(1))
            if new_target_dec <= 0:
                raise InvalidOperation("Target must be greater than zero")
            # normalize to 2 decimal places with sane rounding
            new_target_dec = new_target_dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (InvalidOperation, Exception):
            messages.error(request, 'Invalid target amount.')
            return redirect(f"{reverse('superadmin:marketing_manager_details')}?from={from_date}&to={to_date}")

        old_target = customer.targeted_amount
        # Persist using queryset update to bypass model full_clean (legacy decimal strings elsewhere)
        Customer.objects.filter(customer_id=customer_id).update(
            targeted_amount=new_target_dec,
            updated_at=timezone.now()
        )

        log_activity_event(
            'customer.target_updated',
            subject_user=None,
            performed_by=request.user,
            metadata={
                'customer_id': customer.customer_id,
                'old_target': str(old_target),
                'new_target': str(new_target_dec),
            },
        )
        messages.success(request, f"Target updated for {customer.customer_id}.")
    except Exception as e:
        logger.exception(f"Error updating customer target: {str(e)}")
        messages.error(request, 'Failed to update target amount.')

    redirect_url = f"{reverse('superadmin:marketing_manager_details')}?from={from_date}&to={to_date}"
    return redirect(redirect_url)


@login_required
@superadmin_required
def all_writer_details(request):
    """Superadmin view to see all writers with job KPIs and filters."""
    from marketing.models import Job
    from datetime import datetime, time, timedelta
    from django.db.models import Q

    writer_q = (request.GET.get('writer_q') or '').strip()
    emp_q = (request.GET.get('emp_q') or '').strip()
    job_q = (request.GET.get('job_q') or '').strip()
    from_date_raw = (request.GET.get('from') or '').strip()
    to_date_raw = (request.GET.get('to') or '').strip()

    def _parse_date(val):
        for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
        return None

    from_dt = None
    to_dt = None
    parsed_from = _parse_date(from_date_raw)
    parsed_to = _parse_date(to_date_raw)
    if parsed_from:
        from_dt = timezone.make_aware(datetime.combine(parsed_from, time.min))
    if parsed_to:
        to_dt = timezone.make_aware(datetime.combine(parsed_to, time.max))

    from common.pymongo_utils import pymongo_filter
    
    # Use PyMongo to bypass broken ORM SQL parsing
    writer_query = {'role': 'writer'}
    if writer_q:
        try:
            # Handle both integer and string IDs
            try:
                id_val = int(writer_q)
                writer_query['id'] = id_val
            except ValueError:
                writer_query['id'] = writer_q
        except Exception:
            pass
            
    if emp_q:
        writer_query['employee_id'] = {'$regex': emp_q, '$options': 'i'}

    # Fetch writers
    writers = pymongo_filter(
        CustomUser, 
        query=writer_query, 
        sort=[('first_name', 1), ('last_name', 1)]
    )
    
    # Prefetch specialisations via PyMongo to avoid ORM join crashes
    from superadminpanel.models import SpecialisationMaster
    from common.pymongo_utils import pymongo_prefetch_m2m
    pymongo_prefetch_m2m(
        writers,
        field_name='specialisations',
        related_model=SpecialisationMaster,
        join_table='custom_users_specialisations',
        source_field='customuser_id',
        target_field='specialisationmaster_id'
    )
    
    writer_ids = [w.id for w in writers]

    # Fetch jobs
    job_query = {'allocated_to_id': {'$in': writer_ids}}
    if from_dt:
        job_query['created_at'] = job_query.get('created_at', {})
        job_query['created_at']['$gte'] = from_dt
    if to_dt:
        job_query['created_at'] = job_query.get('created_at', {})
        job_query['created_at']['$lte'] = to_dt
    
    if job_q:
        job_query['$or'] = [
            {'system_id': {'$regex': job_q, '$options': 'i'}},
            {'job_id': {'$regex': job_q, '$options': 'i'}},
            {'topic': {'$regex': job_q, '$options': 'i'}}
        ]

    jobs = pymongo_filter(Job, query=job_query, sort=[('created_at', -1)])
    today = timezone.localdate()
    week_start = today - timedelta(days=6)

    writer_map = {w.id: {'writer': w, 'jobs': []} for w in writers}
    for job in jobs:
        if job.allocated_to_id in writer_map:
            writer_map[job.allocated_to_id]['jobs'].append(job)

    writer_data = []
    for item in writer_map.values():
        w = item['writer']
        w_jobs = item['jobs']
        total_jobs = len(w_jobs)
        completed_jobs = sum(1 for j in w_jobs if str(getattr(j, 'status', '')).lower() == 'completed')
        in_progress_jobs = sum(1 for j in w_jobs if str(getattr(j, 'status', '')).lower() == 'in_progress')
        today_jobs = [j for j in w_jobs if getattr(j, 'created_at', None) and j.created_at.date() == today]
        week_jobs = [j for j in w_jobs if getattr(j, 'created_at', None) and j.created_at.date() >= week_start]

        def _sum_words(job_list):
            total = 0
            for j in job_list:
                try:
                    total += int(j.word_count or 0)
                except Exception:
                    continue
            return total

        today_jobs = [j for j in w_jobs if getattr(j, 'created_at', None) and j.created_at.date() == today]
        today_completed = [j for j in today_jobs if str(getattr(j, 'status', '')).lower() == 'completed']
        today_inprogress = [j for j in today_jobs if str(getattr(j, 'status', '')).lower() == 'in_progress']
        issue_statuses = {'query', 'hold'}
        today_issues_list = [j for j in today_jobs if str(getattr(j, 'status', '')).lower() in issue_statuses]

        def _serialize_job(job):
            return {
                'system_id': getattr(job, 'system_id', ''),
                'job_id': getattr(job, 'job_id', ''),
                'topic': getattr(job, 'topic', ''),
                'category': getattr(job, 'category', ''),
                'status': getattr(job, 'status', ''),
                'word_count': getattr(job, 'word_count', '') or '',
                'deadline': job.deadline.strftime('%d/%m/%Y') if getattr(job, 'deadline', None) else 'N/A',
                'amount': str(job.amount) if getattr(job, 'amount', None) not in (None, '') else 'N/A',
                'created_at': job.created_at.strftime('%d/%m/%Y %H:%M') if getattr(job, 'created_at', None) else 'N/A',
            }

        today_buckets = {
            'today_all': [_serialize_job(j) for j in today_jobs],
            'today_completed': [_serialize_job(j) for j in today_completed],
            'today_inprogress': [_serialize_job(j) for j in today_inprogress],
            'today_words': [_serialize_job(j) for j in today_jobs],
            'today_issues': [_serialize_job(j) for j in today_issues_list],
        }

        writer_data.append({
            'writer': w,
            'jobs': w_jobs,
            'total_jobs': total_jobs,
            'completed_jobs': completed_jobs,
            'in_progress_jobs': in_progress_jobs,
            'today_jobs': len(today_jobs),
            'today_words': _sum_words(today_jobs),
            'week_jobs': len(week_jobs),
            'week_words': _sum_words(week_jobs),
            'today_completed_jobs': len(today_completed),
            'today_inprogress_jobs': len(today_inprogress),
            'today_issues': len(today_issues_list),
            'today_words_count': _sum_words(today_jobs),
            'today_buckets_json': json.dumps(today_buckets),
            'today_buckets': today_buckets,
        })

    context = {
        'writer_data': writer_data,
        'writer_q': writer_q,
        'emp_q': emp_q,
        'job_q': job_q,
        'from_date': from_date_raw,
        'to_date': to_date_raw,
        'writer_choices': writers if not writer_q else pymongo_filter(CustomUser, query={'role': 'writer'}, sort=[('first_name', 1), ('last_name', 1)]),
    }
    return render(request, 'all_writer_details.html', context)


@login_required
@superadmin_required
def writer_details(request, writer_id):
    """Dedicated page for a single writer with KPIs and job list."""
    from marketing.models import Job
    from datetime import datetime, time, timedelta
    import json

    from_date_raw = (request.GET.get('from') or '').strip()
    to_date_raw = (request.GET.get('to') or '').strip()

    def _parse_date(val):
        for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
        return None

    from common.pymongo_utils import pymongo_get, pymongo_filter
    from django.http import Http404

    # Use PyMongo to bypass broken ORM SQL parsing
    # Handle both integer and string IDs
    writer = None
    try:
        writer = pymongo_get(CustomUser, id=int(writer_id), role='writer')
    except (ValueError, TypeError):
        writer = pymongo_get(CustomUser, id=writer_id, role='writer')
    
    if not writer:
        raise Http404("Writer not found")

    parsed_from = _parse_date(from_date_raw)
    parsed_to = _parse_date(to_date_raw)
    from_dt = timezone.make_aware(datetime.combine(parsed_from, time.min)) if parsed_from else None
    to_dt = timezone.make_aware(datetime.combine(parsed_to, time.max)) if parsed_to else None

    # Fetch jobs via PyMongo
    job_query = {'allocated_to_id': writer.id}
    if from_dt:
        job_query['created_at'] = job_query.get('created_at', {})
        job_query['created_at']['$gte'] = from_dt
    if to_dt:
        job_query['created_at'] = job_query.get('created_at', {})
        job_query['created_at']['$lte'] = to_dt

    jobs = pymongo_filter(Job, query=job_query, sort=[('created_at', -1)])

    # Prefetch specialisations via PyMongo
    from superadminpanel.models import SpecialisationMaster
    pymongo_prefetch_m2m(
        [writer],
        field_name='specialisations',
        related_model=SpecialisationMaster,
        join_table='custom_users_specialisations',
        source_field='customuser_id',
        target_field='specialisationmaster_id'
    )
    today = timezone.localdate()
    week_start = today - timedelta(days=6)

    total_jobs = len(jobs)
    completed_jobs_list = [j for j in jobs if str(getattr(j, 'status', '')).lower() == 'completed']
    in_progress_jobs_list = [j for j in jobs if str(getattr(j, 'status', '')).lower() == 'in_progress']
    issue_statuses = {'query', 'hold'}
    issue_jobs_list = [j for j in jobs if str(getattr(j, 'status', '')).lower() in issue_statuses]

    completed_jobs = len(completed_jobs_list)
    in_progress_jobs = len(in_progress_jobs_list)
    today_jobs = [j for j in jobs if getattr(j, 'created_at', None) and j.created_at.date() == today]
    week_jobs = [j for j in jobs if getattr(j, 'created_at', None) and j.created_at.date() >= week_start]
    today_issue_jobs = [j for j in issue_jobs_list if getattr(j, 'created_at', None) and j.created_at.date() == today]
    week_issue_jobs = [j for j in issue_jobs_list if getattr(j, 'created_at', None) and j.created_at.date() >= week_start]
    year_issue_jobs = [j for j in issue_jobs_list if getattr(j, 'created_at', None) and j.created_at.date().year == today.year]

    def _sum_words(job_list):
        total = 0
        for j in job_list:
            try:
                total += int(j.word_count or 0)
            except Exception:
                continue
        return total

    # Build category-specific job lists for filtering on UI
    job_buckets = {
        'total': jobs,
        'completed': completed_jobs_list,
        'in_progress': in_progress_jobs_list,
        'today': today_jobs,
        'week': week_jobs,
    }

    def _serialize_job(job):
        return {
            'system_id': getattr(job, 'system_id', ''),
            'job_id': getattr(job, 'job_id', ''),
            'topic': getattr(job, 'topic', ''),
            'category': getattr(job, 'category', ''),
            'status': getattr(job, 'status', ''),
            'word_count': getattr(job, 'word_count', '') or '',
            'deadline': job.deadline.strftime('%d/%m/%Y') if getattr(job, 'deadline', None) else '�',
            'amount': str(job.amount) if getattr(job, 'amount', None) not in (None, '') else '�',
            'created_at': job.created_at.strftime('%d/%m/%Y %H:%M') if getattr(job, 'created_at', None) else '�',
        }

    job_buckets_json = json.dumps({
        'total': [ _serialize_job(j) for j in jobs ],
        'completed': [ _serialize_job(j) for j in completed_jobs_list ],
        'in_progress': [ _serialize_job(j) for j in in_progress_jobs_list ],
        'today': [ _serialize_job(j) for j in today_jobs ],
        'week': [ _serialize_job(j) for j in week_jobs ],
        'issues_today': [ _serialize_job(j) for j in today_issue_jobs ],
        'issues_week': [ _serialize_job(j) for j in week_issue_jobs ],
        'issues_year': [ _serialize_job(j) for j in year_issue_jobs ],
    })

    context = {
        'writer': writer,
        'from_date': from_date_raw,
        'to_date': to_date_raw,
        'total_jobs': total_jobs,
        'completed_jobs': completed_jobs,
        'in_progress_jobs': in_progress_jobs,
        'today_jobs': len(today_jobs),
        'today_words': _sum_words(today_jobs),
        'week_jobs': len(week_jobs),
        'week_words': _sum_words(week_jobs),
        'issues_today': len(today_issue_jobs),
        'issues_week': len(week_issue_jobs),
        'issues_year': len(year_issue_jobs),
        'job_buckets_json': job_buckets_json,
    }
    return render(request, 'writer_details.html', context)


@login_required
@superadmin_required
def admin_my_letters(request):
    """View all generated letters in the system"""
    from .models import GeneratedLetter
    
    try:
        all_letters = list(GeneratedLetter.objects.all())
        letters = [l for l in all_letters if not l.is_deleted]
        letters.sort(key=lambda x: x.generated_at, reverse=True)
    except Exception as e:
        logger.error(f"Error fetching letters: {e}")
        letters = []
    
    context = {
        'letters': letters,
    }
    return render(request, 'admin_my_letters.html', context)


@login_required
@superadmin_required
def admin_view_letter(request, letter_id):
    """View a specific letter generated by admin or download as PDF"""
    from .models import GeneratedLetter
    
    try:
        all_letters = list(GeneratedLetter.objects.all())
        letter = None
        for l in all_letters:
            if l.id == letter_id and not l.is_deleted:
                letter = l
                break
        
        if not letter:
            messages.error(request, "Letter not found.")
            return redirect('superadmin:admin_my_letters')
    except Exception as e:
        logger.error(f"Error fetching letter: {e}")
        messages.error(request, "Error loading letter.")
        return redirect('superadmin:admin_my_letters')
    
    # Check if download is requested
    if request.GET.get('download') == '1':
        return _generate_letter_pdf_admin(letter)
    
    context = {
        'letter': letter,
    }
    return render(request, 'admin_view_letter.html', context)


def _generate_letter_pdf_admin(letter):
    """Generate PDF from letter content for superadmin"""
    from django.http import HttpResponse
    from io import BytesIO
    from xhtml2pdf import pisa
    
    # Create HTML with proper styling for PDF
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: Arial, Helvetica, sans-serif;
                font-size: 12pt;
                line-height: 1.6;
                color: #333;
            }}
            h1, h2, h3 {{
                color: #222;
            }}
            .letter-header {{
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 2px solid #333;
                padding-bottom: 20px;
            }}
            .letter-content {{
                margin-top: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            .footer {{
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                text-align: center;
                font-size: 10pt;
                color: #666;
                padding: 10px;
                border-top: 1px solid #ddd;
            }}
        </style>
    </head>
    <body>
        <div class="letter-content">
            {letter.rendered_content}
        </div>
    </body>
    </html>
    """
    
    # Create PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_content.encode('utf-8')), result)
    
    if pdf.err:
        logger.error(f"Error generating PDF for letter {letter.letter_id}")
        return HttpResponse("Error generating PDF", status=500)
    
    # Create response
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    filename = f"{letter.letter_type}_{letter.letter_id}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

