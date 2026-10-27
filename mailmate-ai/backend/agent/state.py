from typing import TypedDict

class EmailState(TypedDict, total=False):
    question: str
    recipient_name: str
    recipient_email: str
    mail_reason: str
    subject: str
    body: str
    response: str
