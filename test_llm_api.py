"""
Тестовый скрипт для проверки стабильности gptunnel.ru API
Запуск: python test_llm_api.py
"""

import time
import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

# Добавляем src в path для импорта конфига
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Загружаем .env
load_dotenv()

# Импортируем переменные из data_parser (там они уже настроены)
from data_processing.data_parser import LLM_API_KEY, LLM_BASE_URL

if not LLM_API_KEY:
    print("❌ ОШИБКА: Не найден LLM_API_KEY!")
    print("Убедитесь что переменная окружения установлена или есть .env файл")
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

def test_request(request_num: int, delay: float = 0):
    """Выполняет один тестовый запрос"""
    
    if delay > 0:
        print(f"\n⏳ Пауза {delay}с...")
        time.sleep(delay)
    
    print(f"\n{'='*60}")
    print(f"🔄 Запрос #{request_num}")
    print(f"{'='*60}")
    
    # Простой промпт
    prompt = {
        "role": "user",
        "content": "Return JSON: {\"test\": \"success\", \"number\": " + str(request_num) + "}"
    }
    
    start_time = time.time()
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Always respond with valid JSON."},
                prompt
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content
        
        print(f"✅ УСПЕХ")
        print(f"⏱️  Время: {elapsed:.2f}с")
        print(f"📝 Ответ: {content[:100]}...")
        
        return {
            "success": True,
            "time": elapsed,
            "request_num": request_num
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
            "request_num": request_num
        }


def main():
    print("="*60)
    print("🔬 ТЕСТ СТАБИЛЬНОСТИ gptunnel.ru API")
    print("="*60)
    
    # Тест 1: Быстрые последовательные запросы (без паузы)
    print("\n\n📊 ТЕСТ 1: Быстрые последовательные запросы (без пауз)")
    print("-"*60)
    
    results_fast = []
    for i in range(1, 6):  # 5 запросов
        result = test_request(i, delay=0)
        results_fast.append(result)
    
    # Тест 2: Запросы с паузой 3 секунды
    print("\n\n📊 ТЕСТ 2: Запросы с паузой 3 секунды")
    print("-"*60)
    
    results_delayed = []
    for i in range(6, 11):  # еще 5 запросов
        result = test_request(i, delay=3.0)
        results_delayed.append(result)
    
    # Статистика
    print("\n\n" + "="*60)
    print("📈 СТАТИСТИКА")
    print("="*60)
    
    # Тест 1
    success_fast = [r for r in results_fast if r['success']]
    failed_fast = [r for r in results_fast if not r['success']]
    
    print(f"\n🏃 ТЕСТ 1 (без пауз):")
    print(f"  ✅ Успешных: {len(success_fast)}/{len(results_fast)}")
    print(f"  ❌ Ошибок: {len(failed_fast)}/{len(results_fast)}")
    
    if success_fast:
        avg_time_fast = sum(r['time'] for r in success_fast) / len(success_fast)
        print(f"  ⏱️  Среднее время: {avg_time_fast:.2f}с")
        times_str = [f"{r['time']:.1f}с" for r in success_fast]
        print(f"  📊 Времена: {times_str}")
    
    if failed_fast:
        print(f"  🔴 Номера провалившихся запросов: {[r['request_num'] for r in failed_fast]}")
    
    # Тест 2
    success_delayed = [r for r in results_delayed if r['success']]
    failed_delayed = [r for r in results_delayed if not r['success']]
    
    print(f"\n🚶 ТЕСТ 2 (с паузой 3с):")
    print(f"  ✅ Успешных: {len(success_delayed)}/{len(results_delayed)}")
    print(f"  ❌ Ошибок: {len(failed_delayed)}/{len(results_delayed)}")
    
    if success_delayed:
        avg_time_delayed = sum(r['time'] for r in success_delayed) / len(success_delayed)
        print(f"  ⏱️  Среднее время: {avg_time_delayed:.2f}с")
        times_str_delayed = [f"{r['time']:.1f}с" for r in success_delayed]
        print(f"  📊 Времена: {times_str_delayed}")
    
    if failed_delayed:
        print(f"  🔴 Номера провалившихся запросов: {[r['request_num'] for r in failed_delayed]}")
    
    # Общий вывод
    print(f"\n🎯 ОБЩИЙ РЕЗУЛЬТАТ:")
    total_success = len(success_fast) + len(success_delayed)
    total_requests = len(results_fast) + len(results_delayed)
    success_rate = (total_success / total_requests) * 100
    
    print(f"  Всего запросов: {total_requests}")
    print(f"  Успешных: {total_success} ({success_rate:.1f}%)")
    print(f"  Ошибок: {total_requests - total_success} ({100-success_rate:.1f}%)")
    
    if success_rate < 80:
        print(f"\n  ⚠️  ВЫВОД: API нестабилен! Рекомендуется использовать алгоритмические парсеры как основные.")
    elif len(failed_fast) > len(failed_delayed):
        print(f"\n  💡 ВЫВОД: Пауза между запросами помогает, но API всё равно нестабилен.")
    else:
        print(f"\n  ✅ ВЫВОД: API работает стабильно.")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()

