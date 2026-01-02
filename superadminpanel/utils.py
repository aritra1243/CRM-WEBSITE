import re

def extract_template_variables(content):
    """
    Extracts all variables in {{ variable }} format from the content.
    Returns an ORDERED list of unique variable names (preserving first occurrence order).
    """
    if not content:
        return []
    
    # Regex to find {{ variable }} or {{variable}}
    pattern = r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}'
    matches = re.findall(pattern, content)
    
    # Return ordered unique list (preserving first occurrence order)
    seen = set()
    ordered_vars = []
    for var in matches:
        if var not in seen:
            seen.add(var)
            ordered_vars.append(var)
    return ordered_vars


def get_user_field_value(user, field_name):
    """
    Tries to fetch the value of a field from the user object.
    Returns the value if found, else None.
    Handles method calls (like get_full_name) and properties.
    """
    # Comprehensive map of template variables to user model fields/methods
    FIELD_MAPPING = {
        # Name fields
        'full_name': 'get_full_name',
        'name': 'get_full_name',
        'first_name': 'first_name',
        'last_name': 'last_name',
        'employee_name': 'get_full_name',
        
        # Contact fields
        'email': 'email',
        'phone': 'phone',
        'phone_number': 'phone',
        'mobile': 'phone',
        'mobile_number': 'phone',
        'whatsapp': 'whatsapp_number',
        'whatsapp_number': 'whatsapp_number',
        'alternate_email': 'alternate_email',
        
        # Employee fields
        'employee_id': 'employee_id',
        'emp_id': 'employee_id',
        'employee_code': 'employee_id',
        
        # Organisation fields
        'organisation': 'child_organisation',
        'organization': 'child_organisation',
        'child_org_name': 'child_organisation',
        'child_organisation': 'child_organisation',
        
        # Role and Department
        'department': 'department',
        'role': 'role',
        'designation': 'role',
        
        # Salary and compensation
        'salary': 'salary',
        'monthly_salary': 'salary',
        
        # Dates
        'joining_date': 'joining_date',
        'date_joined': 'date_joined',
        'date_of_joining': 'joining_date',
        'member_since': 'date_joined',
        
        # Address
        'address': 'address',
        'user_address': 'address',
    }

    # Resolve actual attribute name
    attr_name = FIELD_MAPPING.get(field_name, field_name)
    
    if hasattr(user, attr_name):
        val = getattr(user, attr_name)
        
        # If it's a method (like get_full_name), call it
        if callable(val):
            result = val()
            return result if result else None
        
        # Return value only if not empty
        if val is not None and val != '':
            return val
        
    return None
