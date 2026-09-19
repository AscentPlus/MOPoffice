from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from administration.models import Post, Department, DocumentType, DocumentOrigin, DocumentPriority, DocumentStatus
from filetracking.models import FileMaster, FileAction, FileMovement
from filetracking.forms import FileActionForm

User = get_user_model()

class ExternalProcessingTest(TestCase):
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
        self.status_processing = DocumentStatus.objects.create(name='Processing')

        # Create File
        self.file = FileMaster.objects.create(
            subject='Govt Grant Approval Request',
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

    def test_form_action_choices_for_processing(self):
        # When file is pending, Acknowledge Return is not in choices
        form_pending = FileActionForm(user=self.clerk, file_status='Pending')
        action_choices_pending = dict(form_pending.fields['action_type'].choices)
        self.assertIn('EXTERNAL', action_choices_pending)
        self.assertNotIn('ACK_RETURN', action_choices_pending)

        # When file is processing, ONLY Acknowledge Return is allowed
        form_processing = FileActionForm(user=self.clerk, file_status='Processing')
        action_choices_processing = dict(form_processing.fields['action_type'].choices)
        self.assertNotIn('EXTERNAL', action_choices_processing)
        self.assertIn('ACK_RETURN', action_choices_processing)

    def test_send_to_external_workflow(self):
        # 1. Login as Clerk (current holder)
        self.client.login(username='clerk', password='password')

        # Action URL
        url = reverse('file_detail', kwargs={'file_id': self.file.id})

        # Post action EXTERNAL with remarks
        response = self.client.post(url, {
            'action_type': 'EXTERNAL',
            'remarks': 'Forwarded to Govt for validation and sanction.'
        })

        # Assert redirection to dashboard
        self.assertRedirects(response, reverse('dashboard'))

        # Fetch updated file details
        self.file.refresh_from_db()

        # Assert status changed and holder details remain the clerk
        self.assertEqual(self.file.current_status.name, 'Processing')
        self.assertEqual(self.file.current_holder, self.clerk_post)
        self.assertEqual(self.file.current_user, self.clerk)

        # Assert FileAction record is created
        latest_action = FileAction.objects.filter(file=self.file).latest('action_at')
        self.assertEqual(latest_action.action_type, 'EXTERNAL')
        self.assertEqual(latest_action.action_by, self.clerk)
        self.assertEqual(latest_action.remarks, 'Forwarded to Govt for validation and sanction.')

        # Assert custody-retaining movement registered
        latest_movement = FileMovement.objects.filter(file=self.file).latest('moved_at')
        self.assertEqual(latest_movement.from_post, self.clerk_post)
        self.assertEqual(latest_movement.to_post, self.clerk_post)
        self.assertEqual(latest_movement.to_user, self.clerk)
        self.assertEqual(latest_movement.remarks, 'SENT FOR EXTERNAL/GOVERNMENT APPROVAL: Forwarded to Govt for validation and sanction.')
        self.assertFalse(latest_movement.action_required)

        # Assert file vanishes from active inbox list
        inbox_response = self.client.get(reverse('inbox'))
        self.assertNotContains(inbox_response, self.file.file_number)

        # Assert file does not count in admin summary dashboard pending counts
        self.client.login(username='secretary', password='password') # priority is 1.0 (admin)
        summary_response = self.client.get(reverse('summary_dashboard'))
        self.assertContains(summary_response, '0') # Clerk should show 0 pending files

    def test_acknowledge_return_workflow(self):
        # 1. Move file to Processing status first
        self.file.current_status = self.status_processing
        self.file.save()

        # 2. Login as Clerk (current holder)
        self.client.login(username='clerk', password='password')

        # Action URL
        url = reverse('file_detail', kwargs={'file_id': self.file.id})

        # Post action ACK_RETURN with remarks
        response = self.client.post(url, {
            'action_type': 'ACK_RETURN',
            'remarks': 'File returned with approved stamp. Resuming internal process.'
        })

        # Assert redirection back to file_detail page.
        self.assertRedirects(response, url)

        # Fetch updated file details
        self.file.refresh_from_db()

        # Assert status restored to Pending
        self.assertEqual(self.file.current_status.name, 'Pending')
        self.assertEqual(self.file.current_holder, self.clerk_post)
        self.assertEqual(self.file.current_user, self.clerk)

        # Assert FileAction record is created
        latest_action = FileAction.objects.filter(file=self.file).latest('action_at')
        self.assertEqual(latest_action.action_type, 'ACK_RETURN')
        self.assertEqual(latest_action.action_by, self.clerk)
        self.assertEqual(latest_action.remarks, 'File returned with approved stamp. Resuming internal process.')

        # Assert movement registered as action_required=True (so it goes into active workflow inbox)
        latest_movement = FileMovement.objects.filter(file=self.file).latest('moved_at')
        self.assertEqual(latest_movement.from_post, self.clerk_post)
        self.assertEqual(latest_movement.to_post, self.clerk_post)
        self.assertEqual(latest_movement.to_user, self.clerk)
        self.assertEqual(latest_movement.remarks, 'ACKNOWLEDGED RETURN FROM GOVT: File returned with approved stamp. Resuming internal process.')
        self.assertTrue(latest_movement.action_required)

        # Assert file reappears in active inbox
        inbox_response = self.client.get(reverse('inbox'))
        self.assertContains(inbox_response, self.file.file_number)

    def test_track_file_date_defaults(self):
        from django.utils import timezone
        current_ym = timezone.now().strftime('%Y-%m')

        # 1. Login as Secretary
        self.client.login(username='secretary', password='password')

        # 2. Get track_file view without params
        response = self.client.get(reverse('track_file'))

        # 3. Assert search_date context variable defaults to current month/year
        self.assertEqual(response.context['search_date'], current_ym)

        # 4. Assert response contains our default file (since it was created today/current month)
        self.assertContains(response, self.file.file_number)

    def test_summary_dashboard_processing_files_listing(self):
        # Move file to Processing status via EXTERNAL action
        self.client.login(username='clerk', password='password')
        self.client.post(reverse('file_detail', kwargs={'file_id': self.file.id}), {
            'action_type': 'EXTERNAL',
            'remarks': 'Dispatched to Finance Department for review.'
        })

        # Login as Secretary (Admin)
        self.client.login(username='secretary', password='password')
        response = self.client.get(reverse('summary_dashboard'))

        # Assert context contains processing_files and processing_count
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['processing_count'], 1)
        self.assertEqual(len(response.context['processing_files']), 1)
        
        proc_item = response.context['processing_files'][0]
        self.assertEqual(proc_item['file'], self.file)
        self.assertEqual(proc_item['sent_by_user'], self.clerk)
        self.assertEqual(proc_item['narration'], 'Dispatched to Finance Department for review.')

        # Assert HTML contains the file number, subject, and sender
        self.assertContains(response, self.file.file_number)
        self.assertContains(response, 'Govt Grant Approval Request')
        self.assertContains(response, 'Dispatched to Finance Department for review.')
        self.assertContains(response, 'Files Under External / Government Processing')


