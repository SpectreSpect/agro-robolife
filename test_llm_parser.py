"""
Тест LLM Parser на реальных данных.

Проверяет работу полного pipeline: DataReader -> LLMParser -> validation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import logging
from data_processing import DataParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

def main():
    print("\n" + "=" * 80)
    print("TEST: LLM Parser on Real Data")
    print("=" * 80)
    
    try:
        # Проверяем наличие файлов
        data_dir = Path("data")
        if not data_dir.exists():
            print(f"\nERROR: Directory '{data_dir}' not found")
            return False
        
        excel_files = list(data_dir.glob("*.xlsx"))
        if not excel_files:
            print(f"\nERROR: No Excel files found in '{data_dir}'")
            print("Please add some Excel files to test.")
            return False
        
        print(f"\n1. Found {len(excel_files)} Excel files:")
        for f in excel_files:
            print(f"   - {f.name}")
        
        # Создаем DataParser с LLM
        print("\n2. Initializing LLM Parser...")
        parser = DataParser(data_dir, use_llm=True)
        
        if not parser.use_llm:
            print("   ERROR: LLM Parser not available")
            print("   Possible issues:")
            print("     - LLM_API_KEY not set in .env")
            print("     - Dependencies not installed")
            return False
        
        print("   OK: LLM Parser initialized")
        
        # Парсим файлы
        print("\n3. Parsing files with LLM...")
        records = parser.parse_all_files()
        
        if not records:
            print("   WARNING: No records extracted")
            return False
        
        print(f"   OK: Extracted {len(records)} records")
        
        # Показываем статистику
        print("\n4. Results:")
        print(f"   Total records: {len(records)}")
        
        # Группируем по подразделениям
        departments = set(r.get("department_name") for r in records)
        print(f"   Departments: {len(departments)}")
        for dept in sorted(departments):
            count = sum(1 for r in records if r.get("department_name") == dept)
            print(f"     - {dept}: {count} records")
        
        # Группируем по операциям
        operations = set(r.get("operation_name") for r in records)
        print(f"   Operations: {len(operations)}")
        for op in sorted(operations):
            print(f"     - {op}")
        
        # Показываем первую запись как пример
        if records:
            print("\n5. Sample record:")
            sample = records[0]
            for key, value in sample.items():
                print(f"     {key}: {value}")
        
        # Статистика LLM
        if hasattr(parser, 'llm_parser') and parser.llm_parser:
            stats = parser.llm_parser.get_statistics()
            print("\n6. LLM Statistics:")
            print(f"   Requests: {stats['total_requests']}")
            print(f"   Input tokens: {stats['total_input_tokens']}")
            print(f"   Output tokens: {stats['total_output_tokens']}")
            print(f"   Total cost: ${stats['total_cost']:.4f}")
            print(f"   Avg cost/request: ${stats['avg_cost_per_request']:.4f}")
            print(f"   Cache size: {stats['cache_size']} entries")
        
        print("\n" + "=" * 80)
        print("SUCCESS! LLM Parser works correctly!")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

