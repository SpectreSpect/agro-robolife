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

def extract_date_from_filename(filename: str) -> Optional[datetime]:
    
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
    return None


class OperationalReportParser:
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.data = []
    
    def parse(self) -> List[Dict[str, Any]]:
        
        logger.info(f"Парсинг оперативной отчетности (алгоритмически): {self.file_path.name}")
        
        try:
            wb = openpyxl.load_workbook(self.file_path, data_only=True)
            
            for sheet_name in wb.sheetnames:
                logger.info(f"  Обработка листа: {sheet_name}")
                ws = wb[sheet_name]
                
                date_cell = ws.cell(2, 2).value
                if not isinstance(date_cell, datetime):
                    logger.warning(f"    Не найдена дата в листе {sheet_name}")
                    continue
                
                operation_date = date_cell
                crop_name = sheet_name
                
                operations = []
                col_idx = 2
                while col_idx <= ws.max_column:
                    operation_cell = ws.cell(3, col_idx).value
                    if operation_cell and str(operation_cell).strip() != "Предприятие":
                        operation_name = str(operation_cell).strip()
                        if operation_name and operation_name != "":
                            operations.append((col_idx, operation_name))
                            logger.debug(
                                f"    Найдена операция: {operation_name} в колонке {col_idx}"
                            )
                        
                        col_idx += 7
                    else:
                        col_idx += 1
                
                if not operations:
                    logger.warning(f"    Не найдены операции в листе {sheet_name}")
                    continue
                
                logger.info(f"    Найдено {len(operations)} операций")
                
                records_added = 0
                for row_idx in range(6, ws.max_row + 1):
                    enterprise_name = ws.cell(row_idx, 1).value
                    
                    if not enterprise_name:
                        break
                    
                    enterprise_str = str(enterprise_name).strip()
                    if enterprise_str.startswith("Итого") or enterprise_str == "":
                        continue
                    
                    department_name = enterprise_str
                    
                    for op_col, operation_name in operations:
                        try:
                            
                            plan_total_col = op_col
                            fact_col = op_col + 1
                            
                            plan_total = ws.cell(row_idx, plan_total_col).value
                            fact_current = ws.cell(row_idx, fact_col).value
                            
                            if plan_total is None or plan_total == 0:
                                continue
                            
                            plan_total = float(plan_total) if plan_total else 0
                            fact_current = float(fact_current) if fact_current else 0
                            
                            work_from_start = plan_total
                            work_per_day = fact_current
                            remaining_work = plan_total - fact_current
                            
                            if plan_total > 0:
                                completion_percent = fact_current / plan_total
                            else:
                                completion_percent = 0
                            
                            if plan_total > 0 or fact_current > 0:
                                record = {
                                    "operation_date": operation_date,
                                    "department_name": department_name,
                                    "operation_name": operation_name,
                                    "crop_name": crop_name,
                                    "work_per_day": work_per_day,
                                    "work_from_start": work_from_start,
                                    "remaining_work": remaining_work,
                                    "completion_percent": completion_percent,
                                    "source_file": self.file_path.name,
                                    "source_sheet": sheet_name,
                                    "enterprise_name": enterprise_str,
                                }
                                
                                self.data.append(record)
                                records_added += 1
                        
                        except Exception as e:
                            logger.warning(
                                f"    Ошибка при обработке операции {operation_name} для {enterprise_str}: {e}"
                            )
                            continue
                
                logger.info(
                    f"    Добавлено {records_added} записей из листа {sheet_name}"
                )
            
            wb.close()
            logger.info(
                f"  Всего извлечено {len(self.data)} записей из оперативной отчетности"
            )
            return self.data
        
        except Exception as e:
            logger.error(
                f"Ошибка при парсинге оперативной отчетности {self.file_path.name}: {e}"
            )
            import traceback
            traceback.print_exc()
            return []


class DailyReportLLMParser:
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.llm_client = LLMClient(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.data = []
    
    def parse(self) -> List[Dict[str, Any]]:
        
        logger.info(f"Парсинг дневного отчёта через LLM: {self.file_path.name}")
        
        try:
            wb = openpyxl.load_workbook(self.file_path, data_only=True)
            
            sheet_name = wb.sheetnames[0]
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


class HybridParser:
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.llm_client = LLMClient(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    
    def parse(self) -> List[Dict[str, Any]]:
        
        try:
            wb = openpyxl.load_workbook(self.file_path, data_only=True)
            ws = wb[wb.sheetnames[0]]
            
            sheet_data = ExcelToLLMConverter.convert_sheet_to_dict(ws, wb.sheetnames[0])
            wb.close()
            
            table_type = self.llm_client.determine_table_type(sheet_data, self.file_path.name)
            
            if table_type == "operational_report":
                logger.info(f"Используется алгоритмический парсер для {self.file_path.name}")
                parser = OperationalReportParser(self.file_path)
            else:
                logger.info(f"Используется LLM парсер для {self.file_path.name}")
                parser = DailyReportLLMParser(self.file_path)
            
            return parser.parse()
            
        except Exception as e:
            logger.error(f"Ошибка при определении типа файла {self.file_path.name}: {e}")
            return []


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
            parser = HybridParser(file_path)
            file_data = parser.parse()
            all_data.extend(file_data)
        
        logger.info(f"Всего извлечено записей: {len(all_data)}")
        
        return all_data
