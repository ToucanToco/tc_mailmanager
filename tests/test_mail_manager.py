# coding: utf-8

from collections import namedtuple
from unittest import TestCase
from mock import MagicMock

from tc_mailmanager import MailManager, InvalidEmailTemplateException


class MailManagerTest(TestCase):

    @classmethod
    def setUpClass(cls):
        credentials = "test"
        cls.mail_manager = MailManager(credentials)
        cls.successful_response = namedtuple('Rep', ['status_code'])(202)

    def test_send_email(self):
        """
        It should send email with email provider(mailjet)
        """
        email_attributes = {
            'Subject': 'Test email',
            'Html-part': 'Test content',
            'Recipients': [{'Email': 'test@toucantoco.com'}]
        }

        self.mail_manager.provider.send_message = MagicMock(return_value=self.successful_response)
        resp = self.mail_manager.send_email(email_attributes)
        self.assertEqual(resp, self.successful_response)

    def test_validate_email_template_empty_value(self):
        field_name, field_content = 'Subject', 'Want some viagra ?'
        ret = self.mail_manager._validate_email_template_empty_value(field_name, field_content)
        self.assertIsNone(ret)

        # empty subject field:
        field_name, field_content = 'Subject', ''
        with self.assertRaises(InvalidEmailTemplateException):
            self.mail_manager._validate_email_template_empty_value(field_name, field_content)

        # only blank characters in subject field
        field_name, field_content = 'Subject', ' \n  '
        with self.assertRaises(InvalidEmailTemplateException):
            self.mail_manager._validate_email_template_empty_value(field_name, field_content)
