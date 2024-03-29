import os
from collections import namedtuple

import pytest
from envelopes import Envelope

from tc_mailmanager import InvalidEmailTemplateException, MailManager
from tc_mailmanager.mail_manager import SendGridV3Provider, SMTPProvider

Response = namedtuple("Response", ["status_code"])


@pytest.fixture(scope="module")
def mail_manager() -> MailManager:
    credentials = "test"
    return MailManager(credentials)


@pytest.fixture(scope="module")
def successful_response() -> Response:
    return Response(202)


@pytest.fixture
def email_with_attachments():
    return {
        "FromEmail": "noreply@toucantoco.com",
        "FromName": "Toucan Toco",
        "Subject": "Toucan Toco - Take a look !",
        "Html-part": "<h1>html part</h1>",
        "Attachments": [
            {
                "filename": "screenshot.png",
                "content": b"QA==",
                "type": "image/png",
                "disposition": "attachment",
            },
            {
                "filename": "screenshot_bis.png",
                "content": b"QA==",
                "type": "image/png",
                "disposition": "attachment",
            },
        ],
        "Recipients": [
            {"Email": "test1@toucantoco.com", "Name": "Test"},
            {"Email": "test2@toucantoco.com"},
        ],
    }


@pytest.fixture
def email_with_categories():
    return {
        "FromEmail": "noreply@toucantoco.com",
        "FromName": "Toucan Toco",
        "Subject": "Toucan Toco - Take a look !",
        "Html-part": "<h1>html part</h1>",
        "Attachments": None,
        "Recipients": [
            {"Email": "test1@toucantoco.com", "Name": "Test"},
            {"Email": "test2@toucantoco.com"},
        ],
        "categories": ["my_instance", "my_small_app", "lala.mynotif"],
    }


def test_sendgrid_provider(email_with_attachments):
    provider = SendGridV3Provider(api_key="foo")
    msg = provider.create_message(email_with_attachments)

    assert isinstance(msg, dict)
    pers = msg["personalizations"][0]["to"]
    dest = [d["email"] for d in pers]
    assert dest == ["test1@toucantoco.com", "test2@toucantoco.com"]


def test_sendgrid_provider_category(email_with_categories):
    provider = SendGridV3Provider(api_key="foo")
    msg = provider.create_message(email_with_categories)

    assert isinstance(msg, dict)
    pers = msg["personalizations"][0]["to"]
    dest = [d["email"] for d in pers]
    assert dest == ["test1@toucantoco.com", "test2@toucantoco.com"]
    assert msg["categories"] == ["my_instance", "my_small_app", "lala.mynotif"]


def test_smtp_provider(mail_manager, email_with_attachments):
    provider = SMTPProvider(
        smtp_credentials={"host": "localhost", "port": 25, "login": "", "password": ""}
    )
    msg = provider.create_message(mail_manager._setup_email_template(email_with_attachments))

    assert isinstance(msg, Envelope)
    dest = [(d[0] if isinstance(d, tuple) else d) for d in msg.to_addr]
    assert dest == ["test1@toucantoco.com", "test2@toucantoco.com"]


def test_send_email(mocker, mail_manager, successful_response):
    mocker.patch.object(mail_manager.provider, "send_message").return_value = successful_response
    email_attributes = {
        "Subject": "Test email",
        "Html-part": "Test content",
        "Recipients": [{"Email": "test@toucantoco.com"}],
    }

    resp = mail_manager.send_email(email_attributes)
    assert resp == successful_response


def test_validate_email_template_empty_value(mail_manager):
    field_name, field_content = "Subject", "Want some viagra ?"
    ret = mail_manager._validate_email_template_empty_value(field_name, field_content)
    assert ret is None

    # empty subject field:
    field_name, field_content = "Subject", ""
    with pytest.raises(InvalidEmailTemplateException):
        mail_manager._validate_email_template_empty_value(field_name, field_content)

    # only blank characters in subject field
    field_name, field_content = "Subject", " \n  "
    with pytest.raises(InvalidEmailTemplateException):
        mail_manager._validate_email_template_empty_value(field_name, field_content)


def test_setup_email_template(mail_manager):
    ret = mail_manager._setup_email_template({"FromEmail": "a@b.com", "FromName": "a"})
    assert ret["FromEmail"] == "a@b.com"
    assert ret["FromName"] == "a"

    os.environ["TOUCAN_FROM_OVERWRITE"] = "enable"
    ret = mail_manager._setup_email_template({"FromEmail": "a@b.com", "FromName": "a"})
    assert ret["FromEmail"] == "noreply@mail.toucantoco.com"
    assert ret["FromName"] == "Toucan Toco"
