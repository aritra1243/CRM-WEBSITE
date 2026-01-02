import os
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from marketing.models import Job, JobAttachment
from accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Sync attachment files from disk to database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job-id',
            type=str,
            help='Sync attachments for a specific job (system_id)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        job_id = options.get('job_id')
        
        media_root = 'media'
        job_attachments_dir = os.path.join(media_root, 'job_attachments')
        
        if not os.path.exists(job_attachments_dir):
            self.stdout.write(self.style.ERROR(f'Directory not found: {job_attachments_dir}'))
            return
        
        # Get a default user for uploaded_by
        try:
            default_user = CustomUser.objects.filter(role='marketing').first()
            if not default_user:
                default_user = CustomUser.objects.first()
        except:
            default_user = None
        
        if not default_user:
            self.stdout.write(self.style.ERROR('No users found in database'))
            return
        
        synced_count = 0
        skipped_count = 0
        
        # If specific job ID provided, only sync that job
        if job_id:
            job_dirs = [job_id]
        else:
            job_dirs = os.listdir(job_attachments_dir)
        
        for job_dir in job_dirs:
            job_path = os.path.join(job_attachments_dir, job_dir)
            
            if not os.path.isdir(job_path):
                continue
            
            # Get the job
            try:
                job = Job.objects.get(system_id=job_dir)
            except Job.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Job not found: {job_dir}'))
                continue
            
            # Get existing attachment filenames in DB
            existing_files = set(job.attachments.values_list('original_filename', flat=True))
            
            # Scan directory for files
            files_in_dir = os.listdir(job_path)
            
            for filename in files_in_dir:
                file_path = os.path.join(job_path, filename)
                
                if not os.path.isfile(file_path):
                    continue
                
                if filename in existing_files:
                    self.stdout.write(f'  [OK] {job_dir}/{filename} (already in DB)')
                    skipped_count += 1
                    continue
                
                # Create attachment record
                try:
                    file_size = os.path.getsize(file_path)
                    # The relative path should be relative to MEDIA_ROOT
                    relative_path = os.path.join('job_attachments', job_dir, filename).replace('\\', '/')
                    
                    if dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(f'[DRY RUN] Would create attachment for: {job_dir}/{filename}')
                        )
                    else:
                        attachment = JobAttachment.objects.create(
                            job=job,
                            file=relative_path,
                            original_filename=filename,
                            file_size=file_size,
                            uploaded_by=default_user,
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f'[+] Created: {job_dir}/{filename} (ID: {attachment.id})')
                        )
                    
                    synced_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'[-] Error creating attachment for {filename}: {str(e)}')
                    )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'=== SYNC COMPLETE ==='))
        self.stdout.write(f'Synced: {synced_count}')
        self.stdout.write(f'Skipped: {skipped_count}')
        if dry_run:
            self.stdout.write(self.style.WARNING('(DRY RUN - no changes made)'))
