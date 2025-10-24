"""
Тест подключения к gptunnel API.

Проверяет работоспособность LLM клиента перед основной разработкой.
"""

import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

import logging
from data_processing.llm_client import LLMClient
from data_processing.llm_config import get_llm_config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def test_basic_connection():
    """Тест базового подключения к API"""
    print("\n" + "=" * 80)
    print("ТЕСТ 1: Базовое подключение к gptunnel API")
    print("=" * 80)
    
    try:
        # Загружаем конфигурацию
        config = get_llm_config()
        print(f"✅ Конфигурация загружена: {config}")
        
        # Создаем клиент
        client = LLMClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            temperature=config.temperature,
        )
        print(f"✅ LLM клиент создан: {client}")
        
        # Простой тестовый запрос
        response = client.send_request(
            prompt="Привет! Ответь одним словом: работает ли подключение?",
            system_prompt="Ты - помощник для тестирования API. Отвечай кратко."
        )
        
        print(f"\n✅ ПОДКЛЮЧЕНИЕ РАБОТАЕТ!")
        print(f"Ответ от LLM: {response}")
        
        # Показываем статистику
        stats = client.get_statistics()
        print(f"\nСтатистика:")
        print(f"  - Запросов: {stats['total_requests']}")
        print(f"  - Токенов (вход): {stats['total_input_tokens']}")
        print(f"  - Токенов (выход): {stats['total_output_tokens']}")
        print(f"  - Стоимость: ${stats['total_cost']:.4f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
        print("\nВозможные причины:")
        print("  1. Файл .env не создан или не содержит LLM_API_KEY")
        print("  2. API ключ неверный")
        print("  3. Проблемы с сетью")
        print("  4. Не установлены зависимости (pip install openai tiktoken)")
        return False


def test_json_parsing():
    """Тест парсинга JSON из ответа LLM"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Парсинг JSON из ответа")
    print("=" * 80)
    
    try:
        config = get_llm_config()
        client = LLMClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
        )
        
        # Запрос на возврат JSON
        response = client.send_request(
            prompt="""
Верни простой JSON объект со следующими полями:
- test: true
- message: "Hello from LLM"
- number: 42

Верни ТОЛЬКО валидный JSON, без дополнительного текста.
""",
            system_prompt="Ты возвращаешь только валидный JSON."
        )
        
        print(f"Ответ LLM:\n{response}\n")
        
        # Парсим JSON
        parsed = client.parse_json_response(response)
        print(f"✅ JSON успешно распарсен:")
        print(f"  {parsed}")
        
        # Проверяем содержимое
        assert "test" in parsed, "Поле 'test' отсутствует"
        assert "message" in parsed, "Поле 'message' отсутствует"
        assert "number" in parsed, "Поле 'number' отсутствует"
        
        print(f"✅ Все поля присутствуют")
        
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False


def test_structure_analysis_prompt():
    """Тест промпта для анализа структуры Excel файла"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Анализ структуры (тестовый промпт)")
    print("=" * 80)
    
    try:
        config = get_llm_config()
        client = LLMClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            temperature=0.1,
        )
        
        # Тестовый образец данных из Excel
        sample_data = """
Строка 1: 
Строка 2: 16.07.2025
Строка 3: ПУ Север
Строка 4: Операция | Культура | План | Факт | Остаток
Строка 5: 
Строка 6: Посев | Пшеница | 100 | 80 | 20
Строка 7: Уборка | Ячмень | 50 | 30 | 20
"""
        
        prompt = f"""
Проанализируй структуру таблицы и найди:
1. В какой строке дата? (ответь числом)
2. В какой строке подразделение? (ответь числом)
3. С какой строки начинаются данные? (ответь числом)

Образец:
{sample_data}

Ответь в формате JSON:
{{
  "date_row": число,
  "dept_row": число,
  "data_start": число
}}

Верни ТОЛЬКО JSON.
"""
        
        response = client.send_request(
            prompt=prompt,
            system_prompt="Ты - эксперт по анализу табличных данных. Отвечай только JSON."
        )
        
        print(f"Ответ LLM:\n{response}\n")
        
        # Парсим
        result = client.parse_json_response(response)
        print(f"✅ Результат анализа:")
        print(f"  Дата в строке: {result.get('date_row')}")
        print(f"  Подразделение в строке: {result.get('dept_row')}")
        print(f"  Данные начинаются со строки: {result.get('data_start')}")
        
        # Проверяем корректность
        assert result.get('date_row') == 2, "Дата должна быть в строке 2"
        assert result.get('dept_row') == 3, "Подразделение должно быть в строке 3"
        assert result.get('data_start') == 6, "Данные должны начинаться со строки 6"
        
        print(f"\n✅ LLM ПРАВИЛЬНО ОПРЕДЕЛИЛ СТРУКТУРУ!")
        
        # Показываем статистику
        stats = client.get_statistics()
        print(f"\nОбщая статистика:")
        print(f"  - Всего запросов: {stats['total_requests']}")
        print(f"  - Успешных: {stats['total_requests'] - stats['failed_requests']}")
        print(f"  - Общая стоимость: ${stats['total_cost']:.4f}")
        print(f"  - Средняя стоимость запроса: ${stats['avg_cost_per_request']:.4f}")
        
        return True
        
    except AssertionError as e:
        print(f"❌ LLM определил структуру неверно: {e}")
        print("   Возможно, нужно улучшить промпт")
        return False
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False


def test_cache():
    """Тест кэширования"""
    print("\n" + "=" * 80)
    print("ТЕСТ 4: Кэширование ответов")
    print("=" * 80)
    
    try:
        config = get_llm_config()
        client = LLMClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
        )
        
        # Первый запрос
        import time
        prompt = "Сколько будет 2+2? Ответь одним числом."
        
        start = time.time()
        response1 = client.send_request(prompt)
        time1 = time.time() - start
        print(f"Первый запрос: {time1:.2f}s -> {response1}")
        
        # Второй запрос (должен взяться из кэша)
        start = time.time()
        response2 = client.send_request(prompt)
        time2 = time.time() - start
        print(f"Второй запрос (кэш): {time2:.2f}s -> {response2}")
        
        # Проверяем
        assert response1 == response2, "Ответы должны совпадать"
        assert time2 < time1 / 2, "Кэшированный запрос должен быть быстрее"
        
        print(f"\n✅ Кэш работает! Ускорение: {time1/time2:.1f}x")
        print(f"   Размер кэша: {len(client.cache)} записей")
        
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False


def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 80)
    print("🚀 ТЕСТИРОВАНИЕ LLM ИНТЕГРАЦИИ")
    print("=" * 80)
    print()
    
    results = []
    
    # Тест 1: Базовое подключение
    results.append(("Базовое подключение", test_basic_connection()))
    
    # Тест 2: Парсинг JSON
    results.append(("Парсинг JSON", test_json_parsing()))
    
    # Тест 3: Анализ структуры
    results.append(("Анализ структуры", test_structure_analysis_prompt()))
    
    # Тест 4: Кэширование
    results.append(("Кэширование", test_cache()))
    
    # Итоговый отчет
    print("\n" + "=" * 80)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{status}: {name}")
    
    print(f"\nИтого: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! LLM интеграция готова к разработке.")
        print("\nСледующие шаги:")
        print("  1. Этап 2: Расширить DataReader")
        print("  2. Этап 3: Создать LLMParser")
        print("  3. Этап 4: Интеграция и тестирование")
    else:
        print("\n⚠️  Некоторые тесты провалены. Исправьте проблемы перед продолжением.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

