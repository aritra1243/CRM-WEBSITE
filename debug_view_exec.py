import os
import django
import random
# Mirroring views.py imports exactly
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM_WEBSITE.settings')
django.setup()

from superadminpanel.models import LetterTemplate, OrganisationMaster
from accounts.models import CustomUser
from superadminpanel.utils import extract_template_variables, get_user_field_value

def debug_view_execution():
    print("--- Starting View Execution Simulation ---")
    
    # 1. Fetch Template
    template = LetterTemplate.objects.filter(is_deleted=False).first()
    if not template:
        print("No template found.")
        return
    
    # 2. Fetch User
    user = CustomUser.objects.filter(is_active=True).first()
    if not user:
        print("No user found.")
        return
        
    print(f"Template: {template.id}")
    print(f"User: {user.id}")

    # 3. Simulate View Logic
    try:
        # Extract variables
        variables = extract_template_variables(template.template_content)
        print(f"Variables: {variables}")
        
        # Helper for special fields
        try:
             # Fetch All strategy
             all_orgs = list(OrganisationMaster.objects.all())
             child_orgs = [o.organisation_name for o in all_orgs if o.org_type == 'child' and o.is_active]
             mother_orgs = [o.organisation_name for o in all_orgs if o.org_type == 'mother' and o.is_active]
             print(f"Child Orgs: {len(child_orgs)}")
        except Exception as e:
             print(f"Error fetching orgs: {e}")
             child_orgs = []
             mother_orgs = []

        designations = ['Writer', 'Admin', 'Allocator', 'Process', 'Marketing']
        
        auto_filled_fields = []
        manual_fields = []
        
        for var in variables:
            print(f"Processing: {var}")
            if var == 'letter_id':
                # Exact line from views.py
                val = f"LT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
                print(f"  Generated ID: {val}")
                auto_filled_fields.append({
                    'name': var,
                    'value': val,
                    'label': 'Letter ID (Auto)',
                    'readonly': True
                })
                continue
                
            if var == 'child_org_name':
                manual_fields.append({
                    'name': var,
                    'label': 'Child Organisation',
                    'type': 'select',
                    'choices': child_orgs
                })
                continue

            if var == 'mother_org_name':
                manual_fields.append({
                    'name': var,
                    'label': 'Mother Organisation',
                    'type': 'select',
                    'choices': mother_orgs
                })
                continue

            if var == 'designation':
                manual_fields.append({
                    'name': var,
                    'label': 'Designation',
                    'type': 'select',
                    'choices': designations
                })
                continue

            # Default logic
            val = get_user_field_value(user, var)
            if val is not None:
                auto_filled_fields.append({
                    'name': var,
                    'value': val,
                    'label': var.replace('_', ' ').title()
                })
            else:
                manual_fields.append({
                    'name': var,
                    'label': var.replace('_', ' ').title(),
                    'type': 'text' 
                })
                
        print("Success! Context prepared.")
        
    except Exception as e:
        print(f"CRITICAL EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_view_execution()
