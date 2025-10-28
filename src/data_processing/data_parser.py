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


class DailyReportAlgorithmicParser:
    """Алгоритмический парсер для дневных отчетов со стандартной структурой"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.data = []
    
    def validate_structure(self, ws) -> bool:
        """Проверяет, подходит ли структура таблицы для алгоритмического парсинга"""
        try:
            # Ищем строку с заголовками в первых 10 строках
            header_row = self._find_header_row(ws)
            if not header_row:
                logger.debug("Не найдена строка заголовков")
                return False
            
            # Ищем колонки "Итого" и "Остаток"
            itogo_cols = []
            ostatok_col = None
            
            for col in range(1, ws.max_column + 1):
                cell_value = ws.cell(header_row, col).value
                if cell_value:
                    cell_str = str(cell_value).strip().lower()
                    if "итого" in cell_str or "итог" in cell_str:
                        itogo_cols.append(col)
                    elif "остаток" in cell_str or "остат" in cell_str:
                        ostatok_col = col
            
            # Если нашли только одну "Итого", проверяем подзаголовки
            if len(itogo_cols) == 1 and header_row < ws.max_row:
                subheader_row = header_row + 1
                has_za_den = False
                has_ot_nachala = False
                
                for col in range(1, ws.max_column + 1):
                    cell_value = ws.cell(subheader_row, col).value
                    if cell_value:
                        cell_str = str(cell_value).strip().lower()
                        if "за день" in cell_str:
                            has_za_den = True
                        elif "начала" in cell_str or "начал" in cell_str:
                            has_ot_nachala = True
                
                # Если нашли подзаголовки, считаем что структура валидна
                if has_za_den and has_ot_nachala:
                    itogo_cols = [0, 0]  # Заглушка для проверки
            
            # Более мягкая проверка: достаточно хотя бы одной "Итого" колонки
            if len(itogo_cols) < 1:
                logger.debug(f"Не найдено колонок 'Итого'")
                return False
            
            # "Остаток" не обязателен, но желателен
            if len(itogo_cols) < 2 and not ostatok_col:
                logger.debug(f"Найдено только {len(itogo_cols)} колонок 'Итого' и нет 'Остаток' - структура слишком простая")
                return False
            
            # Проверяем наличие данных после заголовка
            data_row = header_row + 1
            
            # Если в строке после заголовка пустая первая ячейка, это подзаголовки
            first_cell = ws.cell(data_row, 1).value
            if first_cell is None or (isinstance(first_cell, str) and len(first_cell.strip()) < 3):
                data_row += 1
            
            if data_row > ws.max_row:
                logger.debug("Нет данных после заголовка")
                return False
            
            # Проверяем, что в строке данных есть числовые значения
            # Для двухуровневых заголовков проверяем реальные колонки данных
            has_numeric = False
            for col in range(1, ws.max_column + 1):
                val = ws.cell(data_row, col).value
                if isinstance(val, (int, float)) and val != 0:
                    has_numeric = True
                    break
            
            if not has_numeric:
                logger.debug("Нет числовых данных в первой строке")
                return False
            
            logger.info(f"✓ Структура валидна: заголовок на строке {header_row}, {len(itogo_cols)} колонок 'Итого'")
            return True
            
        except Exception as e:
            logger.debug(f"Ошибка при валидации структуры: {e}")
            return False
    
    def parse(self) -> List[Dict[str, Any]]:
        """Парсинг дневного отчета алгоритмически"""
        logger.info(f"Парсинг дневного отчёта (алгоритмически): {self.file_path.name}")
        
        try:
            wb = openpyxl.load_workbook(self.file_path, data_only=True)
            ws = wb[wb.sheetnames[0]]
            sheet_name = wb.sheetnames[0]
            
            # Извлекаем дату
            operation_date = self._extract_date(ws)
            if not operation_date:
                operation_date = extract_date_from_filename(self.file_path.name) or datetime.now()
            
            # Извлекаем название подразделения
            department_name = self._extract_department(ws)
            
            # Находим строку заголовков
            header_row = self._find_header_row(ws)
            if not header_row:
                logger.error("Не найдена строка заголовков")
                return []
            
            # Определяем колонки
            columns = self._find_columns(ws, header_row)
            if not columns:
                logger.error("Не удалось определить колонки")
                return []
            
            logger.info(f"  Найдены колонки: операция={columns['operation']}, культура={columns['crop']}, " +
                       f"итого1={columns['itogo1']}, итого2={columns['itogo2']}, остаток={columns['ostatok']}")
            
            # Определяем с какой строки начинаются данные
            # Если есть двухуровневые заголовки (подзаголовки), пропускаем их
            data_start_row = header_row + 1
            
            # Проверяем, есть ли подзаголовки
            first_cell = ws.cell(data_start_row, 1).value
            if first_cell is None or (isinstance(first_cell, str) and len(first_cell.strip()) < 3):
                # Вероятно подзаголовки, пропускаем еще одну строку
                data_start_row += 1
            
            # Парсим строки данных
            records_count = 0
            logger.info(f"  Начинаем парсинг данных с строки {data_start_row} до строки {ws.max_row}")
            
            for row_idx in range(data_start_row, ws.max_row + 1):
                # Проверяем первую колонку
                operation_val = ws.cell(row_idx, columns['operation']).value
                
                if not operation_val:
                    logger.debug(f"  Строка {row_idx}: пустая первая колонка, конец данных")
                    break  # Пустая строка - конец данных
                
                operation_str = str(operation_val).strip()
                if not operation_str or operation_str.lower().startswith("итого"):
                    continue  # Строка "Итого" - пропускаем
                
                # Извлекаем данные
                crop_val = ws.cell(row_idx, columns['crop']).value
                crop_name = str(crop_val).strip() if crop_val else ""
                
                itogo1_val = ws.cell(row_idx, columns['itogo1']).value
                itogo2_val = ws.cell(row_idx, columns['itogo2']).value
                
                # "Остаток" может отсутствовать
                if columns['ostatok']:
                    ostatok_val = ws.cell(row_idx, columns['ostatok']).value
                else:
                    ostatok_val = None
                
                work_per_day = float(itogo1_val) if isinstance(itogo1_val, (int, float)) else 0
                work_from_start = float(itogo2_val) if isinstance(itogo2_val, (int, float)) else 0
                remaining_work = float(ostatok_val) if isinstance(ostatok_val, (int, float)) else 0
                
                # Пропускаем строки без данных
                if work_per_day == 0 and work_from_start == 0 and remaining_work == 0:
                    logger.debug(f"  Строка {row_idx}: все числовые значения равны 0, пропускаем")
                    continue
                
                # Вычисляем процент выполнения
                total = work_from_start + remaining_work
                completion_percent = work_from_start / total if total > 0 else 0
                
                record = {
                    "operation_date": operation_date,
                    "department_name": department_name,
                    "operation_name": operation_str,
                    "crop_name": crop_name,
                    "work_per_day": work_per_day,
                    "work_from_start": work_from_start,
                    "remaining_work": remaining_work,
                    "completion_percent": completion_percent,
                    "source_file": self.file_path.name,
                    "source_sheet": sheet_name
                }
                
                self.data.append(record)
                records_count += 1
                
                # Логируем первые 3 записи для отладки
                if records_count <= 3:
                    logger.info(f"  Строка {row_idx}: {operation_str[:20]} | {crop_name[:15]} | день={work_per_day} начало={work_from_start} остаток={remaining_work}")
            
            wb.close()
            logger.info(f"  Извлечено {records_count} записей алгоритмически")
            return self.data
            
        except Exception as e:
            logger.error(f"Ошибка при алгоритмическом парсинге {self.file_path.name}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _find_header_row(self, ws) -> Optional[int]:
        """Находит строку с заголовками (содержит 'Итого' или 'Остаток')"""
        # Сначала ищем строку с обоими ключевыми словами
        for row in range(1, min(11, ws.max_row + 1)):
            has_itogo = False
            has_ostatok = False
            
            for col in range(1, ws.max_column + 1):
                cell_value = ws.cell(row, col).value
                if cell_value:
                    cell_str = str(cell_value).strip().lower()
                    if "итого" in cell_str or "итог" in cell_str:
                        has_itogo = True
                    if "остаток" in cell_str or "остат" in cell_str:
                        has_ostatok = True
            
            if has_itogo and has_ostatok:
                return row
        
        # Если не нашли, ищем строку хотя бы с "Итого"
        for row in range(1, min(11, ws.max_row + 1)):
            for col in range(1, ws.max_column + 1):
                cell_value = ws.cell(row, col).value
                if cell_value:
                    cell_str = str(cell_value).strip().lower()
                    if "итого" in cell_str or "итог" in cell_str:
                        logger.debug(f"Найден заголовок с 'Итого' на строке {row} (без 'Остаток')")
                        return row
        
        return None
    
    def _find_columns(self, ws, header_row: int) -> Optional[Dict[str, int]]:
        """Определяет индексы нужных колонок"""
        itogo_cols = []
        ostatok_col = None
        
        # Сначала ищем в текущей строке заголовков
        for col in range(1, ws.max_column + 1):
            cell_value = ws.cell(header_row, col).value
            if cell_value:
                cell_str = str(cell_value).strip().lower()
                if "итого" in cell_str or "итог" in cell_str:
                    itogo_cols.append(col)
                elif "остаток" in cell_str or "остат" in cell_str:
                    ostatok_col = col
        
        # Если нашли только одну "Итого", проверяем следующую строку на подзаголовки
        if len(itogo_cols) == 1 and header_row < ws.max_row:
            subheader_row = header_row + 1
            itogo_col = itogo_cols[0]
            
            # Ищем "за день" и "от начала" под "Итого"
            za_den_col = None
            ot_nachala_col = None
            
            # Проверяем колонки около найденной "Итого"
            for offset in range(-2, 5):  # Проверяем в радиусе ±2 колонок
                check_col = itogo_col + offset
                if check_col < 1 or check_col > ws.max_column:
                    continue
                
                cell_value = ws.cell(subheader_row, check_col).value
                if cell_value:
                    cell_str = str(cell_value).strip().lower()
                    if "за день" in cell_str or "за д" in cell_str:
                        za_den_col = check_col
                    elif "от начала" in cell_str or "с начала" in cell_str or "начал" in cell_str:
                        ot_nachala_col = check_col
            
            # Если нашли подзаголовки, используем их
            if za_den_col and ot_nachala_col:
                logger.info(f"  Обнаружены двухуровневые заголовки: 'Итого' с подколонками")
                itogo_cols = [za_den_col, ot_nachala_col]
        
        # Более мягкая проверка: нужна хотя бы одна "Итого" колонка
        if len(itogo_cols) < 1:
            logger.debug("Не найдено ни одной колонки 'Итого'")
            return None
        
        # Если только одна "Итого", дублируем её для обоих полей
        if len(itogo_cols) == 1:
            logger.debug(f"Найдена только одна колонка 'Итого' - будет использована для обоих значений")
            itogo_cols.append(itogo_cols[0])
        
        return {
            "operation": 1,  # Первая колонка - операция
            "crop": 2,  # Вторая колонка - культура
            "itogo1": itogo_cols[0] if len(itogo_cols) > 0 else None,  # Первая "Итого" - за день
            "itogo2": itogo_cols[1] if len(itogo_cols) > 1 else itogo_cols[0],  # Вторая "Итого" - с начала
            "ostatok": ostatok_col if ostatok_col else None  # "Остаток" (может быть None)
        }
    
    def _extract_date(self, ws) -> Optional[datetime]:
        """Извлекает дату из первых строк таблицы"""
        # Ищем дату в первых 5 строках
        for row in range(1, min(6, ws.max_row + 1)):
            for col in range(1, min(10, ws.max_column + 1)):
                cell_value = ws.cell(row, col).value
                if isinstance(cell_value, datetime):
                    return cell_value
        
        return None
    
    def _extract_department(self, ws) -> str:
        """Извлекает название подразделения из заголовка"""
        # Служебные слова, которые нужно исключить
        exclude_words = {
            "отчет", "отчёт", "план", "таблица", "по", "за", "на", "свод",
            "данные", "результаты", "отделение", "для", "дневного", "работ",
            "сводный", "итоговый", "операции", "полевые", "наименование",
            "название", "культур", "культуры"
        }
        
        candidates = []
        
        # Ищем название в первых 5 строках
        for row in range(1, min(6, ws.max_row + 1)):
            for col in range(1, min(15, ws.max_column + 1)):
                cell_value = ws.cell(row, col).value
                if cell_value and isinstance(cell_value, str):
                    text = cell_value.strip()
                    
                    # Пропускаем слишком длинные строки (больше 50 символов)
                    if len(text) > 50:
                        continue
                    
                    # Пропускаем слишком короткие
                    if len(text) < 3:
                        continue
                    
                    # Пропускаем даты и числа
                    if text.replace(".", "").replace("/", "").replace("-", "").replace(" ", "").isdigit():
                        continue
                    
                    text_lower = text.lower()
                    
                    # Пропускаем строки, которые полностью состоят из служебных слов
                    words = text_lower.split()
                    filtered_words = [w for w in words if w not in exclude_words]
                    
                    if not filtered_words:
                        continue
                    
                    # Если осталось 1-5 слов
                    if 1 <= len(filtered_words) <= 5:
                        # Восстанавливаем исходный регистр
                        result_words = []
                        for word in text.split():
                            if word.lower() not in exclude_words:
                                result_words.append(word)
                        
                        if result_words:
                            department = " ".join(result_words)
                            
                            # Приоритет названиям с "ПУ", "ООО", "ЗАО" и т.д.
                            priority = 0
                            if any(prefix in department.upper() for prefix in ["ПУ", "ООО", "ЗАО", "ОАО", "АО"]):
                                priority = 10
                            # Или короткие названия (обычно названия организаций)
                            elif len(department.split()) <= 3:
                                priority = 5
                            
                            candidates.append((priority, department, row, col))
        
        # Выбираем кандидата с наивысшим приоритетом
        if candidates:
            candidates.sort(key=lambda x: (-x[0], x[2], x[3]))  # Сортируем по приоритету, потом по позиции
            return candidates[0][1]
        
        # Если не нашли, возвращаем имя файла без расширения
        return self.file_path.stem


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
            
            # Определяем тип таблицы через LLM (с fallback при ошибке)
            table_type = None
            try:
                table_type = self.llm_client.determine_table_type(sheet_data, self.file_path.name)
            except Exception as llm_error:
                logger.warning(f"⚠️ LLM timeout/ошибка при определении типа: {llm_error}")
                logger.info("🔄 Fallback: пробуем алгоритмические парсеры")
                
                # Пробуем алгоритмический парсер для дневного отчёта
                algo_daily = DailyReportAlgorithmicParser(self.file_path)
                if algo_daily.validate_structure(ws):
                    logger.info(f"✅ Успех! Используется алгоритмический парсер (дневной отчёт)")
                    wb.close()
                    return algo_daily.parse()
                
                # Пробуем алгоритмический парсер для оперативной отчётности
                try:
                    logger.info("Пробуем парсер оперативной отчётности...")
                    wb.close()
                    parser_operational = OperationalReportParser(self.file_path)
                    result = parser_operational.parse()
                    if result and len(result) > 0:
                        logger.info(f"✅ Успех! Используется парсер оперативной отчётности")
                        return result
                except Exception:
                    pass
                
                # Если ничего не подошло, пробуем LLM парсер как последнюю попытку
                logger.info(f"⚠️ Алгоритмические парсеры не подошли, используем LLM парсер")
                table_type = "daily_report"  # Предполагаем дневной отчёт
            
            if table_type == "operational_report":
                logger.info(f"Тип: оперативная отчётность → используется алгоритмический парсер")
                wb.close()
                parser = OperationalReportParser(self.file_path)
                return parser.parse()
            
            elif table_type == "daily_report":
                # Сначала пробуем алгоритмический парсер
                algo_parser = DailyReportAlgorithmicParser(self.file_path)
                
                # Проверяем структуру
                if algo_parser.validate_structure(ws):
                    logger.info(f"Тип: дневной отчёт → используется алгоритмический парсер ✓")
                    wb.close()
                    return algo_parser.parse()
                else:
                    logger.info(f"Тип: дневной отчёт → структура нестандартная, пробуем LLM парсер")
                    wb.close()
                    parser = DailyReportLLMParser(self.file_path)
                    result = parser.parse()
                    
                    # Если LLM парсер ничего не вернул (timeout/ошибка), пробуем алгоритмический
                    if not result or len(result) == 0:
                        logger.warning(f"⚠️ LLM парсер не смог обработать {self.file_path.name}")
                        logger.info(f"🔄 Fallback: пробуем алгоритмический парсер для дневного отчёта")
                        algo_parser = DailyReportAlgorithmicParser(self.file_path)
                        result = algo_parser.parse()
                        if result and len(result) > 0:
                            logger.info(f"✓ Fallback успешен: извлечено {len(result)} записей алгоритмически")
                        else:
                            logger.warning(f"❌ Алгоритмический парсер тоже не смог обработать {self.file_path.name}")
                    
                    return result
            
            else:
                # Для неизвестных типов пробуем LLM, затем алгоритмические парсеры
                logger.info(f"Тип: неизвестный → пробуем LLM парсер")
                wb.close()
                parser = DailyReportLLMParser(self.file_path)
                result = parser.parse()
                
                # Если LLM не смог, пробуем все алгоритмические парсеры
                if not result or len(result) == 0:
                    logger.warning(f"⚠️ LLM парсер не смог обработать {self.file_path.name}")
                    logger.info(f"🔄 Fallback: пробуем алгоритмические парсеры")
                    
                    # Пробуем дневной отчёт
                    algo_daily = DailyReportAlgorithmicParser(self.file_path)
                    result = algo_daily.parse()
                    if result and len(result) > 0:
                        logger.info(f"✓ Fallback успешен (дневной отчёт): извлечено {len(result)} записей")
                        return result
                    
                    # Пробуем оперативную отчётность
                    parser_operational = OperationalReportParser(self.file_path)
                    result = parser_operational.parse()
                    if result and len(result) > 0:
                        logger.info(f"✓ Fallback успешен (оперативная отчётность): извлечено {len(result)} записей")
                        return result
                    
                    logger.warning(f"❌ Ни один парсер не смог обработать {self.file_path.name}")
                
                return result
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге {self.file_path.name}: {e}")
            import traceback
            traceback.print_exc()
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
