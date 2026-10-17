from pathlib import Path
import secrets
from cryptography.fernet import Fernet
root = Path(__file__).resolve().parent.parent
if not (root / ".env").exists():
    (root / ".env").write_text("DJANGO_SECRET_KEY=" + secrets.token_urlsafe(48) + "\nCREDENTIAL_KEY=" + Fernet.generate_key().decode() + "\nDEBUG=1\nALLOWED_HOSTS=localhost,127.0.0.1\nTIME_ZONE=Asia/Shanghai\nCELERY_BROKER_URL=filesystem://\n", encoding="utf-8")
    print("Created local .env; back up its encryption key securely.")
else:
    print("Existing .env preserved.")
