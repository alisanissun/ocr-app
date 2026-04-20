import os
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import pytesseract
from PIL import Image
import shutil

app = FastAPI(title="OCR Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 永久儲存目錄（會掛載到 VM 固定路徑）
STORAGE_BASE = Path(os.getenv("STORAGE_PATH", "/app/storage"))
UPLOADS_DIR = STORAGE_BASE / "uploads"
RESULTS_DIR = STORAGE_BASE / "results"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


def validate_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.get("/health")
async def health_check():
    return {"status": "ok", "storage": str(STORAGE_BASE)}


@app.post("/ocr")
async def process_ocr(file: UploadFile = File(...)):
    if not validate_image(file.filename):
        raise HTTPException(status_code=400, detail="不支援的檔案格式，請上傳 JPG/PNG/BMP/TIFF 圖片")

    job_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{job_id[:8]}"

    # 儲存上傳的圖片
    img_ext = Path(file.filename).suffix.lower()
    img_filename = f"{safe_name}{img_ext}"
    img_path = UPLOADS_DIR / img_filename

    try:
        with open(img_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"圖片儲存失敗: {str(e)}")

    # 執行 OCR
    try:
        image = Image.open(img_path)
        # 嘗試繁體中文 + 英文，若失敗則純英文
        try:
            ocr_text = pytesseract.image_to_string(image, lang="chi_tra+eng")
        except Exception:
            try:
                ocr_text = pytesseract.image_to_string(image, lang="chi_sim+eng")
            except Exception:
                ocr_text = pytesseract.image_to_string(image, lang="eng")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR 辨識失敗: {str(e)}")

    # 儲存辨識結果 TXT
    txt_filename = f"{safe_name}_result.txt"
    txt_path = RESULTS_DIR / txt_filename
    result_content = (
        f"=== OCR 辨識結果 ===\n"
        f"原始檔案: {file.filename}\n"
        f"辨識時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Job ID: {job_id}\n"
        f"{'='*40}\n\n"
        f"{ocr_text}\n"
    )
    txt_path.write_text(result_content, encoding="utf-8")

    # 建立 ZIP（含圖片 + txt）
    zip_filename = f"{safe_name}_package.zip"
    zip_path = RESULTS_DIR / zip_filename
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(img_path, img_filename)
        zf.write(txt_path, txt_filename)

    return JSONResponse({
        "job_id": job_id,
        "original_filename": file.filename,
        "ocr_text": ocr_text,
        "txt_file": txt_filename,
        "zip_file": zip_filename,
        "img_file": img_filename,
    })


@app.get("/download/zip/{filename}")
async def download_zip(filename: str):
    # 安全性：只允許下載 results 目錄內的 zip
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="非法檔名")
    file_path = RESULTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="檔案不存在")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip"
    )


@app.get("/download/txt/{filename}")
async def download_txt(filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="非法檔名")
    file_path = RESULTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="檔案不存在")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="text/plain; charset=utf-8"
    )


@app.get("/list")
async def list_jobs():
    """列出所有已處理的工作"""
    results = []
    for zip_file in sorted(RESULTS_DIR.glob("*_package.zip"), reverse=True):
        results.append({
            "zip_file": zip_file.name,
            "size_kb": round(zip_file.stat().st_size / 1024, 1),
            "created": datetime.fromtimestamp(zip_file.stat().st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        })
    return {"total": len(results), "jobs": results}