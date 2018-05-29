# coding: utf-8

from __future__ import unicode_literals
import os
import base64
import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Personalization, Content, Attachment

from envelopes import Envelope


class SendGridV3Provider(object):
    """Sendgrid (v3) specific code is here."""

    def __init__(self, api_key):
        self.sg = SendGridAPIClient(apikey=api_key)
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def add_attachments(mail, attachments):
        attachments = [attachments] if isinstance(attachments, dict) else attachments
        for att_dict in attachments:
            attachment = Attachment()
            attachment.set_content(att_dict['content'])
            attachment.set_filename(att_dict['filename'])
            attachment.set_type(att_dict.get('type'))
            attachment.set_disposition(att_dict.get('disposition'))
            mail.add_attachment(attachment)
        return mail

    def create_message(self, email_attributes):
        mail = Mail()
        mail.set_from(Email(email_attributes['FromEmail'], email_attributes['FromName']))
        mail.set_subject(email_attributes['Subject'])
        p = Personalization()
        for recipient in email_attributes['Recipients']:
            p.add_to(Email(recipient['Email'], recipient.get('Name')))
        mail.add_personalization(p)
        # mail.add_content(Content("text/plain", "some text here"))
        mail.add_content(Content("text/html", email_attributes['Html-part']))
        if email_attributes['Attachments']:
            mail = self.add_attachments(mail, email_attributes['Attachments'])
        return mail.get()  # type(mail.get()) -> dict

    def send_message(self, message):
        pers = message['personalizations'][0]['to']
        dest = [d['email'] for d in pers]
        self.logger.info("[sendgrid] sending email to {}".format(dest))
        try:
            response = self.sg.client.mail.send.post(request_body=message)
        except Exception:
            self.logger.error("SendGridV3Provider send_message failed", exc_info=True)
            return False
        return response  # type(response) -> python_http_client.client.Response

    def is_successful_response(self, response):
        """Allows to know if a message has been sucessfully sent"""
        return (response is not False) and (200 <= response.status_code <= 299)


class SMTPProvider(object):
    """SMTP-Provider specific code is here (this implementation uses Envelopes)"""

    def __init__(self, smtp_credentials):
        # Mandatory fields:
        self.smtp_host = smtp_credentials['host']
        self.smtp_port = smtp_credentials['port']
        self.smtp_login = smtp_credentials['login']
        self.smtp_password = smtp_credentials['password']

        # Optional fields:
        self.smtp_is_tls = smtp_credentials.get('tls', False)
        self.smtp_is_smtps = smtp_credentials.get('smtps', False)

        self.smtp_timeout = 30.0
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def add_attachments(message, attachments):
        attachments = [attachments] if isinstance(attachments, dict) else attachments
        for att_dict in attachments:
            # unlike sendgrid, envelopes does b64encode itself:
            content = base64.b64decode(att_dict['content'])
            # att_dict["disposition"] is not handled
            message.add_attachment(
                file_path=att_dict['filename'],
                data=content,
                mimetype=att_dict.get('type')
            )
        return message

    def create_message(self, email_attributes):
        recipients = []
        for recipient in email_attributes['Recipients']:
            if 'Name' in recipient:
                recipients.append((recipient['Email'], recipient['Name']))
            else:
                recipients.append(recipient['Email'])

        message = Envelope(
            from_addr=(email_attributes['FromEmail'], email_attributes['FromName']),
            to_addr=recipients,
            subject=email_attributes['Subject'],
            html_body=email_attributes['Html-part'],
        )
        if email_attributes['Attachments']:
            message = self.add_attachments(message, email_attributes['Attachments'])
        return message  # type(message) -> Envelope object

    def send_message(self, message):
        dest = [d[0] for d in message.to_addr]
        self.logger.info("[smtp] sending email to {}".format(dest))
        try:
            conn, send_result = message.send(
                host=self.smtp_host,
                port=self.smtp_port,
                login=self.smtp_login,
                password=self.smtp_password,
                tls=self.smtp_is_tls,
                smtps=self.smtp_is_smtps,
                timeout=self.smtp_timeout,
            )
        except Exception:
            self.logger.error("SMTPProvider send_message failed", exc_info=True)
            return False
        else:
            return True  # not much details about the success

    def is_successful_response(self, response):
        """Allows to know if a message has been sucessfully sent"""
        return response  # it's already a boolean


class MailManager(object):
    """Provider-agnostic code here."""

    def __init__(self, credentials=None, credentials_from_env=False, provider='sendgrid'):
        self.logger = logging.getLogger(__name__)
        if provider == 'sendgrid':
            self.provider = self.build_sendgrid_provider(credentials, credentials_from_env)
        elif provider == 'smtp':
            self.provider = self.build_smtp_provider(credentials, credentials_from_env)
        else:
            raise NotImplementedError("unknown provider: {}".format(provider))

    @staticmethod
    def build_sendgrid_provider(credentials, credentials_from_env):
        if credentials_from_env:
            credentials = os.environ['SENDGRID_API_KEY']
        return SendGridV3Provider(credentials)

    @staticmethod
    def build_smtp_provider(credentials, credentials_from_env):
        if credentials_from_env:
            credentials = {
                'host': os.environ['SMTP_HOST'],
                'port': int(os.environ['SMTP_PORT']),
                'login': os.environ['SMTP_LOGIN'],
                'password': os.environ['SMTP_PASSWORD'],
                'tls': os.environ.get('SMTP_TLS', '').lower() == 'true',
                'smtps': os.environ.get('SMTP_SMTPS', '').lower() == 'true',
            }
        return SMTPProvider(credentials)

    def send_email(self, email_attributes):
        return self.send_emails([email_attributes])[0]

    def send_emails(self, emails_attributes):
        emails = [self._setup_email_template(email_attrs) for email_attrs in emails_attributes]
        [self._validate_email_template(email) for email in emails]

        messages = [self.provider.create_message(email) for email in emails]
        responses = [self.provider.send_message(msg) for msg in messages]
        total_success = all(self.provider.is_successful_response(resp) for resp in responses)

        if not total_success:
            raise SendEmailException
        return responses

    def _setup_email_template(self, email_attributes):
        """Setup some default values for email_attributes"""
        if not email_attributes:
            raise InvalidEmailTemplateException('Missing values to setup email template')
        email = {
            'FromEmail': os.environ.get('TOUCAN_FROM_EMAIL') or 'noreply@mail.toucantoco.com',
            'FromName': os.environ.get('TOUCAN_FROM_NAME') or 'Toucan Toco',
            'Subject': '',
            'Html-part': '',
            'Attachments': {},
            'Recipients': []
        }
        email.update(email_attributes)
        return email

    def _validate_email_template(self, email_template):
        self._validate_email_template_empty_value('Subject', email_template['Subject'], )
        self._validate_email_template_empty_value('Html-part', email_template['Html-part'])
        self._validate_email_template_recipients(email_template['Recipients'])

    def _validate_email_template_empty_value(self, field_name, field_content):
        if len(field_content) == 0 or field_content.isspace():
            raise InvalidEmailTemplateException('The "{}" of email template is empty'.format(field_name))

    def _validate_email_template_recipients(self, recipients):
        if len(recipients) == 0:
            raise InvalidEmailTemplateException('The email template should have at least one recipient')


class InvalidEmailTemplateException(Exception):
    """Raised when an email template is invalid"""


class SendEmailException(Exception):
    """Raised when an email failed to be sent"""
