import json
import logging
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    
    def __init__(self, api_key: str, base_url: str = "https://gptunnel.ru/v1"):
        # Timeout 30 секунд БЕЗ retries - если API тормозит, лучше сразу использовать fallback
        # Retries бессмысленны при slow API - это просто 3x timeout
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0,  # 30 секунд - достаточно для нормальных ответов
            max_retries=0   # БЕЗ retries - если timeout, сразу fallback на алгоритм
        )
        self.model = "gpt-4o-mini"
    
    def determine_table_type(
        self, 
        sheet_data: Dict[str, Any], 
        file_name: str
    ) -> str:
        
        start_time = time.time()
        try:
            rows_data = sheet_data.get("rows", [])
            rows_sample = rows_data[:20] if len(rows_data) > 20 else rows_data
            
            prompt = f"""Determine the type of this Excel table.

File: {file_name}
Data (first 20 rows):
{json.dumps(rows_sample, ensure_ascii=False, indent=2)}

Analyze and return ONLY ONE of these types:

TYPE A - "daily_report" if:
- Single enterprise/department report
- Contains "Итого" columns for totals
- Has operations and crops in rows
- Typical filename pattern: "Таблица_для_дневного_отчета"

TYPE B - "operational_report" if:
- Multiple enterprises in rows
- Operations spread across columns
- Has sections like "Площадь, га"
- Typical filename pattern: "Оперативная_отчетность"

Return JSON:
{{
  "table_type": "daily_report" or "operational_report"
}}
"""
            
            # Логируем размер промпта для отладки
            prompt_size = len(prompt.encode('utf-8'))
            logger.debug(f"📊 LLM запрос для {file_name}: {prompt_size} байт, {len(rows_sample)} строк")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing Excel table structures. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            table_type = result.get("table_type", "daily_report")
            
            elapsed = time.time() - start_time
            logger.info(f"Определен тип таблицы {file_name}: {table_type} (за {elapsed:.1f}с)")
            return table_type
            
        except Exception as e:
            elapsed = time.time() - start_time
            error_type = type(e).__name__
            logger.error(f"Ошибка при определении типа таблицы {file_name}: {error_type}: {e} (после {elapsed:.1f}с)")
            logger.info(f"Используется дефолтный тип 'daily_report' для {file_name}")
            return "daily_report"
    
    def extract_table_data(
        self, 
        sheet_data: Dict[str, Any], 
        file_name: str
    ) -> List[Dict[str, Any]]:
        
        start_time = time.time()
        try:
            prompt = self._build_extraction_prompt(sheet_data, file_name)
            
            # Логируем размер промпта для отладки
            prompt_size = len(prompt.encode('utf-8'))
            rows_count = len(sheet_data.get("rows", [])[:50])
            logger.debug(f"📊 LLM запрос для парсинга {file_name}: {prompt_size} байт, {rows_count} строк")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting structured data from agricultural reports in Excel format. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            elapsed = time.time() - start_time
            if "records" in result:
                logger.info(f"Извлечено {len(result['records'])} записей через LLM из {file_name} (за {elapsed:.1f}с)")
                return result["records"]
            else:
                logger.warning(f"LLM вернул ответ без поля 'records' для {file_name} (за {elapsed:.1f}с)")
                return []
                
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Ошибка при обращении к LLM для {file_name}: {e} (после {elapsed:.1f}с)")
            return []
    
    def _build_extraction_prompt(
        self, 
        sheet_data: Dict[str, Any], 
        file_name: str
    ) -> str:
        
        rows_data = sheet_data.get("rows", [])
        sheet_name = sheet_data.get("sheet_name", "Unknown")
        
        rows_sample = rows_data[:50] if len(rows_data) > 50 else rows_data
        
        prompt = f"""Extract agricultural data from DAILY REPORT table.

File: {file_name}
Sheet: {sheet_name}

Data (first 50 rows):
{json.dumps(rows_sample, ensure_ascii=False, indent=2)}

This is a DAILY REPORT with single enterprise. Extract data as follows:

1. Find date in header (usually in first 3 rows, cell might contain date) or extract from filename pattern _DDMM.xlsx
2. Find the department or enterprise name:
   * Look in the header area (the first 3 rows).
   * The name cannot be empty.
   * It should represent a company, organization, or department.
   * Ignore any text that looks like a report title or description, such as:
     “Отчет”, “План”, “Свод”, “Данные”, “по”, “за”, “на”, “таблица”, “результаты”, “Отделение”.
   * The name is typically short (1–4 words) and may include forms of ownership like “ПУ”, “ООО”, “ЗАО”, or “АО”.
   * Return only the department or enterprise name — clean text without extra words or formatting.
   * Examples: “ПУ Север”, “Агрохолдинг Рассвет”, “ООО Колос”, ”Прогресс”, ”Мир”.
3. Find header row with column names (look for "Итого", "Остаток" columns)
4. Identify columns:
   - "Итого" columns (there are usually TWO adjacent "Итого" columns)
   - First "Итого" = work per day (объем работ за день)
   - Second "Итого" = work from start (объем работ с начала)
   - "Остаток" = remaining work (оставшийся объем)
5. For EACH data row (after header row):
   - operation_name = first column value (название операции)
   - crop_name = second column value (название культуры)
   - work_per_day = value from first "Итого" column
   - work_from_start = value from second "Итого" column
   - remaining_work = value from "Остаток" column
   - Calculate completion_percent = work_from_start / (work_from_start + remaining_work) if denominator > 0, else 0

RETURN JSON:
{{
  "records": [
    {{
      "operation_date": "YYYY-MM-DD",
      "department_name": "string",
      "operation_name": "string",
      "crop_name": "string",
      "work_per_day": number,
      "work_from_start": number,
      "remaining_work": number,
      "completion_percent": number (0 to 1)
    }}
  ]
}}

CRITICAL RULES:
1. Skip header rows (first 5 rows typically)
2. Skip summary rows starting with "Итого по..."
3. Skip empty rows
4. All numeric values must be numbers, not strings
5. Dates in YYYY-MM-DD format
6. If field unknown, use null for strings or 0 for numbers
7. Return ALL data rows from entire table
8. Extract work values ONLY from "Итого" columns (суммарные значения по всем агрегатам)
"""
        
        return prompt


class ExcelToLLMConverter:
    
    @staticmethod
    def convert_sheet_to_dict(worksheet, sheet_name: str) -> Dict[str, Any]:
        
        rows = []
        max_row = min(worksheet.max_row, 200)
        max_col = min(worksheet.max_column, 50)
        
        for row_idx in range(1, max_row + 1):
            row_data = {}
            for col_idx in range(1, max_col + 1):
                cell = worksheet.cell(row_idx, col_idx)
                cell_value = cell.value
                
                if cell_value is not None:
                    if hasattr(cell_value, 'isoformat'):
                        cell_value = cell_value.isoformat()
                    row_data[f"col_{col_idx}"] = cell_value
            
            if row_data:
                row_data["row_num"] = row_idx
                rows.append(row_data)
        
        return {
            "sheet_name": sheet_name,
            "rows": rows,
            "total_rows": len(rows),
            "max_row": worksheet.max_row,
            "max_column": worksheet.max_column
        }

