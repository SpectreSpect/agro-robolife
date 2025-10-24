"""
LLM-based парсер для Excel файлов.

Использует LLM для извлечения данных из Excel файлов любой структуры.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .llm_client import LLMClient
from .llm_config import get_llm_config
from .data_reader import DataReader
from .prompts_templates import (
    SYSTEM_PROMPT_ANALYST,
    STRUCTURE_ANALYSIS_PROMPT_V1,
    EXTRACTION_PROMPT_V1,
    DAILY_REPORT_EXTRACTION,
    OPERATIONAL_REPORT_EXTRACTION,
    format_sample_data,
)

logger = logging.getLogger(__name__)


class LLMParser:
    """
    Парсер Excel файлов с использованием LLM.
    
    Алгоритм работы:
    1. Получить метаданные файла от DataReader
    2. Анализ структуры через LLM (первые N строк)
    3. Извлечение данных через LLM
    4. Валидация и постобработка
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Args:
            llm_client: LLM клиент (если None - создается автоматически)
        """
        if llm_client is None:
            config = get_llm_config()
            self.llm_client = LLMClient(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                max_retries=config.max_retries,
                log_requests=config.log_requests,
            )
        else:
            self.llm_client = llm_client
        
        self.data_reader = DataReader()
        self.structure_cache = {}  # Кэш структур файлов
        
        logger.info(f"LLMParser инициализирован с {self.llm_client}")
    
    def parse_file(
        self,
        file_path: Path,
        file_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Парсит Excel файл с использованием LLM.
        
        Args:
            file_path: Путь к файлу
            file_metadata: Метаданные файла (опционально, будут извлечены если None)
        
        Returns:
            Список извлеченных записей
        """
        logger.info(f"Начало LLM парсинга файла: {file_path.name}")
        
        try:
            # Получаем метаданные если не предоставлены
            if file_metadata is None:
                file_metadata = self.data_reader.read_excel_file_enhanced(file_path)
            
            if "error" in file_metadata:
                logger.error(f"Ошибка в метаданных файла: {file_metadata['error']}")
                return []
            
            # Парсим каждый лист
            all_records = []
            file_type = file_metadata.get("file_type", "other")
            
            for sheet_name, sheet_info in file_metadata["sheets"].items():
                logger.info(f"  Парсинг листа: {sheet_name}")
                
                try:
                    # Этап 1: Анализ структуры
                    structure = self._analyze_structure(
                        file_path,
                        sheet_name,
                        sheet_info,
                        file_type
                    )
                    
                    if not structure:
                        logger.warning(f"    Не удалось определить структуру листа {sheet_name}")
                        continue
                    
                    # Этап 2: Извлечение данных
                    records = self._extract_data(
                        file_path,
                        sheet_name,
                        sheet_info,
                        structure,
                        file_type
                    )
                    
                    if not records:
                        logger.warning(f"    Не извлечено данных из листа {sheet_name}")
                        continue
                    
                    # Этап 3: Валидация
                    valid_records = self._validate_records(records)
                    
                    # Этап 4: Постобработка
                    processed_records = self._post_process(valid_records)
                    
                    all_records.extend(processed_records)
                    logger.info(f"    Извлечено {len(processed_records)} записей из {sheet_name}")
                    
                except Exception as e:
                    logger.error(f"    Ошибка при парсинге листа {sheet_name}: {e}")
                    continue
            
            logger.info(f"Всего извлечено {len(all_records)} записей из {file_path.name}")
            return all_records
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге файла {file_path}: {e}")
            return []
    
    def _analyze_structure(
        self,
        file_path: Path,
        sheet_name: str,
        sheet_info: Dict[str, Any],
        file_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Анализирует структуру листа через LLM.
        
        Returns:
            Словарь с описанием структуры или None
        """
        # Проверяем кэш
        cache_key = f"{file_path.name}_{sheet_name}"
        if cache_key in self.structure_cache:
            logger.debug(f"    Структура взята из кэша")
            return self.structure_cache[cache_key]
        
        try:
            # Форматируем образец данных
            sample_data = sheet_info.get("sample_data", [])
            if not sample_data:
                return None
            
            formatted_sample = format_sample_data(sample_data, max_rows=20)
            
            # Формируем промпт
            prompt = STRUCTURE_ANALYSIS_PROMPT_V1.format(
                sample_data=formatted_sample,
                file_name=file_path.name,
                total_rows=sheet_info.get("max_rows", "?"),
                total_cols=sheet_info.get("max_cols", "?"),
                sheet_name=sheet_name,
            )
            
            # Отправляем LLM
            response = self.llm_client.send_request(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_ANALYST
            )
            
            # Парсим JSON
            structure = self.llm_client.parse_json_response(response)
            
            # Сохраняем в кэш
            self.structure_cache[cache_key] = structure
            
            logger.debug(f"    Структура определена: {structure.get('file_type')}")
            return structure
            
        except Exception as e:
            logger.error(f"    Ошибка при анализе структуры: {e}")
            return None
    
    def _extract_data(
        self,
        file_path: Path,
        sheet_name: str,
        sheet_info: Dict[str, Any],
        structure: Dict[str, Any],
        file_type: str
    ) -> List[Dict[str, Any]]:
        """
        Извлекает данные из листа через LLM.
        
        Returns:
            Список извлеченных записей
        """
        try:
            # Получаем все данные из листа (не только sample)
            all_data = self.data_reader.extract_cell_values(
                file_path,
                sheet_name,
                max_rows=1000,  # Максимум 1000 строк
                max_cols=50
            )
            
            if not all_data:
                return []
            
            # Форматируем данные для LLM
            formatted_data = format_sample_data(all_data, max_rows=min(100, len(all_data)))
            
            # Выбираем промпт в зависимости от типа файла
            if file_type == "daily_report":
                prompt_template = DAILY_REPORT_EXTRACTION
            elif file_type == "operational_report":
                prompt_template = OPERATIONAL_REPORT_EXTRACTION
            else:
                prompt_template = EXTRACTION_PROMPT_V1
            
            # Формируем промпт
            prompt = prompt_template.format(
                structure=json.dumps(structure, ensure_ascii=False, indent=2),
                table_data=formatted_data,
                sheet_name=sheet_name,
            )
            
            # Отправляем LLM
            response = self.llm_client.send_request(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_ANALYST
            )
            
            # Парсим JSON
            records = self.llm_client.parse_json_response(response)
            
            # Убеждаемся что это список
            if isinstance(records, dict):
                records = [records]
            elif not isinstance(records, list):
                logger.warning(f"    LLM вернул неожиданный тип: {type(records)}")
                return []
            
            logger.debug(f"    LLM извлек {len(records)} записей")
            return records
            
        except Exception as e:
            logger.error(f"    Ошибка при извлечении данных: {e}")
            return []
    
    def _validate_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Валидирует извлеченные записи.
        
        Returns:
            Список валидных записей
        """
        valid_records = []
        required_fields = [
            "operation_date",
            "department_name",
            "operation_name",
            "crop_name",
            "work_per_day",
            "work_from_start",
            "remaining_work",
        ]
        
        for i, record in enumerate(records):
            try:
                # Проверяем наличие обязательных полей
                missing = [f for f in required_fields if f not in record]
                if missing:
                    logger.debug(f"      Запись {i}: пропущено полей: {missing}")
                    continue
                
                # Проверяем типы
                if not isinstance(record.get("department_name"), str):
                    continue
                if not isinstance(record.get("operation_name"), str):
                    continue
                if not isinstance(record.get("crop_name"), str):
                    continue
                
                # Проверяем пустые строки
                if not record.get("department_name", "").strip():
                    continue
                if not record.get("operation_name", "").strip():
                    continue
                if not record.get("crop_name", "").strip():
                    continue
                
                # Преобразуем числа
                try:
                    record["work_per_day"] = float(record.get("work_per_day", 0))
                    record["work_from_start"] = float(record.get("work_from_start", 0))
                    record["remaining_work"] = float(record.get("remaining_work", 0))
                except (ValueError, TypeError):
                    logger.debug(f"      Запись {i}: ошибка преобразования чисел")
                    continue
                
                # Проверяем неотрицательность
                if record["work_per_day"] < 0:
                    record["work_per_day"] = 0
                if record["work_from_start"] < 0:
                    record["work_from_start"] = 0
                if record["remaining_work"] < 0:
                    record["remaining_work"] = 0
                
                # Пропускаем полностью нулевые записи
                if (record["work_per_day"] == 0 and 
                    record["work_from_start"] == 0 and 
                    record["remaining_work"] == 0):
                    continue
                
                valid_records.append(record)
                
            except Exception as e:
                logger.debug(f"      Запись {i}: ошибка валидации: {e}")
                continue
        
        logger.debug(f"    Валидных записей: {len(valid_records)} из {len(records)}")
        return valid_records
    
    def _post_process(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Постобработка извлеченных данных.
        
        - Нормализация дат
        - Расчет процента выполнения
        - Округление чисел
        - Стандартизация названий
        """
        processed = []
        
        for record in records:
            try:
                # Обработка даты
                date_value = record.get("operation_date")
                if isinstance(date_value, datetime):
                    record["operation_date"] = date_value
                elif isinstance(date_value, str):
                    # Пытаемся распарсить дату из строки
                    try:
                        record["operation_date"] = datetime.strptime(date_value, "%Y-%m-%d")
                    except ValueError:
                        try:
                            record["operation_date"] = datetime.fromisoformat(date_value)
                        except ValueError:
                            logger.debug(f"      Не удалось распарсить дату: {date_value}")
                            continue
                else:
                    continue
                
                # Расчет процента выполнения
                work_from_start = record["work_from_start"]
                remaining_work = record["remaining_work"]
                total_plan = work_from_start + remaining_work
                
                if total_plan > 0:
                    record["completion_percent"] = work_from_start / total_plan
                else:
                    record["completion_percent"] = 1.0 if work_from_start > 0 else 0.0
                
                # Округление чисел до 2 знаков
                record["work_per_day"] = round(record["work_per_day"], 2)
                record["work_from_start"] = round(record["work_from_start"], 2)
                record["remaining_work"] = round(record["remaining_work"], 2)
                record["completion_percent"] = round(record["completion_percent"], 4)
                
                # Стандартизация названий (убираем лишние пробелы)
                record["department_name"] = record["department_name"].strip()
                record["operation_name"] = record["operation_name"].strip()
                record["crop_name"] = record["crop_name"].strip()
                
                processed.append(record)
                
            except Exception as e:
                logger.debug(f"      Ошибка постобработки: {e}")
                continue
        
        return processed
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику работы парсера"""
        llm_stats = self.llm_client.get_statistics()
        return {
            **llm_stats,
            "structure_cache_size": len(self.structure_cache),
        }
    
    def clear_cache(self):
        """Очищает все кэши"""
        self.structure_cache.clear()
        self.llm_client.clear_cache()
        logger.info("Кэш LLMParser очищен")

