import os, json, uuid, shutil
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import fitz

from backend import store
from backend.engine import status as model_status, run_ocr

BASE = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE / "data" / "uploads"
RESULT_DIR = BASE / "data" / "results"
FRONTEND_DIR = BASE / "frontend"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Dots OCR Local", version="0.1.0")
store.init_db()
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

@app.get("/", response_class=HTMLResponse)
def home():
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "app": "Dots OCR Local",
        "device": "CPU",
        "model": model_status(),
        "time": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/jobs")
def jobs():
    return store.list_jobs()

@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    item = store.get_job(job_id)
    if not item:
        raise HTTPException(404, "کار پیدا نشد")
    return item

@app.post("/api/documents")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, "فرمت فایل پشتیبانی نمی‌شود")
    job_id = uuid.uuid4().hex
    safe_name = Path(file.filename or "document").name
    saved = UPLOAD_DIR / f"{job_id}_{safe_name}"
    with saved.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    store.create_job(job_id, safe_name, str(saved.relative_to(BASE)))
    background_tasks.add_task(process_document, job_id, str(saved), suffix)
    return {"id": job_id, "filename": safe_name, "status": "queued"}

def process_document(job_id: str, saved_path: str, suffix: str):
    try:
        store.update_job(job_id, status="processing", progress=1)
        pages = []
        if suffix == ".pdf":
            pdf = fitz.open(saved_path)
            max_pages = int(os.getenv("MAX_PDF_PAGES", "10"))
            if len(pdf) > max_pages:
                raise RuntimeError(f"این نسخه حداکثر {max_pages} صفحه از PDF را پردازش می‌کند.")
            dpi = int(os.getenv("PDF_DPI", "140"))
            for index, page in enumerate(pdf):
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
                page_path = RESULT_DIR / f"{job_id}_page_{index+1}.png"
                pix.save(page_path)
                text = run_ocr(str(page_path))
                pages.append({"page": index+1, "text": text})
                store.update_job(job_id, progress=int((index+1)/len(pdf)*95))
            pdf.close()
        else:
            text = run_ocr(saved_path)
            pages.append({"page": 1, "text": text})
            store.update_job(job_id, progress=95)

        result = {
            "id": job_id,
            "filename": Path(saved_path).name,
            "pages": pages,
            "text": "\n\n".join(f"--- صفحه {p['page']} ---\n{p['text']}" for p in pages)
        }
        json_path = RESULT_DIR / f"{job_id}.json"
        md_path = RESULT_DIR / f"{job_id}.md"
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text("# نتیجه OCR\n\n" + result["text"], encoding="utf-8")
        store.update_job(job_id, status="completed", progress=100,
                         result_json=json.dumps(result, ensure_ascii=False), error=None)
    except Exception as exc:
        store.update_job(job_id, status="failed", error=str(exc), progress=100)

@app.get("/api/jobs/{job_id}/export/{kind}")
def export_result(job_id: str, kind: str):
    if kind not in {"json", "md"}:
        raise HTTPException(400, "فرمت خروجی نامعتبر است")
    path = RESULT_DIR / f"{job_id}.{kind}"
    if not path.exists():
        raise HTTPException(404, "خروجی هنوز آماده نیست")
    return FileResponse(path, filename=f"dots_ocr_{job_id}.{kind}")
