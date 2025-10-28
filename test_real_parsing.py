"""
Тестовый скрипт для воспроизведения реальной генерации отчёта
Парсит файлы точно так же как при генерации, но БЕЗ asyncio
"""

import sys
import os
from pathlib import Path
import time

# Добавляем src в path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

from data_processing.data_parser import DataParser

def test_parsing_sync():
    """Синхронная версия - как в обычном скрипте"""
    print("="*60)
    print("🔬 ТЕСТ: Синхронный парсинг файлов")
    print("="*60)
    
    shared_files = Path("shared_files")
    
    if not shared_files.exists():
        print(f"❌ Папка {shared_files} не найдена!")
        return
    
    files = list(shared_files.glob("*.xlsx"))
    if not files:
        print(f"❌ Нет файлов в {shared_files}!")
        return
    
    print(f"\n📂 Найдено файлов: {len(files)}")
    for f in files:
        print(f"   - {f.name}")
    
    print(f"\n⏱️  Начало парсинга...")
    start_time = time.time()
    
    try:
        parser = DataParser(shared_files)
        all_data = parser.parse_all_files()
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ УСПЕХ!")
        print(f"⏱️  Время: {elapsed:.1f}с")
        print(f"📊 Извлечено записей: {len(all_data)}")
        
        return True
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ ОШИБКА: {type(e).__name__}")
        print(f"⏱️  Время до ошибки: {elapsed:.1f}с")
        print(f"📝 Детали: {str(e)[:500]}")
        
        import traceback
        traceback.print_exc()
        
        return False


def test_parsing_in_thread():
    """Версия с threading - как в report_scheduler"""
    print("\n\n" + "="*60)
    print("🔬 ТЕСТ: Парсинг в отдельном thread")
    print("="*60)
    
    import threading
    
    result = {"success": False, "time": 0, "error": None}
    
    def parse_in_thread():
        shared_files = Path("shared_files")
        
        if not shared_files.exists():
            result["error"] = "Папка не найдена"
            return
        
        print(f"\n📂 Thread ID: {threading.current_thread().ident}")
        print(f"⏱️  Начало парсинга в thread...")
        
        start_time = time.time()
        
        try:
            parser = DataParser(shared_files)
            all_data = parser.parse_all_files()
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ УСПЕХ в thread!")
            print(f"⏱️  Время: {elapsed:.1f}с")
            print(f"📊 Извлечено записей: {len(all_data)}")
            
            result["success"] = True
            result["time"] = elapsed
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ ОШИБКА в thread: {type(e).__name__}")
            print(f"⏱️  Время до ошибки: {elapsed:.1f}с")
            print(f"📝 Детали: {str(e)[:500]}")
            
            result["error"] = str(e)
            result["time"] = elapsed
            
            import traceback
            traceback.print_exc()
    
    thread = threading.Thread(target=parse_in_thread)
    thread.start()
    thread.join()
    
    return result["success"]


def test_parsing_in_asyncio():
    """Версия с asyncio.to_thread - КАК В ГЕНЕРАЦИИ!"""
    print("\n\n" + "="*60)
    print("🔬 ТЕСТ: Парсинг через asyncio.to_thread (КАК В ГЕНЕРАЦИИ)")
    print("="*60)
    
    import asyncio
    
    async def parse_async():
        shared_files = Path("shared_files")
        
        if not shared_files.exists():
            print(f"❌ Папка {shared_files} не найдена!")
            return False
        
        print(f"\n⏱️  Начало парсинга через asyncio.to_thread...")
        start_time = time.time()
        
        try:
            def blocking_parse():
                parser = DataParser(shared_files)
                return parser.parse_all_files()
            
            # Запускаем в отдельном thread через asyncio.to_thread
            all_data = await asyncio.to_thread(blocking_parse)
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ УСПЕХ через asyncio!")
            print(f"⏱️  Время: {elapsed:.1f}с")
            print(f"📊 Извлечено записей: {len(all_data)}")
            
            return True
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ ОШИБКА через asyncio: {type(e).__name__}")
            print(f"⏱️  Время до ошибки: {elapsed:.1f}с")
            print(f"📝 Детали: {str(e)[:500]}")
            
            import traceback
            traceback.print_exc()
            
            return False
    
    # Запускаем в event loop
    return asyncio.run(parse_async())


def test_parsing_in_new_event_loop():
    """Версия с новым event loop - КАК В _scheduled_generation!"""
    print("\n\n" + "="*60)
    print("🔬 ТЕСТ: Парсинг в НОВОМ event loop (КАК В РАСПИСАНИИ)")
    print("="*60)
    
    import asyncio
    
    async def parse_async():
        shared_files = Path("shared_files")
        
        if not shared_files.exists():
            print(f"❌ Папка {shared_files} не найдена!")
            return False
        
        print(f"\n⏱️  Начало парсинга в новом event loop...")
        start_time = time.time()
        
        try:
            def blocking_parse():
                parser = DataParser(shared_files)
                return parser.parse_all_files()
            
            # Запускаем в отдельном thread
            all_data = await asyncio.to_thread(blocking_parse)
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ УСПЕХ в новом event loop!")
            print(f"⏱️  Время: {elapsed:.1f}с")
            print(f"📊 Извлечено записей: {len(all_data)}")
            
            return True
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ ОШИБКА в новом event loop: {type(e).__name__}")
            print(f"⏱️  Время до ошибки: {elapsed:.1f}с")
            print(f"📝 Детали: {str(e)[:500]}")
            
            import traceback
            traceback.print_exc()
            
            return False
    
    # Создаём НОВЫЙ event loop как в _scheduled_generation
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(parse_async())
    finally:
        loop.close()
    
    return result


def main():
    print("="*60)
    print("🎯 ВОСПРОИЗВЕДЕНИЕ УСЛОВИЙ ГЕНЕРАЦИИ ОТЧЁТА")
    print("="*60)
    print("\nЗапускаем 4 варианта парсинга:")
    print("1. Синхронный (обычный скрипт)")
    print("2. В отдельном thread")
    print("3. Через asyncio.to_thread")
    print("4. В новом event loop (как в расписании)")
    print("\nКакой из них воспроизведёт timeout?\n")
    
    results = {}
    
    # Тест 1
    results["sync"] = test_parsing_sync()
    
    # Тест 2
    results["thread"] = test_parsing_in_thread()
    
    # Тест 3
    results["asyncio"] = test_parsing_in_asyncio()
    
    # Тест 4
    results["new_loop"] = test_parsing_in_new_event_loop()
    
    # Итоги
    print("\n\n" + "="*60)
    print("📈 ИТОГИ")
    print("="*60)
    
    print(f"\n✅ Успешные:")
    for name, success in results.items():
        icon = "✅" if success else "❌"
        print(f"   {icon} {name:15} {'SUCCESS' if success else 'FAILED'}")
    
    failed = [name for name, success in results.items() if not success]
    
    if not failed:
        print(f"\n✅ ВСЕ ТЕСТЫ ПРОШЛИ!")
        print(f"   Проблема НЕ в asyncio/threading.")
        print(f"   Проблема скорее всего в самом API (нестабильность).")
    else:
        print(f"\n⚠️  ПРОВАЛИВШИЕСЯ ТЕСТЫ: {', '.join(failed)}")
        print(f"   Проблема ВОСПРОИЗВЕДЕНА!")
        if "new_loop" in failed or "asyncio" in failed:
            print(f"   Причина: asyncio + синхронный OpenAI клиент!")
            print(f"   Решение: использовать async OpenAI клиент или только sync парсеры")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()

