# coding: utf-8

from __future__ import unicode_literals
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
            attachment_attrs = email_attributes['Attachments']
            attachment = Attachment()
            attachment.set_content(attachment_attrs['content'])
            attachment.set_filename(attachment_attrs['filename'])
            attachment.set_type(attachment_attrs.get('type'))
            attachment.set_disposition(attachment_attrs.get('disposition'))
            mail.add_attachment(attachment)
        return mail.get()  # type(mail.get()) -> dict

    def send_message(self, message):
        try:
            response = self.sg.client.mail.send.post(request_body=message)
        except:
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
            attachment_attrs = email_attributes['Attachments']
            # unlike sendgrid, envelopes does b64encode itself:
            content = base64.b64decode(attachment_attrs['content'])
            # attachment_attrs["disposition"] is not handled
            message.add_attachment(
                file_path=attachment_attrs['filename'],
                data=content,
                mimetype=attachment_attrs.get('type')
            )
        return message  # type(message) -> Envelope object

    def send_message(self, message):
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
        except:
            self.logger.error("SMTPProvider send_message failed", exc_info=True)
            return False
        else:
            return True  # not much details about the success

    def is_successful_response(self, response):
        """Allows to know if a message has been sucessfully sent"""
        return response  # it's already a boolean


class MailManager(object):
    """Provider-agnostic code here."""

    def __init__(self, credentials=None, provider='sendgrid'):
        self.logger = logging.getLogger(__name__)

        if provider == 'sendgrid':
            self.provider = SendGridV3Provider(credentials)
        elif provider == 'smtp':
            self.provider = SMTPProvider(credentials)
        else:
            raise NotImplementedError("unknown provider: {}".format(provider))

    def send_email(self, email_attributes):
        email = self._setup_email_template(email_attributes)
        self._validate_email_template(email)

        message = self.provider.create_message(email)
        response = self.provider.send_message(message)
        is_success = self.provider.is_successful_response(response)

        if not is_success:
            raise SendEmailException
        return response

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
            'FromEmail': 'noreply@mail.toucantoco.com',
            'FromName': 'Toucan Toco',
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
