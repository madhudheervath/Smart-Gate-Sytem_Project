import hmac
import hashlib
import time
from settings import settings

def make_qr_token(pass_id: int, user_id: int, ttl_minutes: int = None) -> tuple[str, int]:
    ttl = ttl_minutes or settings.QR_TTL_MINUTES
    exp = int(time.time()) + ttl*60
    data = f"{pass_id}.{user_id}.{exp}"
    sig = hmac.new(settings.SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{data}.{sig}", exp

def parse_token(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 4:
            return None
        pid, uid, exp, sig = parts
        return int(pid), int(uid), int(exp), sig
    except Exception:
        return None

