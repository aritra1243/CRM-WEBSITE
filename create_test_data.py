import os
import sys
import django
from django.utils import timezone

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM_WEBSITE.settings')
django.setup()

from accounts.models import CustomUser
from marketing.models import Job
from common.pymongo_utils import pymongo_create_user, pymongo_create

def create_test_data():
    # 1. Create a Writer
    writer_email = 'testwriter@example.com'
    if not CustomUser.objects.filter(email=writer_email).exists():
        print(f"Creating writer: {writer_email}")
        writer = pymongo_create_user(
            CustomUser,
            email=writer_email,
            username='testwriter',
            first_name='Test',
            last_name='Writer',
            role='writer',
            approval_status='approved',
            is_approved=True,
            password='Password123!',
            employee_id='WRIT001'
        )
        print(f"Writer created: {writer.id}")
    else:
        writer = CustomUser.objects.get(email=writer_email)
        print("Writer already exists.")

    # 2. Create a Job for the writer
    print("Creating test job...")
    job = pymongo_create(
        Job,
        system_id='JOB-TEST-001',
        job_id='JT001',
        topic='Test Dissertation',
        category='Dissertation',
        status='in_progress',
        word_count=2000,
        amount=1500,
        allocated_to_id=writer.id,
        created_at=timezone.now(),
        deadline=timezone.now() + timezone.timedelta(days=5)
    )
    print(f"Job created: {job.id}")

if __name__ == "__main__":
    create_test_data()
