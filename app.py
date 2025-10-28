import os
import sys
import shutil
import logging
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import uvicorn

sys.path.append(str(Path(__file__).parent.parent))

from src.web.database import get_db, init_db
from src.web.models import Report, ScheduleConfig
from src.web.report_scheduler import ReportScheduler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# WebSocket Manager для broadcast сообщений всем клиентам
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket подключен. Всего соединений: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket отключен. Всего соединений: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Отправить сообщение всем подключенным клиентам"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Ошибка отправки WebSocket сообщения: {e}")


app = FastAPI(title="Agro Data Processing System", version="3.0")
ws_manager = ConnectionManager()

BASE_DIR = Path("src/web")
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SHARED_FILES_DIR = Path("shared_files")
ARCHIVED_FILES_DIR = Path("archived_files")
OUTPUT_DIR = Path("outputs")
TEMPLATE_PATH = Path("templates") / "dashboard_template.xlsx"

# Создаем необходимые директории
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)
SHARED_FILES_DIR.mkdir(exist_ok=True)
ARCHIVED_FILES_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Глобальный планировщик
scheduler = ReportScheduler(
    shared_files_dir=SHARED_FILES_DIR,
    archived_files_dir=ARCHIVED_FILES_DIR,
    output_dir=OUTPUT_DIR,
    template_path=TEMPLATE_PATH
)
scheduler.set_ws_manager(ws_manager)


# Pydantic модели для запросов
class ScheduleRequest(BaseModel):
    schedule_type: str  # "one_time" или "periodic"
    recipient_email: EmailStr
    scheduled_time: Optional[str] = None  # ISO format для one_time
    periodic_time: Optional[str] = None  # "HH:MM" для periodic


class FileRenameRequest(BaseModel):
    new_name: str


@app.on_event("startup")
async def startup_event():
    init_db()
    logger.info("База данных инициализирована")
    scheduler.start()
    logger.info("Планировщик отчетов запущен")


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("Планировщик отчетов остановлен")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ============================================================================
# API для управления файлами
# ============================================================================

@app.get("/api/files")
async def get_files():
    """Получить список файлов из shared_files"""
    try:
        files = []
        for file_path in SHARED_FILES_DIR.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.xlsx', '.xls']:
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                })
        
        # Сортируем по дате модификации (новые первые)
        files.sort(key=lambda x: x["modified"], reverse=True)
        
        return {"files": files}
    
    except Exception as e:
        logger.error(f"Ошибка при получении списка файлов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/files/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Загрузить файлы в shared_files"""
    try:
        uploaded_files = []
        
        for file in files:
            if not file.filename.endswith((".xlsx", ".xls")):
                continue

            file_path = SHARED_FILES_DIR / file.filename
            
            # Если файл уже существует, добавляем timestamp
            if file_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name, ext = os.path.splitext(file.filename)
                file_path = SHARED_FILES_DIR / f"{name}_{timestamp}{ext}"
            
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            uploaded_files.append(file_path.name)
            logger.info(f"Загружен файл: {file_path.name}")

        # Уведомляем всех клиентов об изменении файлов
        await ws_manager.broadcast({
            "type": "files_updated"
        })
        
        return {
            "files": uploaded_files,
            "message": f"Загружено {len(uploaded_files)} файлов"
        }

    except Exception as e:
        logger.error(f"Ошибка при загрузке файлов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/files/{filename}")
async def delete_file(filename: str):
    """Удалить файл из shared_files"""
    try:
        file_path = SHARED_FILES_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Файл не найден")
        
        file_path.unlink()
        logger.info(f"Удален файл: {filename}")
        
        # Уведомляем всех клиентов об изменении файлов
        await ws_manager.broadcast({
            "type": "files_updated"
        })
        
        return {"message": "Файл удален"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при удалении файла: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/files/{filename}/rename")
async def rename_file(filename: str, request: FileRenameRequest):
    """Переименовать файл в shared_files"""
    try:
        old_path = SHARED_FILES_DIR / filename
        new_path = SHARED_FILES_DIR / request.new_name
        
        if not old_path.exists():
            raise HTTPException(status_code=404, detail="Файл не найден")
        
        if new_path.exists():
            raise HTTPException(status_code=400, detail="Файл с таким именем уже существует")
        
        # Проверяем расширение
        if not request.new_name.endswith((".xlsx", ".xls")):
            raise HTTPException(status_code=400, detail="Неправильное расширение файла")
        
        old_path.rename(new_path)
        logger.info(f"Файл переименован: {filename} -> {request.new_name}")
        
        # Уведомляем всех клиентов об изменении файлов
        await ws_manager.broadcast({
            "type": "files_updated"
        })
        
        return {"message": "Файл переименован", "new_name": request.new_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при переименовании файла: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files/download/{filename}")
async def download_shared_file(filename: str):
    """Скачать файл из shared_files"""
    try:
        file_path = SHARED_FILES_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Файл не найден")

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# API для управления расписанием
# ============================================================================

@app.get("/api/schedule")
async def get_schedule():
    """Получить текущее расписание"""
    try:
        schedule = scheduler.get_active_schedule()
        
        if schedule:
            return schedule
        else:
            return {
                "is_enabled": False,
                "schedule_type": None,
                "scheduled_time": None,
                "periodic_time": None,
                "recipient_email": None
            }
    
    except Exception as e:
        logger.error(f"Ошибка при получении расписания: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/schedule")
async def set_schedule(request: ScheduleRequest):
    """Установить расписание"""
    try:
        if request.schedule_type not in ["one_time", "periodic"]:
            raise HTTPException(status_code=400, detail="Неверный тип расписания")
        
        scheduled_time = None
        periodic_time = None
        
        if request.schedule_type == "one_time":
            if not request.scheduled_time:
                raise HTTPException(status_code=400, detail="Не указано время для разовой задачи")
            
            # Парсим ISO время
            scheduled_time_str = request.scheduled_time.replace('Z', '+00:00')
            scheduled_time_utc = datetime.fromisoformat(scheduled_time_str)
        
            if scheduled_time_utc.tzinfo:
                scheduled_time = scheduled_time_utc.astimezone().replace(tzinfo=None)
            else:
                scheduled_time = scheduled_time_utc
        
            if scheduled_time <= datetime.now():
                raise HTTPException(status_code=400, detail="Время должно быть в будущем")
        
        elif request.schedule_type == "periodic":
            if not request.periodic_time:
                raise HTTPException(status_code=400, detail="Не указано время для периодической задачи")
            
            # Проверяем формат времени
            try:
                hour, minute = map(int, request.periodic_time.split(":"))
                if not (0 <= hour < 24 and 0 <= minute < 60):
                    raise ValueError()
                periodic_time = request.periodic_time
            except:
                raise HTTPException(status_code=400, detail="Неверный формат времени (ожидается HH:MM)")
        
        success = scheduler.set_schedule(
            schedule_type=request.schedule_type,
            recipient_email=request.recipient_email,
            scheduled_time=scheduled_time,
            periodic_time=periodic_time
        )
        
        if success:
            # Уведомляем всех подключенных клиентов об изменении расписания
            await ws_manager.broadcast({
                "type": "schedule_updated"
            })
            return {"message": "Расписание установлено"}
        else:
            raise HTTPException(status_code=500, detail="Ошибка при установке расписания")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при установке расписания: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/schedule")
async def cancel_schedule():
    """Отменить расписание"""
    try:
        success = scheduler.cancel_schedule()
        
        if success:
            # Уведомляем всех подключенных клиентов об отмене расписания
            await ws_manager.broadcast({
                "type": "schedule_updated"
            })
            return {"message": "Расписание отменено"}
        else:
            raise HTTPException(status_code=500, detail="Ошибка при отмене расписания")
    
    except Exception as e:
        logger.error(f"Ошибка при отмене расписания: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schedule/countdown")
async def get_countdown():
    """Получить время до следующей генерации отчета"""
    try:
        schedule = scheduler.get_active_schedule()
        
        if not schedule or not schedule.get("is_enabled"):
            return {"active": False}
        
        if schedule["schedule_type"] == "one_time" and schedule["scheduled_time"]:
            scheduled_dt = datetime.fromisoformat(schedule["scheduled_time"])
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            
            if scheduled_dt > now:
                seconds_left = (scheduled_dt - now).total_seconds()
                return {
                    "active": True,
                    "type": "one_time",
                    "scheduled_time": schedule["scheduled_time"],
                    "seconds_left": int(seconds_left)
                }
        
        elif schedule["schedule_type"] == "periodic" and schedule["periodic_time"]:
            # Вычисляем следующее срабатывание
            hour, minute = map(int, schedule["periodic_time"].split(":"))
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            next_run = datetime.now(timezone.utc).replace(tzinfo=None, hour=hour, minute=minute, second=0, microsecond=0)
            
            if next_run <= now:
                # Если время уже прошло сегодня, берем завтра
                from datetime import timedelta
                next_run += timedelta(days=1)
            
            seconds_left = (next_run - now).total_seconds()
            return {
                "active": True,
                "type": "periodic",
                "periodic_time": schedule["periodic_time"],
                "next_run": next_run.replace(tzinfo=timezone.utc).isoformat(),
                "seconds_left": int(seconds_left)
            }
        
        return {"active": False}
    
    except Exception as e:
        logger.error(f"Ошибка при получении обратного отсчета: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/schedule/generate-now")
async def generate_now():
    """
    Немедленная генерация отчета
    Работает независимо от настройки расписания
    """
    try:
        # Запускаем генерацию (не блокирует, работает в фоне)
        report_id = await scheduler.generate_now()
        
        # Возвращаем успех сразу, генерация продолжается в фоне
        return {
            "message": "Генерация отчета запущена",
            "report_id": report_id,
            "note": "Отчет генерируется в фоновом режиме. Проверьте историю через несколько секунд."
        }
    
    except Exception as e:
        logger.error(f"Ошибка при запуске генерации: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# API для отчетов
# ============================================================================

@app.get("/api/reports")
async def get_reports(db: Session = Depends(get_db)):
    """Получить историю отчетов"""
    try:
        reports = (
            db.query(Report)
            .order_by(Report.created_at.desc())
            .limit(50)
            .all()
        )
        return [report.to_dict() for report in reports]
    
    except Exception as e:
        logger.error(f"Ошибка при получении отчетов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/{report_id}/download")
async def download_report(report_id: int, db: Session = Depends(get_db)):
    """Скачать отчет"""
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        
        if not report:
            raise HTTPException(status_code=404, detail="Отчет не найден")
        
        output_path = OUTPUT_DIR / report.output_file
        
        if not output_path.exists():
            raise HTTPException(status_code=404, detail="Файл отчета не найден")
        
        return FileResponse(
            path=str(output_path),
            filename=report.output_file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при скачивании отчета: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/{report_id}/files/{filename}")
async def download_source_file(report_id: int, filename: str, db: Session = Depends(get_db)):
    """Скачать исходный файл из архива отчета"""
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        
        if not report:
            raise HTTPException(status_code=404, detail="Отчет не найден")
        
        # Извлекаем timestamp из имени файла отчета
        # Например: report_20251027_210700.xlsx -> 20251027_210700
        import re
        match = re.search(r'report_(\d{8}_\d{6})\.xlsx', report.output_file)
        if not match:
            raise HTTPException(status_code=404, detail="Не удалось определить архив")
        
        timestamp = match.group(1)
        
        # Проверяем что файл в списке archived_files
        if not report.archived_files or filename not in report.archived_files:
            raise HTTPException(status_code=404, detail="Файл не найден в архиве")
        
        # Путь к файлу в архиве
        archive_path = ARCHIVED_FILES_DIR / timestamp / filename
        
        if not archive_path.exists():
            raise HTTPException(status_code=404, detail="Файл не найден в архиве")
        
        return FileResponse(
            path=str(archive_path),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при скачивании исходного файла: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: int, db: Session = Depends(get_db)):
    """Удалить отчет"""
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        
        if not report:
            raise HTTPException(status_code=404, detail="Отчет не найден")
        
        # Удаляем файл отчета
        if report.output_file:
            output_path = OUTPUT_DIR / report.output_file
            if output_path.exists():
                output_path.unlink()
        
        db.delete(report)
        db.commit()
        
        logger.info(f"Отчет {report_id} удален")
        
        return {"message": "Отчет удален"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при удалении отчета: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ WebSocket и статус генерации ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket для real-time обновлений статуса генерации"""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Ожидаем сообщения от клиента (keep-alive)
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/api/generation-status")
async def get_generation_status():
    """Получить текущий статус генерации"""
    return {
        "is_generating": scheduler.is_generating
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
