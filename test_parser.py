"""
Тестирование алгоритмического парсера на файле ПУ Кавказ.xlsx
"""
from pathlib import Path
from src.data_processing.data_parser import DailyReportAlgorithmicParser
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

file_path = Path("ПУ Кавказ.xlsx")

print("="*80)
print("ТЕСТИРОВАНИЕ АЛГОРИТМИЧЕСКОГО ПАРСЕРА")
print("="*80)
print(f"Файл: {file_path.name}\n")

parser = DailyReportAlgorithmicParser(file_path)
data = parser.parse()

print("\n" + "="*80)
print("РЕЗУЛЬТАТЫ:")
print("="*80)

if data:
    print(f"\nВсего записей: {len(data)}\n")
    
    print("Данные по строкам:")
    print("-" * 80)
    
    for i, record in enumerate(data, 1):
        print(f"\nЗапись {i}:")
        print(f"  Дата: {record['operation_date']}")
        print(f"  Подразделение: {record['department_name']}")
        print(f"  Операция: {record['operation_name']}")
        print(f"  Культура: {record['crop_name']}")
        print(f"  За день: {record['work_per_day']}")
        print(f"  С начала: {record['work_from_start']}")
        print(f"  Остаток: {record['remaining_work']}")
        print(f"  % выполнения: {record['completion_percent']:.2%}")
    
    print("\n" + "="*80)
    print("ПРОВЕРКА ОСТАТКОВ:")
    print("="*80)
    
    ostatok_values = [record['remaining_work'] for record in data]
    print(f"\nПолучено: {ostatok_values}")
    print(f"Ожидалось: [120, 0, 134, 135]")
    
    if ostatok_values == [120, 0, 134, 135]:
        print("\n✅ ТЕСТ ПРОЙДЕН! Остатки извлечены правильно!")
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕН! Остатки не совпадают!")
        
else:
    print("\n❌ ОШИБКА: Не удалось извлечь данные!")

