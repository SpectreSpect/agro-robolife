# План интеграции LLM-based парсинга

## Цель
Заменить жесткие парсеры (`DailyReportParser`, `OperationalReportParser`) на гибкий LLM-based парсер, который сможет извлекать данные из Excel файлов **любой структуры**.

---

## Архитектура решения

```
Excel файл → DataReader (метаданные) → LLMParser (анализ + извлечение) → Структурированные данные → TableBuilder
```

### Текущая структура проекта

**Модули:**
- `DataReader` (data_reader.py) - читает Excel, создает метаданные
- `DataParser` (data_parser.py) - **ТРЕБУЕТ ПОЛНОЙ ПЕРЕРАБОТКИ**
- `TableBuilder` (table_builder.py) - **БЕЗ ИЗМЕНЕНИЙ**

**Целевая структура данных** (должна остаться неизменной):
```python
{
    "operation_date": datetime,
    "department_name": str,
    "operation_name": str,
    "crop_name": str,
    "work_per_day": float,
    "work_from_start": float,
    "remaining_work": float,
    "completion_percent": float
}
```

---

## ЭТАП 1: Подготовка инфраструктуры (1-2 дня)

### 1.1 Создание LLM клиента
**Файл:** `src/data_processing/llm_client.py`

**Функциональность:**
- [ ] Обертка над OpenAI SDK с кастомным base_url (gptunnel)
- [ ] Retry логика с exponential backoff (3-5 попыток)
- [ ] Обработка ошибок (rate limit, timeout, invalid response)
- [ ] Логирование всех запросов/ответов в отдельный файл
- [ ] Подсчет токенов и стоимости запросов
- [ ] Поддержка streaming (опционально)
- [ ] Кэширование ответов для идентичных запросов

**API конфигурация:**
```python
BASE_URL = "https://gptunnel.ru/v1"
API_KEY = "shds-394Eyp7326LMrK0NuM4AR8ywac6"
MODEL = "gpt-4o-mini"  # основная модель
FALLBACK_MODEL = "gpt-3.5-turbo"  # запасная
MAX_TOKENS = 16000
TEMPERATURE = 0.1  # низкая для точности
```

**Основные методы:**
```python
class LLMClient:
    def __init__(self, api_key, base_url, model)
    def send_request(prompt: str, system_prompt: str = None) -> str
    def parse_json_response(response: str) -> dict
    def estimate_tokens(text: str) -> int
    def calculate_cost(input_tokens: int, output_tokens: int) -> float
```

**Тестирование:**
- Unit тесты для всех методов
- Mock тесты для OpenAI API
- Интеграционный тест с реальным API
- Тест на обработку ошибок

---

### 1.2 Обновление requirements.txt
**Файл:** `src/requirements.txt`

**Добавить зависимости:**
```txt
openai>=1.0.0
tiktoken>=0.5.0  # для подсчета токенов
pydantic>=2.0.0  # для валидации JSON
tenacity>=8.0.0  # для retry логики
python-dotenv>=1.0.0  # для .env файлов
```

---

### 1.3 Создание конфигурации
**Файл:** `src/data_processing/llm_config.py`

**Содержимое:**
```python
from pydantic_settings import BaseSettings
from typing import Optional

class LLMConfig(BaseSettings):
    api_key: str
    base_url: str = "https://gptunnel.ru/v1"
    model: str = "gpt-4o-mini"
    max_tokens: int = 16000
    temperature: float = 0.1
    max_retries: int = 3
    timeout: int = 60
    enable_cache: bool = True
    log_requests: bool = True
    
    class Config:
        env_file = ".env"
        env_prefix = "LLM_"
```

**Создать файл `.env`:**
```env
LLM_API_KEY=shds-394Eyp7326LMrK0NuM4AR8ywac6
LLM_BASE_URL=https://gptunnel.ru/v1
LLM_MODEL=gpt-4o-mini
```

---

## ЭТАП 2: Улучшение DataReader (1 день)

### 2.1 Расширение метаданных
**Файл:** `src/data_processing/data_reader.py`

**Цель:** Добавить больше информации для LLM-анализа

**Новые методы:**
- [ ] `extract_cell_values(ws, max_rows=20, max_cols=20)` - первые N строк/колонок
- [ ] `detect_header_rows(ws)` - поиск строки с заголовками
- [ ] `extract_sheet_structure(ws)` - анализ структуры листа
- [ ] `get_merged_cells_info(ws)` - информация об объединенных ячейках
- [ ] `extract_formulas(ws)` - извлечение формул (для понимания связей)

**Расширенный output:**
```python
{
    "file_name": str,
    "file_path": str,
    "file_type": str,
    "sheets": {
        "sheet_name": {
            "shape": (rows, cols),
            "columns": list,
            "sample_data": list,  # первые 20 строк
            "header_row": int,  # номер строки с заголовками
            "data_start_row": int,  # первая строка с данными
            "merged_cells": list,
            "column_types": dict,  # определенные типы колонок
            "has_formulas": bool,
            "structure_hints": dict  # подсказки о структуре
        }
    }
}
```

---

## ЭТАП 3: Разработка LLM-based парсера (3-4 дня)

### 3.1 Создание промпт-шаблонов
**Файл:** `src/data_processing/prompts.py`

**Промпт для анализа структуры файла:**
```python
STRUCTURE_ANALYSIS_PROMPT = """
Ты - эксперт по анализу табличных данных в сельскохозяйственной отчетности.

Проанализируй структуру Excel файла и определи:
1. Тип отчета (дневной отчет, оперативная отчетность, другое)
2. Где находятся ключевые данные:
   - Дата операции
   - Название подразделения/предприятия
   - Операции (посев, уборка и т.д.)
   - Культуры (пшеница, ячмень и т.д.)
   - Числовые показатели (план, факт, остаток)

3. Структура таблицы:
   - Строка с заголовками
   - Первая строка с данными
   - Организация данных (по строкам, колонкам, группировка)

ВАЖНО: Ответь в формате JSON.

Данные файла:
{file_data}

Примеры ячеек:
{sample_cells}
"""

EXTRACTION_PROMPT = """
На основе структуры файла извлеки данные в следующем формате:

[
  {
    "operation_date": "YYYY-MM-DD",
    "department_name": "название подразделения",
    "operation_name": "название операции",
    "crop_name": "название культуры",
    "work_per_day": float,
    "work_from_start": float,
    "remaining_work": float
  }
]

Структура файла:
{structure}

Данные из ячеек:
{cell_data}

Правила:
1. Пропускай пустые строки и итоговые строки
2. Преобразуй даты в формат YYYY-MM-DD
3. Числовые значения должны быть float
4. Если значение отсутствует, используй 0
5. Если не можешь извлечь данные - верни пустой массив

ВАЖНО: Ответь ТОЛЬКО валидным JSON массивом.
"""
```

---

### 3.2 Создание нового LLMParser
**Файл:** `src/data_processing/llm_parser.py`

**Класс структура:**
```python
class LLMParser:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.cache = {}  # кэш для структур файлов
        
    def parse_file(self, file_path: Path, file_metadata: dict) -> List[dict]:
        """Главный метод парсинга файла"""
        
    def _analyze_structure(self, file_metadata: dict) -> dict:
        """Анализ структуры файла через LLM"""
        
    def _extract_data(self, structure: dict, raw_data: dict) -> List[dict]:
        """Извлечение данных на основе структуры"""
        
    def _validate_record(self, record: dict) -> bool:
        """Валидация извлеченной записи"""
        
    def _post_process(self, records: List[dict]) -> List[dict]:
        """Постобработка данных"""
```

**Алгоритм работы:**
1. Получить метаданные от DataReader
2. Отправить первые 20 строк LLM для анализа структуры
3. Получить JSON с описанием структуры
4. Извлечь все данные на основе структуры
5. Отправить сырые данные + структуру LLM для парсинга
6. Валидировать результат
7. Применить постобработку

---

### 3.3 Интеграция с DataParser
**Файл:** `src/data_processing/data_parser.py`

**Изменения:**
```python
class DataParser:
    def __init__(self, data_dir: Path, use_llm: bool = True):
        self.data_dir = data_dir
        self.use_llm = use_llm
        
        if use_llm:
            from .llm_client import LLMClient
            from .llm_parser import LLMParser
            from .llm_config import LLMConfig
            
            config = LLMConfig()
            llm_client = LLMClient(config)
            self.llm_parser = LLMParser(llm_client)
        else:
            # Fallback на старые парсеры
            self.llm_parser = None
    
    def parse_all_files(self) -> List[Dict[str, Any]]:
        all_data = []
        
        # Получить метаданные от DataReader
        reader = DataReader(str(self.data_dir))
        files_metadata = reader.read_all_files()
        
        for file_meta in files_metadata:
            if self.use_llm:
                # LLM-based парсинг
                file_path = Path(file_meta['file_path'])
                records = self.llm_parser.parse_file(file_path, file_meta)
                all_data.extend(records)
            else:
                # Старый метод (fallback)
                all_data.extend(self._legacy_parse(file_meta))
        
        return all_data
    
    def _legacy_parse(self, file_meta):
        """Старая логика с DailyReportParser/OperationalReportParser"""
        # Оставить для отката
```

---

## ЭТАП 4: Валидация и тестирование (2-3 дня)

### 4.1 Создание тестовых данных
**Директория:** `tests/test_data/`

**Создать:**
- [ ] `daily_report_sample.xlsx` - пример дневного отчета
- [ ] `operational_report_sample.xlsx` - пример оперативной отчетности
- [ ] `mixed_format.xlsx` - файл с нестандартной структурой
- [ ] `expected_output.json` - эталонные результаты

---

### 4.2 Unit тесты
**Файл:** `tests/test_llm_parser.py`

**Тесты:**
- [ ] `test_structure_analysis()` - анализ структуры
- [ ] `test_data_extraction()` - извлечение данных
- [ ] `test_validation()` - валидация записей
- [ ] `test_date_parsing()` - обработка дат
- [ ] `test_empty_file()` - пустой файл
- [ ] `test_corrupted_data()` - поврежденные данные
- [ ] `test_legacy_fallback()` - откат на старые парсеры

---

### 4.3 Интеграционные тесты
**Файл:** `tests/test_integration.py`

**Тесты:**
- [ ] `test_full_pipeline()` - полный цикл обработки
- [ ] `test_multiple_files()` - обработка нескольких файлов
- [ ] `test_output_format()` - соответствие выходного формата
- [ ] `test_performance()` - производительность (время/стоимость)

---

### 4.4 Сравнительное тестирование
**Скрипт:** `tests/compare_parsers.py`

**Функционал:**
- Запустить оба парсера (старый + LLM) на одинаковых файлах
- Сравнить результаты
- Выявить расхождения
- Сгенерировать отчет

**Метрики:**
- Точность извлечения (precision/recall)
- Время обработки
- Стоимость API запросов
- Количество ошибок

---

## ЭТАП 5: Оптимизация и улучшения (2-3 дня)

### 5.1 Оптимизация промптов
- [ ] A/B тестирование разных промптов
- [ ] Уменьшение размера контекста
- [ ] Few-shot learning (примеры в промпте)
- [ ] Chain-of-thought промптинг для сложных случаев

---

### 5.2 Кэширование
**Файл:** `src/data_processing/cache_manager.py`

**Функционал:**
- [ ] Кэширование структуры файлов по хэшу
- [ ] Кэширование LLM ответов
- [ ] Инвалидация кэша при изменении файла
- [ ] Персистентный кэш (SQLite или Redis)

---

### 5.3 Пакетная обработка
- [ ] Объединение запросов к LLM
- [ ] Параллельная обработка файлов
- [ ] Streaming для больших файлов
- [ ] Rate limiting для API

---

### 5.4 Мониторинг и логирование
**Файл:** `src/data_processing/llm_logger.py`

**Логировать:**
- [ ] Все запросы/ответы LLM
- [ ] Токены и стоимость
- [ ] Время обработки
- [ ] Ошибки и исключения
- [ ] Качество извлечения (метрики)

**Dashboard:**
- Создать простой веб-дашборд для мониторинга
- Статистика использования API
- Графики стоимости
- Журнал ошибок

---

## ЭТАП 6: Документация и деплой (1-2 дня)

### 6.1 Документация
**Файлы:**
- [ ] `docs/LLM_PARSER_GUIDE.md` - руководство по использованию
- [ ] `docs/PROMPTS_ENGINEERING.md` - документация промптов
- [ ] `docs/API_USAGE.md` - использование API
- [ ] `docs/TROUBLESHOOTING.md` - решение проблем

---

### 6.2 Миграция
**Скрипт:** `scripts/migrate_to_llm.py`

**Функционал:**
- [ ] Бэкап текущих парсеров
- [ ] Постепенный переход (feature flag)
- [ ] Откат при ошибках
- [ ] Валидация результатов

**Этапы миграции:**
1. Запуск в режиме сравнения (parallel mode)
2. Ручная проверка результатов
3. Постепенное увеличение доли LLM парсинга
4. Полный переход на LLM
5. Удаление старого кода (опционально)

---

### 6.3 Конфигурация для продакшена
**Файл:** `.env.production`

```env
LLM_API_KEY=shds-394Eyp7326LMrK0NuM4AR8ywac6
LLM_BASE_URL=https://gptunnel.ru/v1
LLM_MODEL=gpt-4o-mini
LLM_MAX_RETRIES=5
LLM_TIMEOUT=120
LLM_ENABLE_CACHE=true
LLM_LOG_REQUESTS=true
LLM_FALLBACK_TO_LEGACY=true
```

---

## ЭТАП 7: Обучение и feedback loop (опционально, 2-3 дня)

### 7.1 Сбор обратной связи
**Файл:** `src/data_processing/feedback_collector.py`

**Функционал:**
- [ ] Пометка неправильно извлеченных данных
- [ ] Ручная коррекция
- [ ] Сохранение примеров
- [ ] Анализ ошибок

---

### 7.2 Улучшение промптов
- [ ] Анализ частых ошибок
- [ ] Добавление примеров в промпт (few-shot)
- [ ] Специализация промптов для разных типов файлов
- [ ] A/B тестирование улучшений

---

## Оценка ресурсов

### Время разработки
- **Этап 1:** 1-2 дня
- **Этап 2:** 1 день
- **Этап 3:** 3-4 дня
- **Этап 4:** 2-3 дня
- **Этап 5:** 2-3 дня
- **Этап 6:** 1-2 дня
- **Этап 7:** 2-3 дня (опционально)

**Итого:** 10-15 рабочих дней (2-3 недели)

---

### Стоимость API (оценка)

**gpt-4o-mini ценообразование:**
- Input: ~$0.15 / 1M токенов
- Output: ~$0.60 / 1M токенов

**Оценка на файл:**
- Анализ структуры: ~2000 input + 500 output токенов = $0.0006
- Извлечение данных: ~5000 input + 2000 output токенов = $0.002
- **Итого на файл: ~$0.003**

**Для 1000 файлов в месяц:**
- Стоимость: ~$3
- С кэшированием: ~$1-2

---

### Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Низкая точность LLM | Средняя | Высокое | Валидация + fallback на старые парсеры |
| Высокая стоимость API | Низкая | Среднее | Кэширование + оптимизация промптов |
| Rate limiting | Средняя | Среднее | Retry логика + пакетная обработка |
| Изменение API gptunnel | Низкая | Высокое | Абстракция + поддержка нескольких провайдеров |
| Сложная структура файлов | Высокая | Среднее | Few-shot learning + human-in-the-loop |

---

## Критерии успеха

### Минимальные требования (MVP)
- [x] LLM парсер работает на всех текущих файлах
- [x] Точность >= 95% по сравнению со старыми парсерами
- [x] Время обработки < 10 секунд на файл
- [x] Стоимость < $0.01 на файл
- [x] Fallback на старые парсеры при ошибках

### Желаемые улучшения
- [ ] Автоматическая обработка новых форматов
- [ ] Интерактивная коррекция ошибок
- [ ] Мониторинг и алерты
- [ ] Dashboard с метриками

---

## Следующие шаги

1. ✅ Утвердить план с командой
2. ⬜ Настроить окружение (API ключи, .env)
3. ⬜ Начать с Этапа 1: создать `llm_client.py`
4. ⬜ Протестировать подключение к gptunnel API
5. ⬜ Создать минимальный рабочий прототип
6. ⬜ Запустить на тестовых данных
7. ⬜ Итеративно улучшать промпты и точность

---

## Контакты и ресурсы

**API документация:**
- gptunnel: https://gptunnel.ru/docs
- OpenAI SDK: https://platform.openai.com/docs

**Полезные ссылки:**
- Промпт-инжиниринг: https://www.promptingguide.ai/
- Best practices для парсинга: https://cookbook.openai.com/

---

**Автор плана:** AI Assistant  
**Дата создания:** 2025-10-24  
**Версия:** 1.0

