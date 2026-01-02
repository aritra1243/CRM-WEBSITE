# superadminpanel/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db import transaction
from datetime import datetime, timedelta
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
    TemplateMaster,
    SpecialisationMaster,
    JobDrop,
)
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
    try:
        all_specs = SpecialisationMaster.objects.all().order_by('specialisation_name')
        context['all_specialisations'] = _filter_not_deleted(all_specs)
    except Exception as e:
        logger.exception(f"Error loading specialisations: {str(e)}")
        context['all_specialisations'] = []
    
    return render(request, 'manage_users.html', context)


@login_required
@superadmin_required
def update_user_role(request, user_id):
    """Update user role"""
    portal_services.update_user_role(request, user_id)
    return redirect('manage_users')


@login_required
@superadmin_required
def update_user_category(request, user_id):
    """Update user category/department"""
    portal_services.update_user_category(request, user_id)
    return redirect('manage_users')


@login_required
@superadmin_required
def update_user_level(request, user_id):
    """Update user level"""
    portal_services.update_user_level(request, user_id)
    return redirect('manage_users')


@login_required
@superadmin_required
def toggle_user_status(request, user_id):
    """Toggle user active status"""
    portal_services.toggle_user_status(request, user_id)
    return redirect('manage_users')


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
        return redirect('manage_users')
    
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
    return redirect('pending_items')


@login_required
@superadmin_required
def reject_user(request, user_id):
    """Reject user registration"""
    portal_services.reject_user(request, user_id)
    return redirect('pending_items')


@login_required
@superadmin_required
def approve_profile_request(request, request_id):
    """Approve profile change request"""
    portal_services.approve_profile_request(request, request_id)
    return redirect('pending_items')


@login_required
@superadmin_required
def reject_profile_request(request, request_id):
    """Reject profile change request"""
    portal_services.reject_profile_request(request, request_id)
    return redirect('pending_items')


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
    try:
        raw_holidays = list(Holiday.objects.all().order_by('-created_at'))
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
                return redirect('holiday_master')
            
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
                        return redirect('holiday_master')
                    
                    holiday.date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    start_date = holiday.date
                    end_date = holiday.date
                    
                else:  # consecutive
                    from_date_str = request.POST.get('from_date')
                    to_date_str = request.POST.get('to_date')
                    
                    if not from_date_str or not to_date_str:
                        messages.error(request, 'From date and To date are required.')
                        return redirect('holiday_master')
                    
                    holiday.from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                    holiday.to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                    
                    if holiday.from_date > holiday.to_date:
                        messages.error(request, 'From date must be before To date.')
                        return redirect('holiday_master')
                    
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
                
                # Sync to Google Calendar (if service is available)
                holiday.google_calendar_sync_started_at = timezone.now()
                holiday.save(update_fields=['google_calendar_sync_started_at'])
                
                log_activity_event(
                    'holiday.google_calendar_sync_started_at',
                    subject_user=None,
                    performed_by=None,
                    metadata={'holiday_id': holiday.id, 'performed_by': 'system'},
                )
                
                try:
                    # Import Google Calendar service if available
                    from .services.google_calendar_service import GoogleCalendarService
                    calendar_service = GoogleCalendarService()
                    event_id = calendar_service.create_event(
                        holiday_name=holiday_name,
                        start_date=start_date,
                        end_date=end_date,
                        description=description,
                        holiday_type=holiday_type
                    )
                    
                    if event_id:
                        holiday.google_calendar_event_id = event_id
                        holiday.is_synced_to_calendar = True
                        holiday.google_calendar_synced_at = timezone.now()
                        holiday.save(update_fields=[
                            'google_calendar_event_id',
                            'is_synced_to_calendar',
                            'google_calendar_synced_at'
                        ])
                        
                        log_activity_event(
                            'holiday.google_calendar_synced_at',
                            subject_user=None,
                            performed_by=None,
                            metadata={
                                'holiday_id': holiday.id,
                                'event_id': event_id,
                                'performed_by': 'system',
                            },
                        )
                        
                        logger.info(f"Holiday '{holiday_name}' created and synced to Google Calendar")
                        messages.success(request, f'Holiday "{holiday_name}" created and synced to Google Calendar!')
                    else:
                        holiday.google_calendar_sync_failed_at = timezone.now()
                        holiday.save(update_fields=['google_calendar_sync_failed_at'])
                        
                        log_activity_event(
                            'holiday.google_calendar_sync_failed_at',
                            subject_user=None,
                            performed_by=None,
                            metadata={
                                'holiday_id': holiday.id,
                                'error': 'Failed to create calendar event',
                                'performed_by': 'system',
                            },
                        )
                        
                        logger.warning(f"Holiday created but failed to sync to Google Calendar")
                        messages.warning(request, f'Holiday "{holiday_name}" created but failed to sync to Google Calendar.')
                        
                except ImportError:
                    logger.info("Google Calendar service not available")
                    messages.success(request, f'Holiday "{holiday_name}" created successfully!')
                except Exception as calendar_error:
                    holiday.google_calendar_sync_failed_at = timezone.now()
                    holiday.save(update_fields=['google_calendar_sync_failed_at'])
                    
                    log_activity_event(
                        'holiday.google_calendar_sync_failed_at',
                        subject_user=None,
                        performed_by=None,
                        metadata={
                            'holiday_id': holiday.id,
                            'error': str(calendar_error),
                            'performed_by': 'system',
                        },
                    )
                    
                    logger.error(f"Google Calendar sync error: {str(calendar_error)}")
                    messages.warning(request, f'Holiday "{holiday_name}" created but Google Calendar sync failed.')
            
            return redirect('holiday_master')
            
        except Exception as e:
            logger.exception(f"Error creating holiday: {str(e)}")
            messages.error(request, 'An error occurred while creating the holiday.')
            return redirect('holiday_master')
    
    return redirect('holiday_master')


@login_required
@superadmin_required
def edit_holiday(request, holiday_id):
    """Update an existing holiday"""
    if request.method != 'POST':
        return redirect('holiday_master')
    
    holiday = next(
        (
            item for item in Holiday.objects.all()
            if item.id == holiday_id and not getattr(item, 'is_deleted', False)
        ),
        None
    )
    
    if not holiday:
        messages.error(request, 'Holiday not found.')
        return redirect('holiday_master')
    
    try:
        holiday_name = request.POST.get('holiday_name', '').strip()
        holiday_type = request.POST.get('holiday_type', 'full_day')
        date_type = request.POST.get('date_type', 'single')
        description = request.POST.get('description', '').strip()
        
        if not holiday_name:
            messages.error(request, 'Holiday name is required.')
            return redirect('holiday_master')
        
        if date_type == 'single':
            date_str = request.POST.get('date')
            if not date_str:
                messages.error(request, 'Date is required for single-day holiday.')
                return redirect('holiday_master')
            start_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            end_date = start_date
        else:
            from_date_str = request.POST.get('from_date')
            to_date_str = request.POST.get('to_date')
            
            if not from_date_str or not to_date_str:
                messages.error(request, 'Both From and To dates are required for consecutive holidays.')
                return redirect('holiday_master')
            
            start_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            
            if start_date > end_date:
                messages.error(request, 'From date must be before To date.')
                return redirect('holiday_master')
        
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
            
            holiday.google_calendar_sync_started_at = timezone.now()
            holiday.google_calendar_sync_failed_at = None
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
            
            try:
                from .services.google_calendar_service import GoogleCalendarService
                calendar_service = GoogleCalendarService()
                
                if holiday.google_calendar_event_id:
                    sync_ok = calendar_service.update_event(
                        holiday.google_calendar_event_id,
                        holiday_name,
                        start_date,
                        end_date,
                        description=description,
                        holiday_type=holiday_type,
                    )
                else:
                    event_id = calendar_service.create_event(
                        holiday_name=holiday_name,
                        start_date=start_date,
                        end_date=end_date,
                        description=description,
                        holiday_type=holiday_type,
                    )
                    sync_ok = bool(event_id)
                    if event_id:
                        holiday.google_calendar_event_id = event_id
                
                if sync_ok:
                    holiday.is_synced_to_calendar = True
                    holiday.google_calendar_synced_at = timezone.now()
                    holiday.save(update_fields=['is_synced_to_calendar', 'google_calendar_synced_at', 'google_calendar_event_id'])
                else:
                    holiday.is_synced_to_calendar = False
                    holiday.google_calendar_sync_failed_at = timezone.now()
                    holiday.save(update_fields=['is_synced_to_calendar', 'google_calendar_sync_failed_at'])
                    logger.warning("Holiday updated but failed to sync to Google Calendar.")
            
            except ImportError:
                logger.info("Google Calendar service not available")
            except Exception as calendar_error:
                holiday.is_synced_to_calendar = False
                holiday.google_calendar_sync_failed_at = timezone.now()
                holiday.save(update_fields=['is_synced_to_calendar', 'google_calendar_sync_failed_at'])
                logger.error(f"Google Calendar sync error during update: {str(calendar_error)}")
        
        messages.success(request, f'Holiday "{holiday.holiday_name}" updated successfully.')
    
    except Exception as e:
        logger.exception(f"Error updating holiday: {str(e)}")
        messages.error(request, 'An error occurred while updating the holiday.')
    
    return redirect('holiday_master')


@login_required
@superadmin_required
def delete_holiday(request, holiday_id):
    """Permanently delete a holiday"""
    if request.method != 'POST':
        return redirect('holiday_master')
    
    holiday = Holiday.objects.filter(id=holiday_id).first()
    
    if not holiday:
        messages.error(request, 'Holiday not found.')
        return redirect('holiday_master')
    
    holiday_id_ref = holiday.id
    holiday_name_ref = holiday.holiday_name
    calendar_event_id = holiday.google_calendar_event_id
    
    try:
        with transaction.atomic():
            if calendar_event_id:
                try:
                    from .services.google_calendar_service import GoogleCalendarService
                    calendar_service = GoogleCalendarService()
                    calendar_service.delete_event(calendar_event_id)
                    logger.info(f"Holiday deleted from Google Calendar: {holiday_name_ref}")
                except ImportError:
                    logger.info("Google Calendar service not available")
                except Exception as calendar_error:
                    logger.error(f"Error deleting from Google Calendar: {str(calendar_error)}")
            
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
    
    return redirect('holiday_master')


# This is continuation of views.py - PRICE and REFERENCING MASTER sections
# Copy this after Holiday Master views

# ========================================
# PRICE MASTER VIEWS
# ========================================

@login_required
@superadmin_required
def price_master(request):
    """Price Master - List all prices"""
    try:
        raw_prices = list(PriceMaster.objects.all().order_by('-created_at'))
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
                return redirect('price_master')
            
            try:
                price_per_word = float(price_per_word)
                if price_per_word <= 0:
                    messages.error(request, 'Price per word must be greater than 0.')
                    return redirect('price_master')
            except ValueError:
                messages.error(request, 'Invalid price format.')
                return redirect('price_master')
            
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
                return redirect('price_master')
            
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
            
            return redirect('price_master')
            
        except Exception as e:
            logger.exception(f"Error creating price: {str(e)}")
            messages.error(request, 'An error occurred while creating the price.')
            return redirect('price_master')
    
    return redirect('price_master')


@login_required
@superadmin_required
def edit_price(request, price_id):
    """Update an existing price entry"""
    if request.method != 'POST':
        return redirect('price_master')
    
    all_prices = list(PriceMaster.objects.filter(id=price_id))
    price_obj = next(
        (item for item in all_prices if not getattr(item, 'is_deleted', False)),
        None
    )
    
    if not price_obj:
        messages.error(request, 'Price entry not found.')
        return redirect('price_master')
    
    try:
        category = request.POST.get('category', '').strip()
        level = request.POST.get('level', '').strip()
        price_per_word = request.POST.get('price_per_word', '').strip()
        
        if not category or not level or not price_per_word:
            messages.error(request, 'All fields are required.')
            return redirect('price_master')
        
        try:
            price_per_word = float(price_per_word)
            if price_per_word <= 0:
                messages.error(request, 'Price per word must be greater than 0.')
                return redirect('price_master')
        except ValueError:
            messages.error(request, 'Invalid price format.')
            return redirect('price_master')
        
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
            return redirect('price_master')
        
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
    
    return redirect('price_master')


@login_required
@superadmin_required
def delete_price(request, price_id):
    """Delete a price entry"""
    if request.method != 'POST':
        return redirect('price_master')
    
    price_obj = None
    try:
        price_obj = PriceMaster.objects.get(id=price_id)
    except PriceMaster.DoesNotExist:
        messages.error(request, 'Price entry not found.')
        return redirect('price_master')
    
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
    
    return redirect('price_master')


# ========================================
# REFERENCING MASTER VIEWS
# ========================================

@login_required
@superadmin_required
def referencing_master(request):
    """Referencing Master - List all references"""
    try:
        raw_references = list(ReferencingMaster.objects.all().order_by('-created_at'))
        references = [
            reference for reference in raw_references
            if not getattr(reference, 'is_deleted', False)
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
                return redirect('referencing_master')
            
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
                return redirect('referencing_master')
            
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
            
            return redirect('referencing_master')
            
        except Exception as e:
            logger.exception(f"Error creating reference: {str(e)}")
            messages.error(request, 'An error occurred while creating the reference.')
            return redirect('referencing_master')
    
    return redirect('referencing_master')


@login_required
@superadmin_required
def edit_reference(request, reference_id):
    """Update an existing reference entry"""
    if request.method != 'POST':
        return redirect('referencing_master')
    
    reference_obj = _find_reference_by_id(reference_id)
    
    if not reference_obj:
        messages.error(request, 'Reference entry not found.')
        return redirect('referencing_master')
    
    try:
        referencing_style = request.POST.get('referencing_style', '').strip()
        used_in = request.POST.get('used_in', '').strip()
        
        if not referencing_style or not used_in:
            messages.error(request, 'All fields are required.')
            return redirect('referencing_master')
        
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
            return redirect('referencing_master')
        
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
    
    return redirect('referencing_master')


@login_required
@superadmin_required
def delete_reference(request, reference_id):
    """Delete a reference entry"""
    if request.method != 'POST':
        return redirect('referencing_master')
    
    reference_obj = _find_reference_by_id(reference_id)
    
    if not reference_obj:
        messages.error(request, 'Reference entry not found.')
        return redirect('referencing_master')
    
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
    
    return redirect('referencing_master')


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
    try:
        raw_writings = list(AcademicWritingMaster.objects.all().order_by('-created_at'))
        writings = [
            writing for writing in raw_writings
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
                return redirect('academic_writing_master')
            
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
                return redirect('academic_writing_master')
            
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
            
            return redirect('academic_writing_master')
            
        except Exception as e:
            logger.exception(f"Error creating writing style: {str(e)}")
            messages.error(request, 'An error occurred while creating the writing style.')
            return redirect('academic_writing_master')
    
    return redirect('academic_writing_master')


@login_required
@superadmin_required
def edit_writing(request, writing_id):
    """Update an existing writing style entry"""
    if request.method != 'POST':
        return redirect('academic_writing_master')
    
    writing_obj = _find_writing_by_id(writing_id)
    
    if not writing_obj:
        messages.error(request, 'Writing style not found.')
        return redirect('academic_writing_master')
    
    try:
        writing_style = request.POST.get('writing_style', '').strip()
        
        if not writing_style:
            messages.error(request, 'Writing style is required.')
            return redirect('academic_writing_master')
        
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
            return redirect('academic_writing_master')
        
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
    
    return redirect('academic_writing_master')


@login_required
@superadmin_required
def delete_writing(request, writing_id):
    """Delete a writing style entry"""
    if request.method != 'POST':
        return redirect('academic_writing_master')
    
    writing_obj = _find_writing_by_id(writing_id)
    
    if not writing_obj:
        messages.error(request, 'Writing style not found.')
        return redirect('academic_writing_master')
    
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
    
    return redirect('academic_writing_master')


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
    try:
        raw_groups = list(ProjectGroupMaster.objects.all().order_by('-created_at'))
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
                return redirect('project_group_master')
            
            # Validate prefix format (alphanumeric only)
            if not project_group_prefix.isalnum():
                messages.error(request, 'Project Group Prefix must contain only letters and numbers.')
                return redirect('project_group_master')
            
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
                return redirect('project_group_master')
            
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
            
            return redirect('project_group_master')
            
        except Exception as e:
            logger.exception(f"Error creating project group: {str(e)}")
            messages.error(request, 'An error occurred while creating the project group.')
            return redirect('project_group_master')
    
    return redirect('project_group_master')


@login_required
@superadmin_required
def edit_project_group(request, group_id):
    """Update an existing project group (Djongo-safe)"""
    if request.method != 'POST':
        return redirect('project_group_master')
    
    # Djongo-safe lookup
    all_groups = list(ProjectGroupMaster.objects.filter(id=group_id))
    group = next(
        (item for item in all_groups if not getattr(item, 'is_deleted', False)),
        None
    )
    
    if not group:
        messages.error(request, 'Project Group not found.')
        return redirect('project_group_master')
    
    try:
        project_group_name = request.POST.get('project_group_name', '').strip()
        project_group_prefix = request.POST.get('project_group_prefix', '').strip().upper()
        
        if not project_group_name or not project_group_prefix:
            messages.error(request, 'All fields are required.')
            return redirect('project_group_master')
        
        # Validate prefix format
        if not project_group_prefix.isalnum():
            messages.error(request, 'Project Group Prefix must contain only letters and numbers.')
            return redirect('project_group_master')
        
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
            return redirect('project_group_master')
        
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
    
    return redirect('project_group_master')


@login_required
@superadmin_required
def delete_project_group(request, group_id):
    """Delete a project group (Djongo-safe)"""
    if request.method != 'POST':
        return redirect('project_group_master')
    
    # Safe lookup
    group = None
    try:
        group = ProjectGroupMaster.objects.get(id=group_id)
    except ProjectGroupMaster.DoesNotExist:
        messages.error(request, 'Project Group not found.')
        return redirect('project_group_master')
    
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
    
    return redirect('project_group_master')





@login_required
@superadmin_required
def template_master(request):
    """Template Master - List all templates"""
    try:
        raw_templates = list(TemplateMaster.objects.all().order_by('-created_at'))
        templates = [
            template for template in raw_templates
            if not getattr(template, 'is_deleted', False)
        ]
        context = {
            'templates': templates,
            'total_templates': len(templates),
        }
        return render(request, 'template_master.html', context)
        
    except Exception as e:
        logger.exception(f"Error loading template master: {str(e)}")
        messages.error(request, 'Error loading templates.')
        return render(request, 'template_master.html', {
            'templates': [],
            'total_templates': 0
        })


@login_required
@superadmin_required
def create_template(request):
    """Create a new template"""
    if request.method == 'POST':
        try:
            template_name = request.POST.get('template_name', '').strip()
            template_description = request.POST.get('template_description', '').strip()
            status = request.POST.get('status', 'active')
            
            if not template_name:
                messages.error(request, 'Template name is required.')
                return redirect('template_master')
            
            # Check for existing template without triggering Djongo NOT recursion
            existing = next(
                (
                    item for item in TemplateMaster.objects.filter(template_name=template_name)
                    if not getattr(item, 'is_deleted', False)
                ),
                None
            )
            
            if existing:
                messages.error(request, f'Template "{template_name}" already exists.')
                return redirect('template_master')
            
            with transaction.atomic():
                template = TemplateMaster()
                template.template_name = template_name
                template.template_description = template_description
                template.status = status
                template.created_by = request.user
                template.created_at = timezone.now()
                
                # Set default tasks structure
                template.default_tasks = template.get_default_tasks_structure()
                
                # Set default visibility config
                template.visibility_config = {
                    'marketing': ['all'],
                    'allocator': ['all'],
                    'writer': ['task_specific'],
                    'process': ['task_specific'],
                    'superadmin': ['all'],
                    'admin': ['all']
                }
                
                template.save()
                
                log_activity_event(
                    'template.created_at',
                    subject_user=None,
                    performed_by=request.user,
                    metadata={
                        'template_id': str(template.id),
                        'template_name': template_name,
                    },
                )
                
                logger.info(f"Template '{template_name}' created by {request.user.email}")
                messages.success(request, f'Template "{template_name}" created successfully!')
            
            return redirect('template_master')
            
        except Exception as e:
            logger.exception(f"Error creating template: {str(e)}")
            messages.error(request, 'An error occurred while creating the template.')
            return redirect('template_master')
    
    return redirect('template_master')


@login_required
@superadmin_required
def edit_template(request, template_id):
    """Update an existing template"""
    if request.method != 'POST':
        return redirect('template_master')
    
    template = TemplateMaster.objects.filter(id=template_id).first()
    if template and getattr(template, 'is_deleted', False):
        template = None
    
    if not template:
        messages.error(request, 'Template not found.')
        return redirect('template_master')
    
    try:
        template_name = request.POST.get('template_name', '').strip()
        template_description = request.POST.get('template_description', '').strip()
        status = request.POST.get('status', 'active')
        
        if not template_name:
            messages.error(request, 'Template name is required.')
            return redirect('template_master')
        
        # Check for duplicate (excluding current)
        existing = next(
            (
                item for item in TemplateMaster.objects.filter(
                    template_name=template_name
                ).exclude(id=template_id)
                if not getattr(item, 'is_deleted', False)
            ),
            None
        )
        
        if existing:
            messages.error(request, f'Template "{template_name}" already exists.')
            return redirect('template_master')
        
        with transaction.atomic():
            template.template_name = template_name
            template.template_description = template_description
            template.status = status
            template.updated_by = request.user
            template.updated_at = timezone.now()
            template.save()
            
            log_activity_event(
                'template.updated_at',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'template_id': str(template.id),
                    'template_name': template_name,
                },
            )
        
        messages.success(request, f'Template "{template_name}" updated successfully.')
    
    except Exception as e:
        logger.exception(f"Error updating template: {str(e)}")
        messages.error(request, 'An error occurred while updating the template.')
    
    return redirect('template_master')


@login_required
@superadmin_required
def delete_template(request, template_id):
    """Delete a template"""
    if request.method != 'POST':
        return redirect('template_master')
    
    template = TemplateMaster.objects.filter(id=template_id).first()
    
    if not template:
        messages.error(request, 'Template not found.')
        return redirect('template_master')
    
    # Check if template is being used
    from marketing.models import Job
    jobs_using_template = Job.objects.filter(template=template).count()
    
    if jobs_using_template > 0:
        messages.error(
            request,
            f'Cannot delete template. It is currently being used by {jobs_using_template} job(s).'
        )
        return redirect('template_master')
    
    template_name_ref = template.template_name
    
    try:
        with transaction.atomic():
            template.delete()
            
            log_activity_event(
                'template.deleted',
                subject_user=None,
                performed_by=request.user,
                metadata={
                    'template_id': str(template_id),
                    'template_name': template_name_ref,
                },
            )
        
        messages.success(request, f'Template "{template_name_ref}" deleted successfully.')
    
    except Exception as e:
        logger.exception(f"Error deleting template: {str(e)}")
        messages.error(request, 'An error occurred while deleting the template.')
    
    return redirect('template_master')

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
            return redirect('manage_users')
    
    return redirect('manage_users')

# superadminpanel/views.py - Add this view function

@login_required
@superadmin_required
def change_user_password(request, user_id):
    """Change password for any user by superadmin with comprehensive validation"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('manage_users')
    
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
    
    return redirect('manage_users')


# ========================================
# SPECIALISATION MASTER VIEWS
# ========================================
@login_required
@superadmin_required
def specialisation_master(request):
    """Specialisation Master - List all specialisations"""
    try:
        raw_specialisations = list(SpecialisationMaster.objects.all().order_by('-created_at'))
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
                return redirect('specialisation_master')
            
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
                return redirect('specialisation_master')
            
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
            
            return redirect('specialisation_master')
            
        except Exception as e:
            logger.exception(f"Error creating specialisation: {str(e)}")
            messages.error(request, 'An error occurred while creating the specialisation.')
            return redirect('specialisation_master')
    
    return redirect('specialisation_master')

@login_required
@superadmin_required
def edit_specialisation(request, specialisation_id):
    """Update an existing specialisation entry"""
    if request.method != 'POST':
        return redirect('specialisation_master')
    
    specialisation_obj = _find_specialisation_by_id(specialisation_id)
    
    if not specialisation_obj:
        messages.error(request, 'Specialisation not found.')
        return redirect('specialisation_master')
    
    try:
        specialisation_name = request.POST.get('specialisation_name', '').strip()
        
        if not specialisation_name:
            messages.error(request, 'Specialisation name is required.')
            return redirect('specialisation_master')
        
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
            return redirect('specialisation_master')
        
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
    
    return redirect('specialisation_master')

@login_required
@superadmin_required
def delete_specialisation(request, specialisation_id):
    """Delete a specialisation entry"""
    if request.method != 'POST':
        return redirect('specialisation_master')
    
    specialisation_obj = _find_specialisation_by_id(specialisation_id)
    
    if not specialisation_obj:
        messages.error(request, 'Specialisation not found.')
        return redirect('specialisation_master')
    
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
    
    return redirect('specialisation_master')

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
        return redirect('manage_users')
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    # Check admin restrictions
    if request.user.role == 'admin' and user.role in ['superadmin', 'admin']:
        messages.error(request, 'You do not have permission to manage Super Admin or Admin accounts.')
        return redirect('manage_users')
    
    # Check if user is writer
    if user.role != 'writer':
        messages.error(request, 'Specialisations can only be updated for Writer role.')
        return redirect('manage_users')
    
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
    
    return redirect('manage_users')


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
    
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', 'all')
    filter_category = request.GET.get('category', 'all')

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
            mgr['total_amount'] += float(job.amount) if job.amount is not None else 0
        except Exception:
            pass
        # Target/system expected amount
        try:
            mgr['target_amount'] += float(job.system_expected_amount) if job.system_expected_amount is not None else 0
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
        if cust:
            cust_id = cust.customer_id
            cust_name = cust.customer_name
            cust_email = cust.customer_email
            cust_phone = cust.customer_phone
            cust_target = cust.targeted_amount
            cust_current = cust.current_amount
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

        if cust_id:
            cdict = mgr['customers'].setdefault(cust_id, {
                'customer_id': cust_id,
                'customer_name': cust_name or '—',
                'customer_email': cust_email or '—',
                'customer_phone': cust_phone or '—',
                'targeted_amount': float(cust_target) if cust_target not in (None, '') else 0.0,
                'current_amount': 0.0,
                'jobs': [],
                'job_amount': 0.0,
            })
            cdict['jobs'].append(job)
            try:
                amt = float(job.amount) if job.amount is not None else 0.0
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
