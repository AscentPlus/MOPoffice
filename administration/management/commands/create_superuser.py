"""
Script to create the first superuser (Secretary) for the MOP system

This script helps create the initial admin user with the Secretary post.
Run this after populating initial data.
"""

from django.core.management.base import BaseCommand
from administration.models import CustomUser, Post
from django.db import transaction


class Command(BaseCommand):
    help = 'Create initial superuser with Secretary post'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\n=== MOP System - Create Superuser ===\n'))

        # Check if Secretary post exists
        try:
            secretary_post = Post.objects.get(priority=1, name='Secretary')
        except Post.DoesNotExist:
            self.stdout.write(self.style.ERROR('Error: Secretary post not found!'))
            self.stdout.write('Please run: python manage.py populate_initial_data first')
            return

        # Check if superuser already exists
        if CustomUser.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING('A superuser already exists!'))
            response = input('Do you want to create another superuser? (yes/no): ')
            if response.lower() != 'yes':
                self.stdout.write('Cancelled.')
                return

        # Get user input
        self.stdout.write('\nEnter superuser details:\n')
        username = input('Username: ').strip()
        
        if not username:
            self.stdout.write(self.style.ERROR('Username cannot be empty!'))
            return

        # Check if username exists
        if CustomUser.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'Username "{username}" already exists!'))
            return

        first_name = input('First name: ').strip()
        last_name = input('Last name: ').strip()
        email = input('Email (optional): ').strip()
        mobile = input('Mobile (optional): ').strip()
        
        # Password
        import getpass
        while True:
            password = getpass.getpass('Password: ')
            password2 = getpass.getpass('Password (again): ')
            
            if password != password2:
                self.stdout.write(self.style.ERROR('Passwords do not match. Try again.'))
                continue
            
            if len(password) < 4:
                self.stdout.write(self.style.ERROR('Password too short. Minimum 4 characters.'))
                continue
            
            break

        # Create superuser
        try:
            with transaction.atomic():
                user = CustomUser.objects.create_superuser(
                    username=username,
                    password=password,
                    email=email or '',
                    first_name=first_name,
                    last_name=last_name,
                    post=secretary_post,
                    mobile=mobile or None,
                )
                
                self.stdout.write(self.style.SUCCESS('\n✓ Superuser created successfully!'))
                self.stdout.write(f'\nUser Details:')
                self.stdout.write(f'  Username: {user.username}')
                self.stdout.write(f'  User ID: {user.user_id}')
                self.stdout.write(f'  Name: {user.get_full_name()}')
                self.stdout.write(f'  Post: {user.post.name}')
                self.stdout.write(f'  Email: {user.email}')
                
                self.stdout.write(self.style.SUCCESS('\nYou can now login at: http://localhost:8000/'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nError creating superuser: {str(e)}'))
