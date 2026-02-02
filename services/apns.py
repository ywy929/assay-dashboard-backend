import time
import httpx
from jose import jwt
from config import settings


# Cache the JWT token (valid for 1 hour, regenerate every 50 minutes)
_token_cache = {"token": None, "generated_at": 0}


def _generate_jwt() -> str:
    with open(settings.APNS_KEY_PATH, "r") as f:
        private_key = f.read()

    headers = {"alg": "ES256", "kid": settings.APNS_KEY_ID}
    payload = {"iss": settings.APNS_TEAM_ID, "iat": int(time.time())}

    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] is None or (now - _token_cache["generated_at"]) > 3000:
        _token_cache["token"] = _generate_jwt()
        _token_cache["generated_at"] = now
    return _token_cache["token"]


def _get_base_url() -> str:
    if settings.APNS_USE_SANDBOX:
        return "https://api.sandbox.push.apple.com"
    return "https://api.push.apple.com"


def send_apns_alert(
    device_token: str,
    title: str,
    body: str,
    data: dict = None,
    collapse_id: str = None,
) -> dict:
    """
    Send a visible push notification via APNs HTTP/2.
    Sets apns-collapse-id so retraction can replace it later.
    """
    try:
        token = _get_token()
        url = f"{_get_base_url()}/3/device/{device_token}"

        headers = {
            "authorization": f"bearer {token}",
            "apns-topic": settings.APNS_BUNDLE_ID,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }
        if collapse_id:
            headers["apns-collapse-id"] = collapse_id

        payload = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
            },
        }
        if data:
            payload.update(data)

        with httpx.Client(http2=True) as client:
            response = client.post(url, json=payload, headers=headers)

        result = {
            "status": response.status_code,
            "reason": response.text,
            "apns_id": response.headers.get("apns-id"),
        }
        print(f"APNs alert: status={response.status_code}, collapse_id={collapse_id}, apns_id={result['apns_id']}")
        if response.status_code != 200:
            print(f"APNs alert error: {result}")
        return result

    except Exception as e:
        print(f"Error sending APNs alert: {e}")
        return {"status": 0, "error": str(e)}


def send_apns_silent(
    device_token: str,
    collapse_id: str,
    data: dict = None,
) -> dict:
    """
    Send a silent/background push via APNs HTTP/2 with the same collapse-id.
    APNs replaces the original notification server-side — since this has no
    alert content, the notification effectively disappears.
    """
    try:
        token = _get_token()
        url = f"{_get_base_url()}/3/device/{device_token}"

        headers = {
            "authorization": f"bearer {token}",
            "apns-topic": settings.APNS_BUNDLE_ID,
            "apns-push-type": "background",
            "apns-priority": "5",
            "apns-collapse-id": collapse_id,
        }

        payload = {
            "aps": {
                "content-available": 1,
            },
        }
        if data:
            payload.update(data)

        with httpx.Client(http2=True) as client:
            response = client.post(url, json=payload, headers=headers)

        result = {
            "status": response.status_code,
            "reason": response.text,
            "apns_id": response.headers.get("apns-id"),
        }
        print(f"APNs silent: status={response.status_code}, collapse_id={collapse_id}, apns_id={result['apns_id']}")
        if response.status_code != 200:
            print(f"APNs silent error: {result}")
        return result

    except Exception as e:
        print(f"Error sending APNs silent push: {e}")
        return {"status": 0, "error": str(e)}
