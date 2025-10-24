import os
import pandas as pd
import openpyxl
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DataReader:

    def __init__(self, data_folder: str = "data"):

        self.data_folder = Path(data_folder)
        self.data_folder.mkdir(exist_ok=True)

    def get_excel_files(self) -> List[Path]:
        excel_files = []
        if self.data_folder.exists():

            daily_reports = sorted(
                self.data_folder.glob("Таблица_для_дневного_отчета_*.xlsx")
            )
            excel_files.extend(daily_reports)

            operational_reports = list(
                self.data_folder.glob("Оперативная_отчетность_*.xlsx")
            )
            excel_files.extend(operational_reports)

            other_files = []
            for pattern in ["*.xlsx", "*.xls"]:
                other_files.extend(self.data_folder.glob(pattern))

            for file_path in other_files:
                if (
                    file_path not in excel_files
                    and not file_path.name.startswith("~$")
                    and not file_path.name.startswith(".")
                ):
                    excel_files.append(file_path)

        logger.info(
            f"Найдено {len(excel_files)} Excel файлов в папке {self.data_folder}"
        )
        return excel_files

    def read_excel_file(self, file_path: Path) -> Dict[str, Any]:

        try:

            excel_data = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")

            result = {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_type": self._determine_file_type(file_path.name),
                "sheets": {},
                "total_sheets": len(excel_data),
            }

            for sheet_name, df in excel_data.items():
                result["sheets"][sheet_name] = {
                    "shape": df.shape,
                    "columns": list(df.columns),
                    "has_data": not df.empty,
                    "first_few_rows": (
                        df.head(3).to_dict("records") if not df.empty else []
                    ),
                }

            logger.info(f"Прочитан файл {file_path.name}: {len(excel_data)} листов")
            return result

        except Exception as e:
            logger.error(f"Ошибка при чтении файла {file_path}: {e}")
            return {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_type": "unknown",
                "error": str(e),
                "sheets": {},
            }

    def read_all_files(self) -> List[Dict[str, Any]]:

        excel_files = self.get_excel_files()
        all_data = []

        for file_path in excel_files:
            file_data = self.read_excel_file(file_path)
            all_data.append(file_data)

        logger.info(f"Обработано {len(all_data)} файлов")
        return all_data

    def _determine_file_type(self, filename: str) -> str:

        filename_lower = filename.lower()

        if "дневного_отчета" in filename_lower:
            return "daily_report"
        elif "оперативная_отчетность" in filename_lower:
            return "operational_report"
        elif "модельная" in filename_lower:
            return "model_report"
        else:
            return "other"

    def get_file_info(self, file_data: Dict[str, Any]) -> Dict[str, Any]:

        return {
            "file_name": file_data["file_name"],
            "file_path": file_data["file_path"],
            "file_type": file_data.get("file_type", "unknown"),
            "total_sheets": file_data.get("total_sheets", 0),
            "has_error": "error" in file_data,
        }
    
    # ======================================================================
    # НОВЫЕ МЕТОДЫ ДЛЯ LLM ИНТЕГРАЦИИ
    # ======================================================================
    
    def extract_cell_values(
        self,
        file_path: Path,
        sheet_name: Optional[str] = None,
        max_rows: int = 20,
        max_cols: int = 20
    ) -> List[List[Any]]:
        """
        Извлекает значения ячеек из листа для анализа LLM.
        
        Args:
            file_path: Путь к файлу
            sheet_name: Имя листа (None = первый лист)
            max_rows: Максимальное количество строк
            max_cols: Максимальное количество колонок
        
        Returns:
            Двумерный массив значений ячеек
        """
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb[sheet_name] if sheet_name else wb[wb.sheetnames[0]]
            
            cell_values = []
            for row_idx, row in enumerate(ws.iter_rows(max_row=max_rows, max_col=max_cols, values_only=True), start=1):
                cell_values.append(list(row))
            
            wb.close()
            return cell_values
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении ячеек из {file_path}: {e}")
            return []
    
    def detect_header_rows(self, file_path: Path, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Определяет строку с заголовками в таблице.
        
        Использует эвристики:
        - Строка содержит больше непустых ячеек
        - Ячейки содержат текст (не числа)
        - Форматирование (жирный шрифт, заливка)
        
        Args:
            file_path: Путь к файлу
            sheet_name: Имя листа
        
        Returns:
            Информация о заголовках
        """
        try:
            wb = openpyxl.load_workbook(file_path)
            ws = wb[sheet_name] if sheet_name else wb[wb.sheetnames[0]]
            
            header_candidates = []
            
            # Анализируем первые 10 строк
            for row_idx in range(1, min(11, ws.max_row + 1)):
                row_cells = list(ws[row_idx])
                
                # Подсчитываем непустые текстовые ячейки
                non_empty = sum(1 for cell in row_cells if cell.value is not None)
                text_cells = sum(1 for cell in row_cells if isinstance(cell.value, str))
                
                # Проверяем форматирование
                bold_cells = sum(1 for cell in row_cells if cell.font and cell.font.bold)
                
                score = non_empty + text_cells * 2 + bold_cells * 3
                
                header_candidates.append({
                    "row": row_idx,
                    "score": score,
                    "non_empty": non_empty,
                    "text_cells": text_cells,
                    "bold_cells": bold_cells,
                })
            
            # Выбираем строку с максимальным счетом
            best = max(header_candidates, key=lambda x: x["score"])
            
            wb.close()
            
            return {
                "header_row": best["row"],
                "confidence": best["score"],
                "details": best,
            }
            
        except Exception as e:
            logger.error(f"Ошибка при определении заголовков в {file_path}: {e}")
            return {"header_row": None, "confidence": 0}
    
    def extract_sheet_structure(self, file_path: Path, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Анализирует структуру листа Excel.
        
        Args:
            file_path: Путь к файлу
            sheet_name: Имя листа
        
        Returns:
            Словарь с информацией о структуре
        """
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb[sheet_name] if sheet_name else wb[wb.sheetnames[0]]
            
            # Определяем типы колонок
            column_types = {}
            for col_idx in range(1, min(21, ws.max_column + 1)):
                col_values = []
                for row_idx in range(1, min(21, ws.max_row + 1)):
                    cell = ws.cell(row_idx, col_idx)
                    if cell.value is not None:
                        col_values.append(type(cell.value).__name__)
                
                if col_values:
                    # Определяем преобладающий тип
                    from collections import Counter
                    most_common = Counter(col_values).most_common(1)[0][0]
                    column_types[col_idx] = most_common
            
            # Находим первую строку с данными (пропускаем пустые строки)
            data_start_row = None
            for row_idx in range(1, min(51, ws.max_row + 1)):
                row_values = [ws.cell(row_idx, col).value for col in range(1, min(11, ws.max_column + 1))]
                non_empty = sum(1 for v in row_values if v is not None)
                if non_empty >= 2:  # Хотя бы 2 непустых ячейки
                    data_start_row = row_idx
                    break
            
            wb.close()
            
            return {
                "max_rows": ws.max_row,
                "max_cols": ws.max_column,
                "column_types": column_types,
                "data_start_row": data_start_row,
                "has_formulas": self._check_formulas(file_path, sheet_name),
            }
            
        except Exception as e:
            logger.error(f"Ошибка при анализе структуры {file_path}: {e}")
            return {}
    
    def get_merged_cells_info(self, file_path: Path, sheet_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получает информацию об объединенных ячейках.
        
        Args:
            file_path: Путь к файлу
            sheet_name: Имя листа
        
        Returns:
            Список информации об объединенных ячейках
        """
        try:
            wb = openpyxl.load_workbook(file_path)
            ws = wb[sheet_name] if sheet_name else wb[wb.sheetnames[0]]
            
            merged_cells = []
            for merged_range in ws.merged_cells.ranges:
                # Получаем значение из первой ячейки
                min_row, min_col = merged_range.min_row, merged_range.min_col
                value = ws.cell(min_row, min_col).value
                
                merged_cells.append({
                    "range": str(merged_range),
                    "min_row": min_row,
                    "min_col": min_col,
                    "max_row": merged_range.max_row,
                    "max_col": merged_range.max_col,
                    "value": value,
                })
            
            wb.close()
            return merged_cells
            
        except Exception as e:
            logger.error(f"Ошибка при получении объединенных ячеек из {file_path}: {e}")
            return []
    
    def _check_formulas(self, file_path: Path, sheet_name: Optional[str] = None) -> bool:
        """Проверяет наличие формул в листе"""
        try:
            wb = openpyxl.load_workbook(file_path)  # data_only=False для формул
            ws = wb[sheet_name] if sheet_name else wb[wb.sheetnames[0]]
            
            # Проверяем первые 100 ячеек
            for row in ws.iter_rows(max_row=10, max_col=10):
                for cell in row:
                    if cell.data_type == 'f':  # formula
                        wb.close()
                        return True
            
            wb.close()
            return False
            
        except Exception:
            return False
    
    def read_excel_file_enhanced(self, file_path: Path) -> Dict[str, Any]:
        """
        Расширенное чтение Excel файла с дополнительными метаданными для LLM.
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            Словарь с расширенной информацией о файле
        """
        # Сначала получаем базовую информацию
        base_info = self.read_excel_file(file_path)
        
        if "error" in base_info:
            return base_info
        
        # Добавляем расширенную информацию для каждого листа
        try:
            for sheet_name in base_info["sheets"].keys():
                # Извлекаем первые 20 строк
                sample_data = self.extract_cell_values(file_path, sheet_name, max_rows=20)
                
                # Определяем заголовки
                header_info = self.detect_header_rows(file_path, sheet_name)
                
                # Анализируем структуру
                structure = self.extract_sheet_structure(file_path, sheet_name)
                
                # Получаем объединенные ячейки
                merged_cells = self.get_merged_cells_info(file_path, sheet_name)
                
                # Добавляем к информации о листе
                base_info["sheets"][sheet_name].update({
                    "sample_data": sample_data,
                    "header_row": header_info.get("header_row"),
                    "header_confidence": header_info.get("confidence", 0),
                    "data_start_row": structure.get("data_start_row"),
                    "max_rows": structure.get("max_rows", 0),
                    "max_cols": structure.get("max_cols", 0),
                    "column_types": structure.get("column_types", {}),
                    "has_formulas": structure.get("has_formulas", False),
                    "merged_cells": merged_cells,
                })
                
                logger.debug(
                    f"Расширенные метаданные для {file_path.name}/{sheet_name}: "
                    f"header_row={header_info.get('header_row')}, "
                    f"data_start={structure.get('data_start_row')}"
                )
            
            return base_info
            
        except Exception as e:
            logger.error(f"Ошибка при расширенном чтении {file_path}: {e}")
            return base_info
