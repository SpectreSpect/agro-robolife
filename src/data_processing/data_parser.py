import openpyxl
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import re
import os
from dotenv import load_dotenv

from .llm_client import LLMClient, ExcelToLLMConverter

logger = logging.getLogger(__name__)

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")

class UniversalLLMParser:
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.llm_client = LLMClient(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.data = []
    
    def parse(self) -> List[Dict[str, Any]]:
        
        logger.info(f"Парсинг файла через LLM: {self.file_path.name}")
        
        try:
            wb = openpyxl.load_workbook(self.file_path, data_only=True)
            
            for sheet_name in wb.sheetnames:
                logger.info(f"  Обработка листа: {sheet_name}")
                ws = wb[sheet_name]
                
                sheet_data = ExcelToLLMConverter.convert_sheet_to_dict(ws, sheet_name)
                
                records = self.llm_client.extract_table_data(
                    sheet_data=sheet_data,
                    file_name=self.file_path.name
                )
                
                for record in records:
                    processed_record = self._process_record(record, sheet_name)
                    if processed_record:
                        self.data.append(processed_record)
                
                logger.info(f"  Добавлено {len(records)} записей из листа {sheet_name}")
            
            wb.close()
            logger.info(f"  Всего извлечено {len(self.data)} записей из файла")
            return self.data
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге {self.file_path.name}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _process_record(self, record: Dict[str, Any], sheet_name: str) -> Optional[Dict[str, Any]]:
        
        try:
            operation_date = self._parse_date(record.get("operation_date"))
            if not operation_date:
                operation_date = self._extract_date_from_filename(self.file_path.name)
            
            department_name = record.get("department_name") or ""
            operation_name = record.get("operation_name") or ""
            crop_name = record.get("crop_name") or sheet_name
            
            work_per_day = float(record.get("work_per_day", 0) or 0)
            work_from_start = float(record.get("work_from_start", 0) or 0)
            remaining_work = float(record.get("remaining_work", 0) or 0)
            completion_percent = float(record.get("completion_percent", 0) or 0)
            
            if work_from_start == 0 and remaining_work == 0 and work_per_day == 0:
                return None
            
            return {
                "operation_date": operation_date,
                "department_name": str(department_name).strip(),
                "operation_name": str(operation_name).strip(),
                "crop_name": str(crop_name).strip(),
                "work_per_day": work_per_day,
                "work_from_start": work_from_start,
                "remaining_work": remaining_work,
                "completion_percent": completion_percent,
                "source_file": self.file_path.name,
                "source_sheet": sheet_name
            }
            
        except Exception as e:
            logger.warning(f"Ошибка при обработке записи: {e}")
            return None
    
    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        
        if isinstance(date_value, datetime):
            return date_value
        
        if isinstance(date_value, str):
            for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue
        
        return None
    
    def _extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        
        match = re.search(r"_(\d{4})\.xlsx$", filename)
        if match:
            date_str = match.group(1)
            day = int(date_str[:2])
            month = int(date_str[2:])
            year = 2025
            
            try:
                return datetime(year, month, day)
            except ValueError:
                logger.warning(f"Неверная дата из имени файла: {date_str}")
                return None
        
        return datetime.now()


class DataParser:
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
    
    def parse_all_files(self) -> List[Dict[str, Any]]:
        
        all_data = []
        
        excel_files = list(self.data_dir.glob("*.xlsx")) + list(self.data_dir.glob("*.xls"))
        excel_files = [f for f in excel_files if not f.name.startswith("~$") and not f.name.startswith(".")]
        
        logger.info(f"Найдено {len(excel_files)} Excel файлов для обработки")
        
        for file_path in excel_files:
            logger.info(f"Парсинг файла: {file_path.name}")
            parser = UniversalLLMParser(file_path)
            file_data = parser.parse()
            all_data.extend(file_data)
        
        logger.info(f"Всего извлечено записей: {len(all_data)}")
        
        return all_data
