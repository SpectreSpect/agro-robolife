import os
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

from data_processing import DataReader, DataParser, TableBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("agro_processing.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


def main():

    logger.info("=" * 80)
    logger.info("    Система обработки сельскохозяйственных данных")
    logger.info("=" * 80)

    try:

        data_reader = DataReader("data")
        data_parser = DataParser(Path("data"))
        table_builder = TableBuilder("templates/dashboard_template.xlsx")

        logger.info("\n1️⃣ Чтение метаданных файлов...")
        files_info = data_reader.read_all_files()

        if not files_info:
            logger.warning("Не найдено Excel файлов в папке 'data'")
            logger.info("Поместите Excel файлы в папку 'data' для обработки")
            return

        logger.info(f"Найдено {len(files_info)} файлов для обработки")

        for file_info in files_info:
            if file_info.get("has_error"):
                logger.warning(
                    f"Ошибка в файле {file_info['file_name']}: {file_info.get('error', 'Неизвестная ошибка')}"
                )
            else:
                total_sheets = file_info.get("total_sheets", 0)
                logger.info(
                    f"  {file_info['file_name']} ({file_info['file_type']}) - {total_sheets} листов"
                )

        logger.info("\n2️⃣ Парсинг и извлечение данных...")

        all_data = data_parser.parse_all_files()

        if not all_data:
            logger.error("Не удалось извлечь данные из файлов")
            return

        logger.info(f"Извлечено {len(all_data)} записей")

        departments = set(record["department_name"] for record in all_data)
        operations = set(record["operation_name"] for record in all_data)
        crops = set(record["crop_name"] for record in all_data)

        logger.info(
            f"  Подразделения: {len(departments)} ({', '.join(sorted(departments))})"
        )
        logger.info(f"  Операции: {len(operations)} ({', '.join(sorted(operations))})")
        logger.info(f"  Культуры: {len(crops)} ({', '.join(sorted(crops))})")

        logger.info("\n3️⃣ Построение Excel таблицы...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"output_processed_{timestamp}.xlsx"

        success = table_builder.build_table(all_data, output_file, "Отчет за день")

        if success:
            logger.info("\n" + "=" * 80)
            logger.info("✅ Обработка завершена успешно!")
            logger.info(f"📄 Выходной файл: {os.path.abspath(output_file)}")
            logger.info(f"   - Обработано файлов: {len(files_info)}")
            logger.info(f"   - Извлечено записей: {len(all_data)}")
            logger.info(f"   - Подразделений: {len(departments)}")
            logger.info(f"   - Операций: {len(operations)}")
            logger.info(f"   - Культур: {len(crops)}")
            logger.info(f"   - Сводные таблицы обновлены ✓")
            logger.info("=" * 80)
        else:
            logger.error("❌ Ошибка при создании Excel файла")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
