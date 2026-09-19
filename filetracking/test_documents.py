from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from administration.models import Post, Department, DocumentType, DocumentOrigin, DocumentPriority, DocumentStatus
from filetracking.models import FileMaster, FileDocument, FileAction

User = get_user_model()

class DocumentStorageTest(TestCase):
    def setUp(self):
        self.post = Post.objects.create(name='Secretary', priority=1)
        self.user = User.objects.create_user(username='testuser', password='password', post=self.post)
        self.dept = Department.objects.create(name='Admin')
        self.dtype = DocumentType.objects.create(name='Letter')
        self.origin = DocumentOrigin.objects.create(name='Internal')
        self.priority = DocumentPriority.objects.create(name='Normal')
        self.status = DocumentStatus.objects.create(name='Pending')
        
        self.client = Client()
        self.client.login(username='testuser', password='password')

    def test_create_file_with_binary_document(self):
        # Create a dummy file
        content = b"This is a test document content"
        test_file = SimpleUploadedFile("test.txt", content, content_type="text/plain")
        
        response = self.client.post(reverse('create_file'), {
            'subject': 'Test Subject',
            'department': self.dept.id,
            'document_type': self.dtype.id,
            'document_origin': self.origin.id,
            'document_priority': self.priority.id,
            'remarks': 'Test remarks',
            'attachment': [test_file]
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify document is in DB
        doc = FileDocument.objects.first()
        self.assertIsNotNone(doc)
        self.assertEqual(bytes(doc.content), content)
        self.assertEqual(doc.file_name, "test.txt")
        self.assertEqual(doc.mimetype, "text/plain")
        
        # Test Download
        download_url = reverse('download_document', args=[doc.id])
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)
        self.assertEqual(response['Content-Type'], "text/plain")
        self.assertIn('inline; filename="test.txt"', response['Content-Disposition'])

    def test_attach_document_during_forward(self):
        # 1. Create file first
        file_obj = FileMaster.objects.create(
            subject='Initial File',
            department=self.dept,
            document_type=self.dtype,
            document_origin=self.origin,
            document_priority=self.priority,
            current_holder=self.post,
            created_by=self.user,
            current_status=self.status
        )
        
        # 2. Forward with attachment
        content = b"Action attachment content"
        test_file = SimpleUploadedFile("action.pdf", content, content_type="application/pdf")
        
        # Create another post to forward to
        other_post = Post.objects.create(name='JS', priority=2)
        other_user = User.objects.create_user(username='other', password='pass', post=other_post)
        
        response = self.client.post(reverse('file_detail', args=[file_obj.id]), {
            'action_type': 'FORWARD',
            'assignee': f'user_{other_user.id}',
            'remarks': 'Forwarding with extra doc',
            'action_attachment': [test_file],
            'action_attachment_description': 'Forwarding attachment'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify document linking
        action = FileAction.objects.filter(action_type='FORWARD').first()
        doc = FileDocument.objects.filter(action=action).first()
        
        self.assertIsNotNone(doc)
        self.assertEqual(bytes(doc.content), content)
        self.assertEqual(doc.file_name, "action.pdf")
        self.assertEqual(doc.action, action)
        self.assertEqual(doc.description, "Forwarding attachment")
