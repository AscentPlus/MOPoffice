from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from administration.models import Post, Department, DocumentType, DocumentOrigin, DocumentPriority, DocumentStatus
from filetracking.models import FileMaster, FileShare

User = get_user_model()

class FileVisibilityTest(TestCase):
    def setUp(self):
        # Create Posts
        self.secretary_post = Post.objects.create(name='Secretary', priority=1)
        self.clerk_post = Post.objects.create(name='Clerk', priority=3)

        # Create Users
        self.secretary = User.objects.create_user(username='secretary', password='password', post=self.secretary_post)
        self.clerk1 = User.objects.create_user(username='clerk1', password='password', post=self.clerk_post)
        self.clerk2 = User.objects.create_user(username='clerk2', password='password', post=self.clerk_post)

        # Create Metadata
        self.dept = Department.objects.create(name='Admin')
        self.dtype = DocumentType.objects.create(name='Letter')
        self.origin = DocumentOrigin.objects.create(name='Internal')
        self.priority = DocumentPriority.objects.create(name='Normal')
        self.status = DocumentStatus.objects.create(name='Pending')

        # Create File
        self.file = FileMaster.objects.create(
            subject='Visibility Test File',
            department=self.dept,
            document_type=self.dtype,
            document_origin=self.origin,
            document_priority=self.priority,
            current_holder=self.secretary_post,
            created_by=self.secretary,
            current_status=self.status
        )

        self.client = Client()

    def test_viewer_visibility_in_inbox(self):
        # 1. Forward file to Clerk 1 (Action Taker) and CC to Clerk Post (View Only)
        self.client.login(username='secretary', password='password')
        
        # Share with Clerk 2 specifically
        FileShare.objects.create(
            file=self.file, 
            shared_with=self.clerk_post, 
            shared_with_user=self.clerk2,
            shared_by=self.secretary
        )
        
        # Forward to Clerk 1
        self.file.current_holder = self.clerk_post
        self.file.current_user = self.clerk1
        self.file.save()

        # 2. Check Clerk 1's inbox (Action Taker)
        self.client.login(username='clerk1', password='password')
        response = self.client.get(reverse('inbox'))
        self.assertContains(response, self.file.file_number)

        # 3. Check Clerk 2's inbox (Viewer/CC)
        # Clerk 2 is in the same post as Clerk 1. 
        # Previously, Clerk 2 wouldn't see it because it was assigned to Clerk 1 specifically.
        self.client.login(username='clerk2', password='password')
        response = self.client.get(reverse('inbox'))
        self.assertContains(response, self.file.file_number)
        
        # 4. Close the file
        self.file.is_closed = True
        self.file.save()
        
        # 5. Verify it disappears from both inboxes
        self.client.login(username='clerk1', password='password')
        response = self.client.get(reverse('inbox'))
        self.assertNotContains(response, self.file.file_number)
        
        self.client.login(username='clerk2', password='password')
        response = self.client.get(reverse('inbox'))
        self.assertNotContains(response, self.file.file_number)

        # 6. Verify it is still searchable in track_file for Clerk 2
        response = self.client.get(reverse('track_file') + f'?search={self.file.file_number}')
        self.assertContains(response, self.file.file_number)
