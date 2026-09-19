from django.core.management.base import BaseCommand
from administration.models import (
    Department, Post, DocumentType, DocumentOrigin,
    DocumentPriority, TransitType, DocumentStatus
)


class Command(BaseCommand):
    help = 'Populate initial master data for MOP system'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting initial data population...'))

        # Create Departments
        departments = [
            {'name': 'Administration', 'remarks': 'General administration department'},
            {'name': 'Finance', 'remarks': 'Financial operations'},
            {'name': 'Human Resources', 'remarks': 'HR and personnel management'},
            {'name': 'IT', 'remarks': 'Information technology'},
        ]
        for dept_data in departments:
            dept, created = Department.objects.get_or_create(
                name=dept_data['name'],
                defaults={'remarks': dept_data['remarks']}
            )
            if created:
                self.stdout.write(f'  Created department: {dept.name}')

        # Create Posts (hierarchy based on priority)
        posts = [
            {'name': 'Secretary', 'priority': 1, 'remarks': 'Top administrative post'},
            {'name': 'Joint Secretary', 'priority': 2, 'remarks': 'Second level authority'},
            {'name': 'Deputy Secretary', 'priority': 3, 'remarks': 'Third level authority'},
            {'name': 'Under Secretary', 'priority': 4, 'remarks': 'Fourth level authority'},
            {'name': 'Section Officer', 'priority': 5, 'remarks': 'Section management'},
            {'name': 'Assistant', 'priority': 6, 'remarks': 'Assistant level'},
            {'name': 'Clerk', 'priority': 7, 'remarks': 'Clerical staff'},
        ]
        for post_data in posts:
            post, created = Post.objects.get_or_create(
                name=post_data['name'],
                defaults={'priority': post_data['priority'], 'remarks': post_data['remarks']}
            )
            if created:
                self.stdout.write(f'  Created post: {post.name} (Priority: {post.priority})')

        # Create Document Types
        doc_types = [
            'Letter', 'Memo', 'Circular', 'Proceedings', 'Endorsement',
            'Demi-Official Letter', 'Application', 'Report', 'Note'
        ]
        for doc_type in doc_types:
            obj, created = DocumentType.objects.get_or_create(name=doc_type)
            if created:
                self.stdout.write(f'  Created document type: {obj.name}')

        # Create Document Origins
        origins = ['Internal', 'External', 'Inter-Department', 'Public']
        for origin in origins:
            obj, created = DocumentOrigin.objects.get_or_create(name=origin)
            if created:
                self.stdout.write(f'  Created document origin: {obj.name}')

        # Create Document Priorities
        priorities = [
            {'name': 'Urgent', 'level': 1, 'remarks': 'Requires immediate attention'},
            {'name': 'High', 'level': 2, 'remarks': 'High priority'},
            {'name': 'Normal', 'level': 3, 'remarks': 'Normal priority'},
            {'name': 'Low', 'level': 4, 'remarks': 'Low priority'},
        ]
        for priority_data in priorities:
            obj, created = DocumentPriority.objects.update_or_create(
                name=priority_data['name'],
                defaults={
                    'level': priority_data['level'],
                    'remarks': priority_data['remarks']
                }
            )
            if created:
                self.stdout.write(f'  Created document priority: {obj.name}')
            else:
                self.stdout.write(f'  Updated document priority: {obj.name} (Level: {obj.level})')

        # Create Transit Types
        transit_types = ['Physical', 'Electronic', 'Both']
        for transit in transit_types:
            obj, created = TransitType.objects.get_or_create(name=transit)
            if created:
                self.stdout.write(f'  Created transit type: {obj.name}')

        # Create Document Statuses
        statuses = [
            'Pending', 'Under Review', 'Approved', 'Rejected',
            'Returned for Clarification', 'Forwarded', 'Closed'
        ]
        for status in statuses:
            obj, created = DocumentStatus.objects.get_or_create(name=status)
            if created:
                self.stdout.write(f'  Created document status: {obj.name}')

        self.stdout.write(self.style.SUCCESS('\nInitial data population completed successfully!'))
        self.stdout.write(self.style.WARNING('\nNext steps:'))
        self.stdout.write('  1. Create a superuser: python manage.py createsuperuser')
        self.stdout.write('  2. Assign the Secretary post to the superuser via admin panel')
        self.stdout.write('  3. Start creating users and files through the application')
