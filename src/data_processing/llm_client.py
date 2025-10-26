import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://gptunnel.ru/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
#LLM_MAX_TOKENS = float(os.getenv("LLM_MAX_TOKENS", "16000"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
#LLM_MAX_RETRIES = float(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60.0"))
#LLM_ENABLE_CACHE = bool(os.getenv("LLM_ENABLE_CACHE", "True"))

class LLMClient:
    
    def __init__(self):
        self.client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL
        )
        self.model = LLM_MODEL
    
    def determine_table_type(
        self, 
        sheet_data: Dict[str, Any], 
        file_name: str
    ) -> str:
        
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
            
            logger.info(f"Определен тип таблицы {file_name}: {table_type}")
            return table_type
            
        except Exception as e:
            logger.error(f"Ошибка при определении типа таблицы {file_name}: {e}")
            return "daily_report"
    
    def extract_table_data(
        self, 
        sheet_data: Dict[str, Any], 
        file_name: str
    ) -> List[Dict[str, Any]]:
        
        try:
            prompt = self._build_extraction_prompt(sheet_data, file_name)
            
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
                temperature=LLM_TEMPERATURE,
                timeout=LLM_TIMEOUT,
                #max_tokens=LLM_MAX_TOKENS,
                #enable_cache=LLM_ENABLE_CACHE,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            if "records" in result:
                logger.info(f"Извлечено {len(result['records'])} записей через LLM из {file_name}")
                return result["records"]
            else:
                logger.warning(f"LLM вернул ответ без поля 'records' для {file_name}")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка при обращении к LLM для {file_name}: {e}")
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
2. Find department/enterprise name:
   - Look in header area (first 3-4 rows)
   - It can be any company or department name
   - Examples: "ПУ Север", "Агрохолдинг Рассвет", "ООО Колос", etc.
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

