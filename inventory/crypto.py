import secrets
from cryptography.fernet import Fernet
from django.conf import settings

def encrypt(value):
    return Fernet(settings.CREDENTIAL_KEY.encode()).encrypt(value.encode()).decode()

def decrypt(value):
    return Fernet(settings.CREDENTIAL_KEY.encode()).decrypt(value.encode()).decode()

def new_password():
    return secrets.token_urlsafe(32) + "aA1!"
