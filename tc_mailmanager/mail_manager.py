import base64
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

from envelopes import Envelope
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Attachment,
    Category,
    Content,
    Email,
    Mail,
    Personalization,
)

if TYPE_CHECKING:
    from python_http_client.client import Response


class SendGridV3Provider:
    """Sendgrid (v3) specific code is here."""

    def __init__(self, api_key: str) -> None:
        self.sg = SendGridAPIClient(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def add_attachments(
        mail: Mail, attachments: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> Mail:
        if isinstance(attachments, dict):
            attachments = [attachments]
        for att_dict in attachments:
            attachment = Attachment()
            attachment.content = att_dict["content"]
            attachment.filename = att_dict["filename"]
            attachment.type = att_dict.get("type")
            attachment.disposition = att_dict.get("disposition")
            mail.add_attachment(attachment)
        return mail

    def create_message(self, email_attributes: Dict[str, Any]) -> Any:
        mail = Mail()
        mail.from_email = Email(email_attributes["FromEmail"], email_attributes["FromName"])
        mail.subject = email_attributes["Subject"]
        p = Personalization()
        for recipient in email_attributes["Recipients"]:
            p.add_to(Email(recipient["Email"], recipient.get("Name")))
        mail.add_personalization(p)
        for category in email_attributes.get("categories", []):
            mail.add_category(Category(category))
        # mail.add_content(Content("text/plain", "some text here"))
        mail.add_content(Content("text/html", email_attributes["Html-part"]))
        if email_attributes["Attachments"]:
            mail = self.add_attachments(mail, email_attributes["Attachments"])
        return mail.get()

    def send_message(self, message: Dict[str, Any]) -> "Response":
        pers = message["personalizations"][0]["to"]
        dest = [d["email"] for d in pers]
        self.logger.info(
            f"[sendgrid] sending email to {dest}, with categories {message.get('categories', [])}"
        )
        try:
            response = self.sg.client.mail.send.post(request_body=message)
        except Exception:
            self.logger.error("SendGridV3Provider send_message failed", exc_info=True)
            return False
        return response

    def is_successful_response(self, response: "Response") -> bool:
        """Allows to know if a message has been sucessfully sent"""
        return (response is not False) and (200 <= response.status_code <= 299)

    def get_emails(self, email_address: str, limit: int) -> Any:
        try:
            params = {
                "query": f'to_email="{email_address}"',
                "limit": limit,
            }
            res = self.sg.client.messages.get(query_params=params)
            emails = res.to_dict
            if res.status_code != 200:
                raise GetEmailException(res.body)
            return emails
        except Exception as e:
            self.logger.error("SendGridV3Provider get_emails failed", exc_info=True)
            raise e


class SMTPProvider:
    """SMTP-Provider specific code is here (this implementation uses Envelopes)"""

    def __init__(self, smtp_credentials: Dict[str, Any]) -> None:
        # Mandatory fields:
        self.smtp_host = smtp_credentials["host"]
        self.smtp_port = smtp_credentials["port"]
        self.smtp_login = smtp_credentials["login"]
        self.smtp_password = smtp_credentials["password"]

        # Optional fields:
        self.smtp_is_tls = smtp_credentials.get("tls", False)
        self.smtp_is_smtps = smtp_credentials.get("smtps", False)

        self.smtp_timeout = 30.0
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def add_attachments(
        message: Envelope, attachments: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> Envelope:
        if isinstance(attachments, dict):
            attachments = [attachments]
        for att_dict in attachments:
            # unlike sendgrid, envelopes does b64encode itself:
            content = base64.b64decode(att_dict["content"])
            # att_dict["disposition"] is not handled
            message.add_attachment(
                file_path=att_dict["filename"], data=content, mimetype=att_dict.get("type")
            )
        return message

    def create_message(self, email_attributes: Dict[str, Any]) -> Envelope:
        recipients = []
        for recipient in email_attributes["Recipients"]:
            if "Name" in recipient:
                recipients.append((recipient["Email"], recipient["Name"]))
            else:
                recipients.append(recipient["Email"])

        message = Envelope(
            from_addr=(email_attributes["FromEmail"], email_attributes["FromName"]),
            to_addr=recipients,
            subject=email_attributes["Subject"],
            html_body=email_attributes["Html-part"],
        )
        if email_attributes["Attachments"]:
            message = self.add_attachments(message, email_attributes["Attachments"])
        return message

    def send_message(self, message: Envelope) -> bool:
        dest = [(d[0] if isinstance(d, tuple) else d) for d in message.to_addr]
        self.logger.info(f"[smtp] sending email to {dest}")
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

    def is_successful_response(self, response: bool) -> bool:
        """Allows to know if a message has been sucessfully sent"""
        return response  # it's already a boolean

    def get_emails(self, email_address: str, limit: int) -> Any:
        raise NotImplementedError("SMTPProvider cannot get_emails")


class MailManager:
    """Provider-agnostic code here."""

    def __init__(
        self,
        credentials: Union[Dict[str, Any], str, None] = None,
        credentials_from_env: bool = False,
        provider: str = "sendgrid",
    ):
        self.logger = logging.getLogger(__name__)
        self.provider: Union[SendGridV3Provider, SMTPProvider]
        if provider == "sendgrid":
            self.provider = self.build_sendgrid_provider(
                cast(Optional[str], credentials), credentials_from_env
            )
        elif provider == "smtp":
            self.provider = self.build_smtp_provider(
                cast(Optional[Dict[str, Any]], credentials), credentials_from_env
            )
        else:
            raise NotImplementedError(f"unknown provider: {provider}")

    @staticmethod
    def build_sendgrid_provider(
        credentials: Optional[str], credentials_from_env: bool
    ) -> SendGridV3Provider:
        if credentials_from_env:
            credentials = os.environ["SENDGRID_API_KEY"]
        assert credentials is not None
        return SendGridV3Provider(credentials)

    @staticmethod
    def build_smtp_provider(
        credentials: Optional[Dict[str, Any]], credentials_from_env: bool
    ) -> SMTPProvider:
        if credentials_from_env:
            credentials = {
                "host": os.environ["SMTP_HOST"],
                "port": int(os.environ["SMTP_PORT"]),
                "login": os.environ["SMTP_LOGIN"],
                "password": os.environ["SMTP_PASSWORD"],
                "tls": os.environ.get("SMTP_TLS", "").lower() == "true",
                "smtps": os.environ.get("SMTP_SMTPS", "").lower() == "true",
            }
        assert credentials is not None
        return SMTPProvider(credentials)

    def send_email(self, email_attributes):
        return self.send_emails([email_attributes])[0]

    def send_emails(self, emails_attributes: List[Dict[str, Any]]) -> Any:
        emails = [self._setup_email_template(email_attrs) for email_attrs in emails_attributes]
        for email in emails:
            self._validate_email_template(email)

        messages = [self.provider.create_message(email) for email in emails]
        responses = [self.provider.send_message(msg) for msg in messages]
        total_success = all(self.provider.is_successful_response(resp) for resp in responses)

        if not total_success:
            raise SendEmailException
        return responses

    def get_emails(self, username: str, limit: int = 10) -> Any:
        return self.provider.get_emails(username, limit)

    def _setup_email_template(self, email_attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Setup some default values for email_attributes"""
        from_email = os.environ.get("TOUCAN_FROM_EMAIL") or "noreply@mail.toucantoco.com"
        from_name = os.environ.get("TOUCAN_FROM_NAME") or "Toucan Toco"

        if not email_attributes:
            raise InvalidEmailTemplateException("Missing values to setup email template")

        if os.environ.get("TOUCAN_FROM_OVERWRITE") == "enable":
            email_attributes["FromEmail"] = from_email
            email_attributes["FromName"] = from_name

        email = {
            "FromEmail": from_email,
            "FromName": from_name,
            "Subject": "",
            "Html-part": "",
            "Attachments": {},
            "Recipients": [],
        }
        email.update(email_attributes)
        return email

    def _validate_email_template(self, email_template: Dict[str, Any]) -> None:
        self._validate_email_template_empty_value(
            "Subject",
            email_template["Subject"],
        )
        self._validate_email_template_empty_value("Html-part", email_template["Html-part"])
        self._validate_email_template_recipients(email_template["Recipients"])

    def _validate_email_template_empty_value(self, field_name: str, field_content: str) -> None:
        if len(field_content) == 0 or field_content.isspace():
            raise InvalidEmailTemplateException(f'The "{field_name}" of email template is empty')

    def _validate_email_template_recipients(self, recipients: List[str]) -> None:
        if len(recipients) == 0:
            raise InvalidEmailTemplateException(
                "The email template should have at least one recipient"
            )


class InvalidEmailTemplateException(Exception):
    """Raised when an email template is invalid"""


class SendEmailException(Exception):
    """Raised when an email failed to be sent"""


class GetEmailException(Exception):
    """Raised when failing to retrieve emails"""
