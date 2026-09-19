from django.test import TestCase, Client
from django.urls import reverse

from administration.models import CustomUser, Post, Department

from .models import Conversation, Message
from .permissions import can_message_user, can_view_conversation
from .services import get_or_create_conversation, send_message, get_total_unread_count


class MessagingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        dept = Department.objects.create(name='Test Dept')
        post_high = Post.objects.create(name='Secretary', priority=1.0)
        post_low = Post.objects.create(name='Clerk', priority=7.0)
        cls.admin = CustomUser.objects.create_user(
            username='admin_msg',
            password='test1234',
            post=post_high,
        )
        cls.staff = CustomUser.objects.create_user(
            username='staff_msg',
            password='test1234',
            post=post_low,
        )

    def test_create_conversation_and_send(self):
        conv, created = get_or_create_conversation(self.admin, self.staff, self.admin)
        self.assertTrue(created)
        conv2, created2 = get_or_create_conversation(self.staff, self.admin, self.staff)
        self.assertFalse(created2)
        self.assertEqual(conv.id, conv2.id)

        send_message(conv, self.admin, 'Hello staff')
        self.assertEqual(Message.objects.filter(conversation=conv).count(), 1)
        self.assertEqual(get_total_unread_count(self.staff), 1)
        self.assertEqual(get_total_unread_count(self.admin), 0)

    def test_permissions(self):
        conv, _ = get_or_create_conversation(self.admin, self.staff)
        self.assertTrue(can_view_conversation(self.admin, conv))
        self.assertTrue(can_view_conversation(self.staff, conv))
        self.assertTrue(can_message_user(self.admin, self.staff))
        self.assertFalse(can_message_user(self.admin, self.admin))

    def test_inbox_requires_login(self):
        client = Client()
        resp = client.get(reverse('messaging_inbox'))
        self.assertEqual(resp.status_code, 302)

    def test_inbox_authenticated(self):
        client = Client()
        client.login(username='admin_msg', password='test1234')
        resp = client.get(reverse('messaging_inbox'))
        self.assertEqual(resp.status_code, 200)
