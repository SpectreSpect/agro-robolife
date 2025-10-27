import pandas as pd
import win32com.client
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class TableBuilder:

    def __init__(self, template_path: str = "templates/dashboard_template.xlsx"):

        self.template_path = Path(template_path)

    def build_table(
        self,
        data: List[Dict[str, Any]],
        output_path: str,
        sheet_name: str = "Отчет за день",
    ) -> bool:
        try:

            if not self.template_path.exists():
                logger.error(f"Шаблон {self.template_path} не найден")
                return False

            df = self._create_dataframe(data)

            if df.empty:
                logger.warning("Нет данных для создания таблицы")
                return False

            success = self._copy_and_fill_workbook(
                str(self.template_path), output_path, sheet_name, df
            )

            if success:
                logger.info(f"Excel таблица успешно создана: {output_path}")
            else:
                logger.error(f"Ошибка при создании Excel таблицы: {output_path}")

            return success

        except Exception as e:
            logger.error(f"Ошибка при построении таблицы: {e}")
            return False

    def _create_dataframe(self, data: List[Dict[str, Any]]) -> pd.DataFrame:

        if not data:
            return pd.DataFrame()

        rows = []
        for i, record in enumerate(data):
            row_num = i + 2  # Номер строки в Excel (начиная с 2)

            completion_formula = f"=IF((F{row_num}+G{row_num})=0,IF(F{row_num}>0,1,0),F{row_num}/(F{row_num}+G{row_num}))"

            operation_date = record.get("operation_date", "")
            if hasattr(operation_date, "strftime"):

                operation_date = operation_date.strftime("%Y-%m-%d")
            elif isinstance(operation_date, str):

                pass
            else:

                operation_date = str(operation_date) if operation_date else ""

            row = {
                "Дата операции": operation_date,
                "Название подразделения": record.get("department_name", ""),
                "Название операции": record.get("operation_name", ""),
                "Наименование культуры": record.get("crop_name", ""),
                "Объем работ за день": record.get("work_per_day", 0),
                "Объем работ с начала": record.get("work_from_start", 0),
                "Оставшийся объем работ": record.get("remaining_work", 0),
                "% выполнения от плана": completion_formula,
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        logger.info(f"Создан DataFrame с {len(df)} строками")
        return df

    def _copy_and_fill_workbook(
        self, source_path: str, output_path: str, sheet_name: str, data: pd.DataFrame
    ) -> bool:

        abs_source = os.path.abspath(source_path)
        abs_output = os.path.abspath(output_path)

        excel = None
        wb_source = None
        wb_output = None

        try:

            excel = win32com.client.Dispatch("Excel.Application")
            
            # Пытаемся установить Visible и DisplayAlerts
            try:
                excel.Visible = False
            except Exception as e:
                logger.warning(f"Не удалось установить Visible=False: {e}")
            
            try:
                excel.DisplayAlerts = False
            except Exception as e:
                logger.warning(f"Не удалось установить DisplayAlerts=False: {e}")

            logger.info(f"Открываем шаблон: {abs_source}")
            wb_source = excel.Workbooks.Open(abs_source)

            logger.info(f"Сохраняем копию: {abs_output}")
            wb_source.SaveAs(abs_output)
            wb_source.Close(SaveChanges=False)

            wb_output = excel.Workbooks.Open(abs_output)
            logger.info("Шаблон успешно скопирован")

            logger.info("Заполняем данными...")
            self._append_data_to_table(wb_output, sheet_name, data)

            logger.info("Обновляем сводные таблицы...")
            self._refresh_pivot_tables(wb_output)

            wb_output.Save()
            logger.info("Файл сохранен")
            wb_output.Close(SaveChanges=False)

            return True

        except Exception as e:
            logger.error(f"Ошибка при копировании и заполнении: {e}")
            return False

        finally:

            try:
                if wb_output is not None:
                    try:
                        wb_output.Close(SaveChanges=False)
                    except:
                        pass
                if wb_source is not None:
                    try:
                        wb_source.Close(SaveChanges=False)
                    except:
                        pass
                if excel is not None:
                    try:
                        excel.Quit()
                    except:
                        pass
            except:
                pass

    def _append_data_to_table(self, wb, sheet_name: str, data: pd.DataFrame):

        try:
            ws = wb.Worksheets(sheet_name)
        except Exception:
            raise ValueError(f"Лист '{sheet_name}' не найден в рабочей книге")

        table = None
        if ws.ListObjects.Count > 0:
            table = ws.ListObjects(1)
            logger.info(f"Найдена существующая таблица: '{table.Name}'")
        else:
            logger.info("Создаем новую таблицу...")
            table = self._create_excel_table(ws, data.columns.tolist())

        header_row = table.HeaderRowRange.Row
        start_row = header_row + 1
        start_col = table.HeaderRowRange.Column
        num_rows = len(data)
        num_cols = len(data.columns)

        data_array = data.values.tolist()

        for i, row in enumerate(data_array):
            for j, val in enumerate(row):
                if isinstance(val, str) and val.startswith("="):

                    pass
                elif pd.isna(val):
                    data_array[i][j] = ""
                elif isinstance(val, (int, float)):
                    data_array[i][j] = float(val)
                else:
                    data_array[i][j] = str(val)

        end_row = start_row + num_rows - 1
        end_col = start_col + num_cols - 1
        data_range = ws.Range(
            ws.Cells(start_row, start_col), ws.Cells(end_row, end_col)
        )
        data_range.Value = data_array  # одна операция вместо тысяч

        table.Resize(
            ws.Range(ws.Cells(header_row, start_col), ws.Cells(end_row, end_col))
        )
        logger.info(
            f"Добавлено {num_rows} строк в таблицу '{table.Name}' за один вызов"
        )

    def _create_excel_table(self, ws, headers: List[str]) -> Any:

        header_row = 1
        num_cols = len(headers)

        for col_idx, header in enumerate(headers, start=1):
            ws.Cells(header_row, col_idx).Value = header

        data_start_row = header_row + 1
        ws.Cells(data_start_row, 1).Value = ""

        table_range = ws.Range(
            ws.Cells(header_row, 1), ws.Cells(data_start_row, num_cols)
        )

        xlSrcRange = 1
        xlYes = 1

        table = ws.ListObjects.Add(
            SourceType=xlSrcRange, Source=table_range, XlListObjectHasHeaders=xlYes
        )
        table.Name = "Table1"
        table.TableStyle = "TableStyleMedium2"

        logger.info(f"Создана таблица: '{table.Name}'")
        return table

    def _refresh_pivot_tables(self, wb):

        pivot_count = 0
        refreshed_count = 0

        table_name = "Table1"
        try:
            report_sheet = wb.Worksheets("Отчет за день")
            if report_sheet.ListObjects.Count > 0:
                actual_table_name = report_sheet.ListObjects(1).Name
                logger.info(f"Источник данных: '{actual_table_name}'")
                table_name = actual_table_name
        except:
            pass

        for ws in wb.Worksheets:
            if ws.PivotTables().Count > 0:
                for pt_idx in range(1, ws.PivotTables().Count + 1):
                    try:
                        pt = ws.PivotTables(pt_idx)

                        if table_name:
                            try:
                                pt.ChangePivotCache(
                                    wb.PivotCaches().Create(
                                        SourceType=1, SourceData=f"{table_name}"
                                    )
                                )
                                logger.info(f"Обновлен источник данных для '{pt.Name}'")
                            except Exception as e:
                                pass

                        pt.ColumnGrand = True
                        pt.RowGrand = True

                        try:
                            pt.RefreshTable()
                            refreshed_count += 1
                            logger.info(
                                f"Обновлена таблица '{pt.Name}' на листе '{ws.Name}'"
                            )
                        except Exception as e:
                            try:
                                pt.PivotCache().Refresh()
                                refreshed_count += 1
                                logger.info(
                                    f"Обновлен кэш для '{pt.Name}' на листе '{ws.Name}'"
                                )
                            except:
                                logger.warning(
                                    f"Не удалось обновить '{pt.Name}' на листе '{ws.Name}'"
                                )

                        pivot_count += 1

                    except Exception as e:
                        logger.warning(
                            f"Ошибка при настройке сводной таблицы {pt_idx} на '{ws.Name}': {e}"
                        )

        logger.info(
            f"Настроено {pivot_count} сводных таблиц, обновлено {refreshed_count}"
        )
