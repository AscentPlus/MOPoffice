from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from administration.models import Post, Department, DocumentType, DocumentOrigin, DocumentPriority, DocumentStatus
from filetracking.models import FileMaster, FileAction, FileMovement

User = get_user_model()

class KeepInFileTest(TestCase):
    def setUp(self):
        # Create Posts
        self.secretary_post = Post.objects.create(name='Secretary', priority=1.0)
        self.clerk_post = Post.objects.create(name='Clerk', priority=3.0)

        # Create Users
        self.secretary = User.objects.create_user(username='secretary', password='password', post=self.secretary_post)
        self.clerk = User.objects.create_user(username='clerk', password='password', post=self.clerk_post)

        # Create Metadata
        self.dept = Department.objects.create(name='Admin')
        self.dtype = DocumentType.objects.create(name='Letter')
        self.origin = DocumentOrigin.objects.create(name='Internal')
        self.priority = DocumentPriority.objects.create(name='Normal')
        self.status_pending = DocumentStatus.objects.create(name='Pending')

        # Create File
        self.file = FileMaster.objects.create(
            subject='Design Draft File',
            department=self.dept,
            document_type=self.dtype,
            document_origin=self.origin,
            document_priority=self.priority,
            current_holder=self.clerk_post,
            current_user=self.clerk,
            created_by=self.secretary,
            current_status=self.status_pending
        )

        self.client = Client()

    def test_action_choices_contain_keep_in_file(self):
        # Assert choice exists in choices list
        choices = dict(FileAction.ACTION_CHOICES)
        self.assertIn('KEEP_IN_FILE', choices)
        self.assertEqual(choices['KEEP_IN_FILE'], 'Keep in File')

    def test_keep_in_file_action_processing(self):
        # Login as Clerk (current holder)
        self.client.login(username='clerk', password='password')

        # Action URL
        url = reverse('file_detail', kwargs={'file_id': self.file.id})

        # Post action KEEP_IN_FILE with narration/remarks
        response = self.client.post(url, {
            'action_type': 'KEEP_IN_FILE',
            'remarks': 'Keeping this file locally to complete administrative review.'
        })

        # Assert redirection to keep_in_files list
        self.assertRedirects(response, reverse('keep_in_files'))

        # Fetch updated file
        self.file.refresh_from_db()

        # Assert status changed and holder details remain unchanged
        self.assertEqual(self.file.current_status.name, 'Keep in File')
        self.assertEqual(self.file.current_holder, self.clerk_post)
        self.assertEqual(self.file.current_user, self.clerk)

        # Assert FileAction record is created
        latest_action = FileAction.objects.filter(file=self.file).latest('action_at')
        self.assertEqual(latest_action.action_type, 'KEEP_IN_FILE')
        self.assertEqual(latest_action.action_by, self.clerk)
        self.assertEqual(latest_action.remarks, 'Keeping this file locally to complete administrative review.')

        # Assert movement path gets 1 custody-retaining movement step
        movement_count = FileMovement.objects.filter(file=self.file).count()
        self.assertEqual(movement_count, 1)

        latest_movement = FileMovement.objects.filter(file=self.file).latest('moved_at')
        self.assertEqual(latest_movement.from_post, self.clerk_post)
        self.assertEqual(latest_movement.to_post, self.clerk_post)
        self.assertEqual(latest_movement.to_user, self.clerk)
        self.assertEqual(latest_movement.remarks, 'Keeping this file locally to complete administrative review.')

        # Assert file vanishes from the clerk's inbox
        inbox_response = self.client.get(reverse('inbox'))
        self.assertNotContains(inbox_response, self.file.file_number)

    def test_keep_in_file_requires_narration(self):
        # Login as Clerk
        self.client.login(username='clerk', password='password')
        url = reverse('file_detail', kwargs={'file_id': self.file.id})

        # Post request without remarks (missing narration)
        response = self.client.post(url, {
            'action_type': 'KEEP_IN_FILE',
            'remarks': ''
        })

        # Assert form error as remarks/narration is required
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('remarks', form.errors)

    def test_keep_in_file_visibility_scoping(self):
        # 1. Clerk marks as Keep in File
        self.client.login(username='clerk', password='password')
        url = reverse('file_detail', kwargs={'file_id': self.file.id})
        self.client.post(url, {
            'action_type': 'KEEP_IN_FILE',
            'remarks': 'Held for assessment.'
        })

        # 2. Login as a third-party Clerk's post user
        clerk2_post = Post.objects.create(name='Accounts Clerk', priority=3.0)
        clerk2 = User.objects.create_user(username='clerk2', password='password', post=clerk2_post)
        
        self.client.login(username='clerk2', password='password')
        response = self.client.get(reverse('keep_in_files'))
        # Clerk 2 is not the holder, they should not see it
        self.assertNotContains(response, self.file.file_number)

        # 3. Login as Secretary. They are NOT the holder, so they should NOT see it in their keep_in_files list either!
        self.client.login(username='secretary', password='password')
        response = self.client.get(reverse('keep_in_files'))
        self.assertNotContains(response, self.file.file_number)

