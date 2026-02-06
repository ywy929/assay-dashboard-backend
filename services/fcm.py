"""
Direct FCM V1 push notification service for Android.
Bypasses Expo and sends directly to Firebase Cloud Messaging.
"""
import time
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from config import settings


# Cache the OAuth2 access token (valid for 1 hour, regenerate every 50 minutes)
_token_cache = {"token": None, "generated_at": 0}

FCM_URL = f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send"


def _get_access_token() -> str:
    now = time.time()
    if _token_cache["token"] is None or (now - _token_cache["generated_at"]) > 3000:
        credentials = service_account.Credentials.from_service_account_file(
            settings.FCM_SERVICE_ACCOUNT_PATH,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"]
        )
        credentials.refresh(Request())
        _token_cache["token"] = credentials.token
        _token_cache["generated_at"] = now
    return _token_cache["token"]


def send_fcm_notification(
    device_token: str,
    title: str,
    body: str,
    data: dict = None,
    channel_id: str = "default",
) -> dict:
    """Send a push notification directly via FCM V1 API."""
    try:
        access_token = _get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # FCM data values must be strings
        str_data = {k: str(v) for k, v in (data or {}).items()}

        message = {
            "message": {
                "token": device_token,
                "notification": {
                    "title": title,
                    "body": body,
                },
                "android": {
                    "priority": "high",
                    "notification": {
                        "channel_id": channel_id,
                        "sound": "default",
                    }
                },
                "data": str_data,
            }
        }

        response = requests.post(FCM_URL, headers=headers, json=message)
        result = response.json()

        print(f"[FCM] status={response.status_code}, token={device_token[:20]}..., response={result}")

        return {"status": response.status_code, "result": result}

    except Exception as e:
        print(f"[FCM] Error sending notification: {e}")
        return {"status": 0, "error": str(e)}
