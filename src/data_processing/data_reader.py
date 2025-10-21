import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
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
