from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import Response

from backend.src.config import config

ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_BYTES = 5 * 1024 * 1024


async def read_image(upload: UploadFile) -> tuple[bytes, str, str]:
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нужен файл JPEG, PNG или WebP",
        )
    data = await upload.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пустой файл",
        )
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл больше 5 МБ",
        )
    return data, content_type, ALLOWED_TYPES[content_type]


def photo_key(folder: str, ext: str) -> str:
    return f"{folder}/{uuid4()}.{ext}"


async def save_photo(s3_client, key: str, data: bytes, content_type: str) -> str:
    if s3_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище фото недоступно",
        )
    await s3_client.put_object(
        Bucket=config.s3.BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


async def load_photo(s3_client, key: str | None) -> Response:
    if not key or s3_client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )
    try:
        obj = await s3_client.get_object(
            Bucket=config.s3.BUCKET_NAME,
            Key=key,
        )
        body = await obj["Body"].read()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )
    media = obj.get("ContentType") or "image/jpeg"
    return Response(
        content=body,
        media_type=media,
        headers={"Cache-Control": "public, max-age=86400"},
    )


async def delete_photo(s3_client, key: str | None) -> None:
    if not key or s3_client is None:
        return
    try:
        await s3_client.delete_object(
            Bucket=config.s3.BUCKET_NAME,
            Key=key,
        )
    except Exception:
        return
