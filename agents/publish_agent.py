"""
Agente 6 — PublishAgent
Sube el video a YouTube vía Data API v3 (gratis, con cuota diaria ~6 uploads/día).

Primera vez: abre el navegador para autorizar OAuth y guarda token.json.
En servidor headless podés generar el token localmente y copiarlo.

Salida: dict {video_id, url} o {skipped: True} si faltan credenciales.
"""
from pathlib import Path

from config import settings
from pipeline.common import get_logger

log = get_logger("PublishAgent")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_service():
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    token = Path(settings.YT_TOKEN_FILE)
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.YT_CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        token.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def publish(video_path: str, metadata: dict, is_short: bool,
            force_private: bool = False) -> dict:
    if not Path(settings.YT_CLIENT_SECRETS).exists():
        log.warning("Sin client_secrets.json — salto la publicación (modo dry-run).")
        return {"skipped": True, "reason": "no_credentials"}

    from googleapiclient.http import MediaFileUpload

    youtube = _get_service()
    title = metadata["title"]
    if is_short and "#shorts" not in title.lower():
        title = f"{title} #Shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": "22",  # People & Blogs (seguro para finanzas educativas)
        },
        "status": {
            "privacyStatus": "private" if force_private else settings.YT_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }

    log.info("Subiendo '%s' (%s)...", title, settings.YT_PRIVACY_STATUS)
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response["id"]

    # thumbnail solo para videos largos
    if not is_short and metadata.get("thumbnail_path"):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(metadata["thumbnail_path"]),
            ).execute()
        except Exception as e:
            log.warning("No pude subir thumbnail: %s", e)

    url = f"https://youtube.com/watch?v={video_id}"
    log.info("Publicado: %s", url)
    return {"video_id": video_id, "url": url}
