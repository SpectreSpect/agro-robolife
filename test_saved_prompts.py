"""
Тестовый скрипт для проверки сохранённых промптов
Запуск: python test_saved_prompts.py
"""

import time
import os
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Добавляем src в path для импорта конфига
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Загружаем .env
load_dotenv()

# Импортируем переменные из data_parser
from data_processing.data_parser import LLM_API_KEY, LLM_BASE_URL

if not LLM_API_KEY:
    print("❌ ОШИБКА: Не найден LLM_API_KEY!")
    exit(1)

print(f"🔑 API Key: {LLM_API_KEY[:10]}...")
print(f"🌐 Base URL: {LLM_BASE_URL}")

# Инициализация клиента
client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    timeout=30.0,
    max_retries=0
)


def parse_prompt_file(prompt_path: Path):
    """Парсит файл промпта и извлекает метаданные и сам промпт"""
    with open(prompt_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Разделяем на метаданные и промпт
    parts = content.split("="*60 + "\n\n", 1)
    if len(parts) == 2:
        metadata = parts[0]
        prompt = parts[1]
    else:
        metadata = ""
        prompt = content
    
    # Извлекаем тип запроса из метаданных
    request_type = "unknown"
    if "determine_type" in prompt_path.name:
        request_type = "determine_type"
        system_msg = "You are an expert at analyzing Excel table structures. Always respond with valid JSON only."
        response_format = {"type": "json_object"}
    elif "extract_data" in prompt_path.name:
        request_type = "extract_data"
        system_msg = "You are an expert at extracting structured data from agricultural reports in Excel format. Always respond with valid JSON only."
        response_format = {"type": "json_object"}
    else:
        system_msg = "You are a helpful assistant."
        response_format = None
    
    return {
        "path": prompt_path,
        "name": prompt_path.name,
        "metadata": metadata,
        "prompt": prompt,
        "request_type": request_type,
        "system_message": system_msg,
        "response_format": response_format
    }


def test_prompt(prompt_info: dict, delay: float = 0):
    """Тестирует один промпт"""
    
    if delay > 0:
        time.sleep(delay)
    
    print(f"\n{'='*60}")
    print(f"📝 Тестируем: {prompt_info['name']}")
    print(f"   Тип: {prompt_info['request_type']}")
    print(f"   Размер: {len(prompt_info['prompt'].encode('utf-8'))} байт")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        messages = [
            {"role": "system", "content": prompt_info['system_message']},
            {"role": "user", "content": prompt_info['prompt']}
        ]
        
        kwargs = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.1
        }
        
        if prompt_info['response_format']:
            kwargs['response_format'] = prompt_info['response_format']
        
        response = client.chat.completions.create(**kwargs)
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content
        
        print(f"✅ УСПЕХ")
        print(f"⏱️  Время: {elapsed:.2f}с")
        print(f"📄 Ответ: {content[:200]}...")
        
        return {
            "success": True,
            "time": elapsed,
            "name": prompt_info['name']
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        error_type = type(e).__name__
        
        print(f"❌ ОШИБКА: {error_type}")
        print(f"⏱️  Время до ошибки: {elapsed:.2f}с")
        print(f"📝 Детали: {str(e)[:200]}")
        
        return {
            "success": False,
            "time": elapsed,
            "error": error_type,
            "name": prompt_info['name']
        }


def main():
    prompts_dir = Path("debug_prompts")
    
    if not prompts_dir.exists():
        print(f"❌ Папка {prompts_dir} не найдена!")
        print("Сначала сгенерируйте отчёт, чтобы создались файлы промптов.")
        return
    
    # Находим все файлы промптов
    prompt_files = sorted(prompts_dir.glob("*.txt"))
    
    if not prompt_files:
        print(f"❌ Нет файлов промптов в папке {prompts_dir}!")
        return
    
    print("="*60)
    print(f"🔬 ТЕСТ СОХРАНЁННЫХ ПРОМПТОВ")
    print(f"   Найдено промптов: {len(prompt_files)}")
    print("="*60)
    
    # Парсим все промпты
    prompts = [parse_prompt_file(f) for f in prompt_files]
    
    # Группируем по типу
    determine_prompts = [p for p in prompts if p['request_type'] == 'determine_type']
    extract_prompts = [p for p in prompts if p['request_type'] == 'extract_data']
    
    print(f"\n📊 Типы промптов:")
    print(f"   - determine_type: {len(determine_prompts)}")
    print(f"   - extract_data: {len(extract_prompts)}")
    
    # Тестируем все промпты
    results = []
    
    for i, prompt_info in enumerate(prompts, 1):
        # Добавляем паузу 3 секунды между запросами (кроме первого)
        delay = 3.0 if i > 1 else 0
        result = test_prompt(prompt_info, delay=delay)
        results.append(result)
    
    # Статистика
    print("\n\n" + "="*60)
    print("📈 СТАТИСТИКА")
    print("="*60)
    
    success = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"\n✅ Успешных: {len(success)}/{len(results)}")
    print(f"❌ Ошибок: {len(failed)}/{len(results)}")
    
    if success:
        avg_time = sum(r['time'] for r in success) / len(success)
        max_time = max(r['time'] for r in success)
        min_time = min(r['time'] for r in success)
        print(f"\n⏱️  Время:")
        print(f"   Среднее: {avg_time:.2f}с")
        print(f"   Мин: {min_time:.2f}с")
        print(f"   Макс: {max_time:.2f}с")
    
    if failed:
        print(f"\n🔴 Провалившиеся промпты:")
        for r in failed:
            print(f"   - {r['name']} ({r.get('error', 'unknown')})")
        
        # Группируем по типу запроса
        failed_determine = [r for r in failed if 'determine_type' in r['name']]
        failed_extract = [r for r in failed if 'extract_data' in r['name']]
        
        if failed_determine:
            print(f"\n   Тип determine_type: {len(failed_determine)} ошибок")
        if failed_extract:
            print(f"   Тип extract_data: {len(failed_extract)} ошибок")
    
    # Вывод
    success_rate = (len(success) / len(results)) * 100
    
    print(f"\n🎯 ОБЩИЙ РЕЗУЛЬТАТ: {success_rate:.1f}% успешно")
    
    if success_rate < 80:
        print(f"\n⚠️  ВЫВОД: Проблема подтверждена! Реальные промпты вызывают timeout.")
        print(f"   Рекомендация: использовать алгоритмические парсеры как основные.")
    elif len(failed) > 0:
        print(f"\n💡 ВЫВОД: Некоторые промпты нестабильны.")
        print(f"   Проверьте конкретные файлы выше.")
    else:
        print(f"\n✅ ВЫВОД: Все промпты работают стабильно!")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()

