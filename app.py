import os
import sys
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlalchemy.orm import Session
import uvicorn

sys.path.append(str(Path(__file__).parent.parent))

from src.web.database import get_db, init_db
from src.web.models import ProcessingJob
from src.data_processing import DataReader, DataParser, TableBuilder

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agro Data Processing System", version="2.0")

BASE_DIR = Path("src/web")
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
UPLOAD_DIR = BASE_DIR.parent.parent / "uploads"
OUTPUT_DIR = BASE_DIR.parent.parent / "outputs"

STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.on_event("startup")
async def startup_event():
    init_db()
    logger.info("База данных инициализирована")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):

    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/upload")
async def upload_files(
    files: List[UploadFile] = File(...), db: Session = Depends(get_db)
):

    try:

        job = ProcessingJob(status="pending", input_files=[])
        db.add(job)
        db.commit()
        db.refresh(job)

        job_dir = UPLOAD_DIR / str(job.id)
        job_dir.mkdir(exist_ok=True)

        uploaded_files = []
        for file in files:
            if not file.filename.endswith((".xlsx", ".xls")):
                continue

            file_path = job_dir / file.filename
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            uploaded_files.append(file.filename)
            logger.info(f"Загружен файл: {file.filename}")

        job.input_files = uploaded_files
        db.commit()

        return {
            "job_id": job.id,
            "files": uploaded_files,
            "message": f"Загружено {len(uploaded_files)} файлов",
        }

    except Exception as e:
        logger.error(f"Ошибка при загрузке файлов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process/{job_id}")
async def process_files(job_id: int, db: Session = Depends(get_db)):

    try:

        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Задача не найдена")

        job.status = "processing"
        db.commit()

        job_dir = UPLOAD_DIR / str(job_id)

        if not job_dir.exists():
            job.status = "failed"
            job.error_message = "Папка с файлами не найдена"
            db.commit()
            raise HTTPException(status_code=404, detail="Папка с файлами не найдена")

        logger.info(f"Начало обработки задачи {job_id}")

        data_reader = DataReader(str(job_dir))
        data_parser = DataParser(job_dir)

        template_path = BASE_DIR.parent.parent / "templates" / "dashboard_template.xlsx"
        table_builder = TableBuilder(str(template_path))

        all_data = data_parser.parse_all_files()

        if not all_data:
            job.status = "failed"
            job.error_message = "Не удалось извлечь данные из файлов"
            db.commit()
            raise HTTPException(status_code=400, detail="Не удалось извлечь данные")

        departments = set(record["department_name"] for record in all_data)
        operations = set(record["operation_name"] for record in all_data)
        crops = set(record["crop_name"] for record in all_data)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"processed_{job_id}_{timestamp}.xlsx"
        output_path = OUTPUT_DIR / output_filename

        success = table_builder.build_table(all_data, str(output_path), "Отчет за день")

        if success:
            job.status = "completed"
            job.output_file = output_filename
            job.records_count = len(all_data)
            job.departments_count = len(departments)
            job.operations_count = len(operations)
            job.crops_count = len(crops)
            logger.info(f"Обработка задачи {job_id} завершена успешно")
        else:
            job.status = "failed"
            job.error_message = "Ошибка при создании Excel файла"

        db.commit()

        return job.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обработке задачи {job_id}: {e}")
        import traceback

        traceback.print_exc()

        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{job_id}")
async def download_file(job_id: int, db: Session = Depends(get_db)):

    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Задача не найдена")

        if job.status != "completed":
            raise HTTPException(status_code=400, detail="Обработка не завершена")

        output_path = OUTPUT_DIR / job.output_file

        if not output_path.exists():
            raise HTTPException(status_code=404, detail="Файл не найден")

        return FileResponse(
            path=str(output_path),
            filename=job.output_file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def get_history(db: Session = Depends(get_db)):

    try:
        jobs = (
            db.query(ProcessingJob)
            .order_by(ProcessingJob.created_at.desc())
            .limit(50)
            .all()
        )
        return [job.to_dict() for job in jobs]
    except Exception as e:
        logger.error(f"Ошибка при получении истории: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: int, db: Session = Depends(get_db)):

    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Задача не найдена")

        job_dir = UPLOAD_DIR / str(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir)

        if job.output_file:
            output_path = OUTPUT_DIR / job.output_file
            if output_path.exists():
                output_path.unlink()

        db.delete(job)
        db.commit()

        return {"message": "Задача удалена"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при удалении задачи: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/job/{job_id}")
async def get_job(job_id: int, db: Session = Depends(get_db)):

    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        return job.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении задачи: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
