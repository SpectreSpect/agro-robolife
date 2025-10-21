import openpyxl
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


def extract_date_from_filename(filename: str) -> Optional[datetime]:

    match = re.search(r"_(\d{4})\.xlsx$", filename)
    if match:
        date_str = match.group(1)
        day = int(date_str[:2])
        month = int(date_str[2:])
        year = 2025  # Предполагаем 2025 год

        try:
            return datetime(year, month, day)
        except ValueError:
            logger.warning(f"Неверная дата из имени файла: {date_str}")
            return None
    return None


class DailyReportParser:

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.data = []

    def parse(self) -> List[Dict[str, Any]]:

        logger.info(f"Парсинг файла: {self.file_path.name}")

        try:
            wb = openpyxl.load_workbook(self.file_path, data_only=True)
            ws = wb[wb.sheetnames[0]]  # Берем первый лист

            date_cell = ws.cell(2, 1).value
            if isinstance(date_cell, datetime):
                operation_date = date_cell
            else:

                operation_date = extract_date_from_filename(self.file_path.name)
                if operation_date is None:
                    logger.warning(
                        f"Не удалось извлечь дату из файла: {self.file_path.name}"
                    )
                    return []
                logger.info(f"  Дата извлечена из имени файла: {operation_date}")

            department_name = None
            for col in range(1, 10):
                cell_value = ws.cell(3, col).value
                if (
                    cell_value
                    and isinstance(cell_value, str)
                    and cell_value.strip().startswith("ПУ")
                ):
                    department_name = cell_value.strip()
                    break

            if not department_name:
                logger.warning(
                    f"Не удалось извлечь название подразделения из {self.file_path.name}"
                )
                return []

            logger.info(f"  Дата: {operation_date}, Подразделение: {department_name}")

            itogo_col_day = None
            itogo_col_total = None
            ostatok_col = None

            for col in range(1, ws.max_column + 1):
                cell_value = ws.cell(4, col).value
                if cell_value:
                    cell_str = str(cell_value).strip()
                    if cell_str == "Итого":
                        itogo_col_day = col
                        itogo_col_total = col + 1
                    elif cell_str == "Остаток":
                        ostatok_col = col

            if itogo_col_day is None or ostatok_col is None:
                logger.warning(
                    f"Не найдены колонки Итого/Остаток в {self.file_path.name}"
                )
                return []

            for row_idx in range(6, ws.max_row + 1):
                operation_name = ws.cell(row_idx, 1).value
                crop_name = ws.cell(row_idx, 2).value

                if not operation_name or not crop_name:
                    break  # Конец данных

                work_per_day = ws.cell(row_idx, itogo_col_day).value
                work_from_start = ws.cell(row_idx, itogo_col_total).value
                remaining_work = ws.cell(row_idx, ostatok_col).value

                work_per_day = work_per_day if work_per_day is not None else 0
                work_from_start = work_from_start if work_from_start is not None else 0
                remaining_work = remaining_work if remaining_work is not None else 0

                total_plan = work_from_start + remaining_work
                if total_plan > 0:
                    completion_percent = work_from_start / total_plan
                else:
                    completion_percent = 1 if work_from_start > 0 else 0

                record = {
                    "operation_date": operation_date,
                    "department_name": department_name,
                    "operation_name": str(operation_name).strip(),
                    "crop_name": str(crop_name).strip(),
                    "work_per_day": work_per_day,
                    "work_from_start": work_from_start,
                    "remaining_work": remaining_work,
                    "completion_percent": completion_percent,
                }

                self.data.append(record)
                logger.debug(f"    Извлечено: {operation_name} - {crop_name}")

            wb.close()
            logger.info(f"  Извлечено {len(self.data)} записей")
            return self.data

        except Exception as e:
            logger.error(f"Ошибка при парсинге {self.file_path.name}: {e}")
            return []


class OperationalReportParser:

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.data = []

    def parse(self) -> List[Dict[str, Any]]:

        logger.info(f"Парсинг оперативной отчетности: {self.file_path.name}")

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
                col_idx = 2  # Начинаем с колонки B
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

                            work_from_start = plan_total  # План всего
                            work_per_day = fact_current  # Факт на текущую дату
                            remaining_work = (
                                plan_total - fact_current
                            )  # Оставшийся объем работ

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
                                    "work_per_day": work_per_day,  # Факт на текущую дату
                                    "work_from_start": work_from_start,  # План всего
                                    "remaining_work": remaining_work,  # План - Факт
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


class DataParser:

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def parse_all_files(self) -> List[Dict[str, Any]]:

        all_data = []

        daily_report_files = sorted(
            self.data_dir.glob("Таблица_для_дневного_отчета_*.xlsx")
        )
        logger.info(f"Найдено {len(daily_report_files)} файлов дневных отчетов")

        for file_path in daily_report_files:
            parser = DailyReportParser(file_path)
            file_data = parser.parse()
            all_data.extend(file_data)

        logger.info(f"Извлечено {len(all_data)} записей из дневных отчетов")

        operational_files = list(self.data_dir.glob("Оперативная_отчетность_*.xlsx"))
        logger.info(f"Найдено {len(operational_files)} файлов оперативной отчетности")

        for operational_file in operational_files:
            logger.info(
                f"Парсинг файла оперативной отчетности: {operational_file.name}"
            )
            parser = OperationalReportParser(operational_file)
            file_data = parser.parse()

            filtered_data = [
                rec
                for rec in file_data
                if rec["work_from_start"] > 0 or rec["remaining_work"] > 0
            ]
            logger.info(
                f"  Отфильтровано {len(filtered_data)} из {len(file_data)} записей"
            )
            all_data.extend(filtered_data)

        logger.info(f"Всего извлечено записей: {len(all_data)}")

        daily_count = len(
            [
                d
                for d in all_data
                if "source_file" not in d
                or "дневного_отчета" in d.get("source_file", "")
            ]
        )
        operational_count = len(
            [
                d
                for d in all_data
                if "source_file" in d
                and "Оперативная_отчетность" in d.get("source_file", "")
            ]
        )

        logger.info(f"  - Из дневных отчетов: {daily_count}")
        logger.info(f"  - Из оперативной отчетности: {operational_count}")

        return all_data
