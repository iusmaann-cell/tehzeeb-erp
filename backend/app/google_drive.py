"""
Bill photo storage via Google Drive.

Why Drive and not local disk or the database: local disk on Render's free web
service is wiped on every redeploy, and the database isn't a good place to store
a growing library of photos (bloats backups, hits free-tier storage limits fast).
Drive is external to both, free at a scale that comfortably covers years of bill
photos, and survives the eventual move to Oracle Cloud with zero changes needed
here.

TWO CREDENTIAL MODES — pick based on your Google account type:

MODE A — OAuth as yourself (personal Gmail accounts — the common case)
  Service accounts have NO storage quota of their own on a personal Gmail
  account (Google will reject uploads with "storageQuotaExceeded" even though
  the account and folder both exist and are shared correctly). The fix is to
  authorize the app as yourself once, so uploads use your own Drive's quota.

  One-time setup:
  1. In Google Cloud Console (console.cloud.google.com), for the same project
     used for the Drive API: APIs & Services -> Credentials -> Create Credentials
     -> OAuth client ID -> Application type: "Desktop app". Note the Client ID
     and Client Secret it gives you.
  2. Go to https://developers.google.com/oauthplayground
  3. Click the gear/settings icon (top right) -> check "Use your own OAuth
     credentials" -> paste in the Client ID and Client Secret from step 1.
  4. In the left panel, find "Drive API v3" and select the scope
     https://www.googleapis.com/auth/drive
  5. Click "Authorize APIs" and sign in with your own Google account (the one
     that owns the bill-photos folder) -> allow access.
  6. Click "Exchange authorization code for tokens" -> copy the Refresh token
     shown (a long string) — this does not expire until you revoke access.
  7. Set three environment variables on the backend:
     - GOOGLE_OAUTH_CLIENT_ID = the Client ID from step 1
     - GOOGLE_OAUTH_CLIENT_SECRET = the Client Secret from step 1
     - GOOGLE_OAUTH_REFRESH_TOKEN = the refresh token from step 6
     - GOOGLE_DRIVE_FOLDER_ID = the bill-photos folder's ID (unchanged from
       before — no need to re-share it with anything, it's already yours)

MODE B — Service account (only works on paid Google Workspace, using a Shared
Drive — personal Gmail accounts cannot create Shared Drives at all)
  1. Create a Shared Drive in Google Drive, share it with the service account's
     email (Content Manager access), and point GOOGLE_DRIVE_FOLDER_ID at a
     folder inside that Shared Drive.
  2. Set GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON to the full contents of the service
     account's downloaded JSON key.

If OAuth env vars (Mode A) are present, they take priority; the service-account
path (Mode B) is used only as a fallback.
"""
import os
import io
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _get_oauth_credentials():
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        return None
    # No access token supplied — google-auth fetches one automatically on first
    # use via the refresh token, and keeps refreshing it as needed after that.
    return OAuthCredentials(
        None, refresh_token=refresh_token, token_uri=TOKEN_URI,
        client_id=client_id, client_secret=client_secret, scopes=SCOPES,
    )


def _get_service_account_credentials():
    json_content = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
    if json_content:
        info = json.loads(json_content)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    json_file = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE")
    if json_file and os.path.exists(json_file):
        return service_account.Credentials.from_service_account_file(json_file, scopes=SCOPES)

    return None


def _get_credentials():
    return _get_oauth_credentials() or _get_service_account_credentials()


def is_configured() -> bool:
    return _get_credentials() is not None and bool(os.getenv("GOOGLE_DRIVE_FOLDER_ID"))


def upload_bill_photo(file_bytes: bytes, filename: str, mime_type: str) -> dict:
    """
    Uploads a photo to the configured Drive folder and makes it viewable via link
    (so it can be displayed/opened from the app without embedding Drive credentials
    on the frontend). Returns {"file_id": ..., "view_url": ...}.
    """
    creds = _get_credentials()
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not creds or not folder_id:
        raise RuntimeError(
            "Google Drive isn't configured on this server yet. Set either the "
            "GOOGLE_OAUTH_* variables (personal Gmail) or GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON "
            "(Google Workspace + Shared Drive) plus GOOGLE_DRIVE_FOLDER_ID — see "
            "backend/app/google_drive.py for setup steps."
        )

    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    file_metadata = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    uploaded = service.files().create(
        body=file_metadata, media_body=media, fields="id, webViewLink",
        supportsAllDrives=True,
    ).execute()

    # Anyone with the link can view — needed so the photo can be opened directly
    # from the app without proxying through our own server or embedding credentials.
    service.permissions().create(
        fileId=uploaded["id"], body={"role": "reader", "type": "anyone"},
        supportsAllDrives=True,
    ).execute()

    return {
        "file_id": uploaded["id"],
        "view_url": uploaded.get("webViewLink") or f"https://drive.google.com/file/d/{uploaded['id']}/view",
    }
