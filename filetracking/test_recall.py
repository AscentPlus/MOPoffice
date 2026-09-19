from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from administration.models import Post, Department, DocumentType, DocumentOrigin, DocumentPriority, DocumentStatus
from filetracking.models import FileMaster, FileMovement, FileAction

User = get_user_model()

class FileRecallTest(TestCase):
    def setUp(self):
        # Create Posts
        self.dept_manager_post = Post.objects.create(name='Dept Manager', priority=2)
        self.clerk_post = Post.objects.create(name='Clerk', priority=3)

        # Create Users
        self.manager = User.objects.create_user(username='manager', password='password', post=self.dept_manager_post)
        self.clerk = User.objects.create_user(username='clerk', password='password', post=self.clerk_post)

        # Create Metadata
        self.dept = Department.objects.create(name='Admin')
        self.dtype = DocumentType.objects.create(name='Letter')
        self.origin = DocumentOrigin.objects.create(name='Internal')
        self.priority = DocumentPriority.objects.create(name='Normal')
        self.status = DocumentStatus.objects.create(name='Pending')

        # Create File
        self.file = FileMaster.objects.create(
            subject='Recall Test File',
            department=self.dept,
            document_type=self.dtype,
            document_origin=self.origin,
            document_priority=self.priority,
            current_holder=self.dept_manager_post,
            created_by=self.manager,
            current_status=self.status,
            current_user=self.manager
        )

        self.client = Client()

    def get_message_texts(self, response):
        return [m.message for m in response.context['messages']]

    def test_successful_recall(self):
        """Test recall within 24h before any action"""
        self.client.login(username='manager', password='password')
        
        # Manually create movement since POST simulation might be tricky with form init
        movement = FileMovement.objects.create(
            file=self.file,
            from_post=self.dept_manager_post,
            to_post=self.clerk_post,
            moved_by=self.manager,
            moved_at=timezone.now()
        )
        self.file.current_holder = self.clerk_post
        self.file.current_user = self.clerk
        self.file.save()

        # Create corresponding FORWARD action (needed for CC cleanup logic)
        FileAction.objects.create(
            file=self.file,
            post=self.dept_manager_post,
            action_type='FORWARD',
            remarks='Forwarded',
            action_by=self.manager
        )
        
        # Recall
        response = self.client.get(reverse('recall_file', args=[movement.id]), follow=True)
        self.assertContains(response, "successfully recalled")
        
        # Verify state
        self.file.refresh_from_db()
        movement.refresh_from_db()
        self.assertEqual(self.file.current_holder, self.dept_manager_post)
        self.assertEqual(self.file.current_user, self.manager)
        self.assertTrue(movement.is_recalled)
        
        # Verify history action
        self.assertTrue(FileAction.objects.filter(file=self.file, action_type='RECALL').exists())

    def test_recall_exceed_24h_fails(self):
        """Test recall failing after 24 hours"""
        self.client.login(username='manager', password='password')
        
        movement = FileMovement.objects.create(
            file=self.file,
            from_post=self.dept_manager_post,
            to_post=self.clerk_post,
            moved_by=self.manager
        )
        # Bypassing auto_now_add with update()
        FileMovement.objects.filter(id=movement.id).update(
            moved_at=timezone.now() - timedelta(hours=25)
        )
        self.file.current_holder = self.clerk_post
        self.file.save()

        response = self.client.get(reverse('recall_file', args=[movement.id]), follow=True)
        self.assertContains(response, "Recall period (24 hours) has expired")
        
        self.file.refresh_from_db()
        self.assertEqual(self.file.current_holder, self.clerk_post)

    def test_recall_after_receiver_action_fails(self):
        """Test recall failing if receiver already took an action"""
        self.client.login(username='manager', password='password')
        
        # Movement
        movement = FileMovement.objects.create(
            file=self.file,
            from_post=self.dept_manager_post,
            to_post=self.clerk_post,
            moved_by=self.manager,
            moved_at=timezone.now()
        )
        self.file.current_holder = self.clerk_post
        self.file.save()
        
        # Receiver takes action
        FileAction.objects.create(
            file=self.file,
            post=self.clerk_post,
            action_type='APPROVE',
            remarks='Agreed',
            action_by=self.clerk,
            action_at = timezone.now() + timedelta(seconds=1)
        )
        
        response = self.client.get(reverse('recall_file', args=[movement.id]), follow=True)
        self.assertContains(response, "The receiver has already taken an action")

    def test_unauthorized_recall(self):
        """Test that other users cannot recall a movement they didn't send"""
        movement = FileMovement.objects.create(
            file=self.file,
            from_post=self.dept_manager_post,
            to_post=self.clerk_post,
            moved_by=self.manager
        )
        
        self.client.login(username='clerk', password='password')
        response = self.client.get(reverse('recall_file', args=[movement.id]), follow=True)
        self.assertContains(response, "You are not authorized")
