import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    
    def __init__(self, api_key: str, base_url: str = "https://gptunnel.ru/v1"):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = "gpt-4o-mini"
    
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
                temperature=0.1,
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
        
        prompt = f"""Extract structured agricultural data from this Excel sheet.

File: {file_name}
Sheet: {sheet_name}

Data (first 50 rows):
{json.dumps(rows_sample, ensure_ascii=False, indent=2)}

Extract ALL records and return JSON with this EXACT structure:
{{
  "records": [
    {{
      "operation_date": "YYYY-MM-DD format or null",
      "department_name": "Department/Enterprise name or null",
      "operation_name": "Operation name or null",
      "crop_name": "Crop name or null",
      "work_per_day": numeric value or 0,
      "work_from_start": numeric value or 0,
      "remaining_work": numeric value or 0,
      "completion_percent": numeric value between 0 and 1 or 0
    }}
  ]
}}

Instructions:
1. Find the date in the table (usually in first few rows, cell like "Дата: DD.MM.YYYY") or extract from filename pattern like "_DDMM.xlsx"
2. Find department/enterprise name (usually starts with "ПУ" or company name)
3. Identify operation types (Культивация, Посев, Боронование, etc.) and crop names (Пшеница, Ячмень, etc.)
4. Extract numeric values for daily work, total work, and remaining work
5. Calculate completion_percent as: work_from_start / (work_from_start + remaining_work) if denominaator > 0, else 0
6. Skip header rows, summary rows (like "Итого"), and empty rows
7. Return ALL data rows from the entire table, not just samples
8. If a field cannot be determined, use null for strings or 0 for numbers
9. Convert all dates to YYYY-MM-DD format
10. Ensure numeric fields are numbers (not strings)
11. Handle both daily report format and operational report format
12. For operational reports with multiple operations in columns, create separate records for each operation
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

