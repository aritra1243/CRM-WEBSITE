import os
import django
import random
import datetime
from datetime import datetime as dt_class # Safety check for imports

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM_WEBSITE.settings')
django.setup()

from superadminpanel.models import LetterTemplate, OrganisationMaster
from accounts.models import CustomUser
from superadminpanel.utils import extract_template_variables, get_user_field_value

def debug_form_logic():
    print("--- Starting Granuarl Debug ---")
    
    # 1. Test LetterTemplate Fetch
    print("1. Fetching first LetterTemplate safe...")
    try:
        all_templates = list(LetterTemplate.objects.all())
        if not all_templates:
            print("   No templates found.")
            return
        t_id = all_templates[0].id
        print(f"   Got ID: {t_id}")
        
        print("2. Testing LetterTemplate.objects.get(id=...)")
        t = LetterTemplate.objects.get(id=t_id)
        print("   Success!")
        template_content = t.template_content
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    # 2. Test CustomUser Fetch
    print("3. Fetching first CustomUser safe...")
    try:
        all_users = list(CustomUser.objects.all())
        if not all_users:
            print("   No users found.")
            return
        u_id = all_users[0].id
        print(f"   Got ID: {u_id}")
        
        print("4. Testing CustomUser.objects.get(id=...)")
        u = CustomUser.objects.get(id=u_id)
        print("   Success!")
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    # 3. Test Organisation Fetch (The suspect)
    print("5. Testing OrganisationMaster.objects.filter(...)")
    try:
         child_orgs = list(OrganisationMaster.objects.filter(org_type='child', is_active=True).values_list('organisation_name', flat=True))
         print(f"   Success! Count: {len(child_orgs)}")
    except Exception as e:
        print(f"   FAILED: {e}")
        # Don't return, as this is try-excepted in view

    # 4. Test Variable Logic
    print("6. Testing Variable Logic")
    from superadminpanel.views import extract_template_variables
    try:
        # We need a proper extraction simulation
        vars = extract_template_variables(template_content)
        print(f"   Vars: {vars}")
        
        from datetime import datetime
        import random
        val = f"LT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        print(f"   Date gen success: {val}")
    except Exception as e:
        print(f"   FAILED logic: {e}")
        import traceback
        traceback.print_exc()

    print("--- Debug Complete ---")

if __name__ == '__main__':
    debug_form_logic()
