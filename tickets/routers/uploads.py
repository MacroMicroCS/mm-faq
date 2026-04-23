"""Attachment upload for ticket replies."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from tickets.auth import get_current_agent

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent.parent / "static" / "uploads" / "tickets"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf", ".txt", ".csv", ".xlsx", ".docx", ".zip"}
MAX_SIZE_MB = 10


@router.post("/api/upload/attachment")
async def upload_attachment(
    file: UploadFile = File(...),
    agent=Depends(get_current_agent),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支援的檔案格式: {ext}")

    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"檔案過大（上限 {MAX_SIZE_MB}MB）")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / filename
    path.write_bytes(content)

    return JSONResponse({
        "ok": True,
        "filename": file.filename,
        "stored_name": filename,
        "url": f"/static/uploads/tickets/{filename}",
        "size": len(content),
        "content_type": file.content_type,
    })
