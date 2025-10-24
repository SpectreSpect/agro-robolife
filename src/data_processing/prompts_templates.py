"""
Шаблоны промптов для LLM-based парсинга Excel файлов.

Этот модуль содержит все промпты для взаимодействия с LLM.
"""

# ============================================================================
# SYSTEM PROMPTS
# ============================================================================

SYSTEM_PROMPT_ANALYST = """
Ты - эксперт по анализу структурированных данных в сельскохозяйственной отчетности.

Твоя задача:
- Понимать различные форматы Excel таблиц
- Находить ключевые данные (даты, подразделения, операции, культуры, числа)
- Извлекать данные точно и структурированно
- Всегда отвечать валидным JSON

Принципы работы:
1. Точность превыше всего - лучше пропустить данные, чем извлечь неверно
2. Следовать указанному формату JSON строго
3. Обрабатывать русские названия корректно
4. При неуверенности - использовать null вместо догадок
"""

SYSTEM_PROMPT_VALIDATOR = """
Ты - валидатор извлеченных данных.

Твоя задача:
- Проверять корректность извлеченных данных
- Находить несоответствия и ошибки
- Предлагать исправления
- Обеспечивать целостность данных

Принципы:
1. Даты должны быть реалистичными
2. Числа должны быть неотрицательными
3. Названия должны быть непустыми
4. Суммы должны сходиться
"""

# ============================================================================
# СТРУКТУРНЫЙ АНАЛИЗ (Этап 1)
# ============================================================================

STRUCTURE_ANALYSIS_PROMPT_V1 = """
Проанализируй структуру Excel таблицы и определи расположение ключевых данных.

## Образец данных из таблицы:
{sample_data}

## Метаданные файла:
- Имя файла: {file_name}
- Количество строк: {total_rows}
- Количество колонок: {total_cols}
- Лист: {sheet_name}

## Что нужно найти:

1. **Дата операции** (operation_date)
   - Где находится? (строка, колонка)
   - Формат даты

2. **Название подразделения** (department_name)
   - Где находится? (строка, колонка)
   - Примеры: "ПУ Север", "ПУ Юг", название предприятия

3. **Структура таблицы с данными:**
   - Строка с заголовками (header_row)
   - Первая строка с данными (data_start_row)
   - Последняя строка с данными (data_end_row)

4. **Колонки с данными:**
   - operation_name (название операции: посев, уборка, и т.д.)
   - crop_name (культура: пшеница, ячмень, и т.д.)
   - work_per_day (объем работ за день)
   - work_from_start (объем работ с начала)
   - remaining_work (оставшийся объем работ)

5. **Особенности:**
   - Есть ли объединенные ячейки?
   - Есть ли итоговые строки? (пропускаем их)
   - Есть ли группировка данных?

## Формат ответа (строго JSON):

{{
  "file_type": "daily_report" | "operational_report" | "other",
  "date_location": {{
    "row": номер_строки,
    "col": номер_колонки,
    "format": "описание формата"
  }},
  "department_location": {{
    "row": номер_строки,
    "col": номер_колонки
  }},
  "table_structure": {{
    "header_row": номер,
    "data_start_row": номер,
    "data_end_row": номер или null если неизвестно
  }},
  "columns": {{
    "operation_name": номер_колонки,
    "crop_name": номер_колонки,
    "work_per_day": номер_колонки,
    "work_from_start": номер_колонки,
    "remaining_work": номер_колонки
  }},
  "special_notes": [
    "любые важные замечания"
  ]
}}

**ВАЖНО:** Верни только валидный JSON, без дополнительного текста.
"""

# Упрощенная версия для быстрого анализа
STRUCTURE_ANALYSIS_PROMPT_V2_SIMPLE = """
Найди в Excel таблице:
1. Где дата операции?
2. Где название подразделения?
3. С какой строки начинаются данные?
4. В каких колонках: операция, культура, план, факт, остаток?

Образец:
{sample_data}

Ответь JSON:
{{
  "date_row": номер,
  "date_col": номер,
  "dept_row": номер,
  "dept_col": номер,
  "data_start": номер,
  "cols": {{
    "operation": номер,
    "crop": номер,
    "per_day": номер,
    "from_start": номер,
    "remaining": номер
  }}
}}
"""

# ============================================================================
# ИЗВЛЕЧЕНИЕ ДАННЫХ (Этап 2)
# ============================================================================

EXTRACTION_PROMPT_V1 = """
Извлеки данные из Excel таблицы в структурированный формат.

## Структура файла (определена ранее):
{structure}

## Все данные из таблицы:
{table_data}

## Целевой формат:

Каждая запись должна содержать:
- operation_date: дата в формате "YYYY-MM-DD"
- department_name: название подразделения (строка)
- operation_name: название операции (строка)
- crop_name: название культуры (строка)
- work_per_day: объем работ за день (число)
- work_from_start: объем работ с начала (число)
- remaining_work: оставшийся объем работ (число)

## Правила извлечения:

1. **Даты:**
   - Преобразуй в формат YYYY-MM-DD
   - Если дата в заголовке - применяй ко всем записям

2. **Названия:**
   - Убирай лишние пробелы
   - Сохраняй оригинальный регистр
   - Пропускай пустые значения

3. **Числа:**
   - Преобразуй в float
   - Пустые ячейки = 0
   - Убирай пробелы и разделители тысяч

4. **Пропускай:**
   - Строки с "Итого", "Всего", "ИТОГО"
   - Пустые строки
   - Заголовки таблиц

5. **Расчеты:**
   - НЕ делай сам расчеты, только извлекай значения
   - completion_percent будет рассчитан позже

## Формат ответа (строго JSON массив):

[
  {{
    "operation_date": "2025-07-16",
    "department_name": "ПУ Север",
    "operation_name": "Посев",
    "crop_name": "Пшеница",
    "work_per_day": 20.5,
    "work_from_start": 80.0,
    "remaining_work": 19.5
  }},
  ...
]

**ВАЖНО:** 
- Верни только валидный JSON массив
- Если данных нет - верни пустой массив []
- Не добавляй пояснения вне JSON
"""

# Few-shot версия с примерами
EXTRACTION_PROMPT_V2_FEWSHOT = """
Извлеки данные из таблицы. Вот примеры:

## Пример 1:
Входные данные:
```
Строка 2: 16.07.2025
Строка 3: ПУ Север
Строка 6: Посев | Пшеница | 20 | 80 | 20
Строка 7: Уборка | Ячмень | 15 | 50 | 30
```

Выходные данные:
```json
[
  {{
    "operation_date": "2025-07-16",
    "department_name": "ПУ Север",
    "operation_name": "Посев",
    "crop_name": "Пшеница",
    "work_per_day": 20.0,
    "work_from_start": 80.0,
    "remaining_work": 20.0
  }},
  {{
    "operation_date": "2025-07-16",
    "department_name": "ПУ Север",
    "operation_name": "Уборка",
    "crop_name": "Ячмень",
    "work_per_day": 15.0,
    "work_from_start": 50.0,
    "remaining_work": 30.0
  }}
]
```

## Теперь твои данные:

Структура:
{structure}

Данные:
{table_data}

Верни JSON массив в том же формате.
"""

# ============================================================================
# ВАЛИДАЦИЯ И ИСПРАВЛЕНИЕ (Этап 3)
# ============================================================================

VALIDATION_PROMPT = """
Проверь корректность извлеченных данных и исправь ошибки.

## Извлеченные данные:
{extracted_data}

## Правила валидации:

1. **Даты:**
   - Должны быть в 2024-2026 годах
   - Формат YYYY-MM-DD
   - Реальные даты (не 32 января)

2. **Числа:**
   - >= 0 (неотрицательные)
   - Разумные значения (не миллиарды)
   - work_from_start >= work_per_day (обычно)
   - work_from_start + remaining_work = общий план (проверка)

3. **Названия:**
   - Не пустые строки
   - Без лишних пробелов
   - Без специальных символов (кроме дефиса)

4. **Логика:**
   - Если work_from_start + remaining_work = 0, то work_per_day = 0
   - Одинаковые даты для записей из одного файла

## Что делать с ошибками:
- Неверная дата → null
- Отрицательное число → 0
- Пустое название → пропустить запись
- Нелогичные значения → пометить в "warnings"

## Формат ответа:

{{
  "valid_records": [
    {{ ...исправленные записи... }}
  ],
  "invalid_records": [
    {{
      "record": {{ ...оригинальная запись... }},
      "errors": ["описание ошибок"]
    }}
  ],
  "warnings": [
    "общие предупреждения"
  ],
  "statistics": {{
    "total": число,
    "valid": число,
    "invalid": число
  }}
}}
"""

# ============================================================================
# СПЕЦИАЛИЗИРОВАННЫЕ ПРОМПТЫ
# ============================================================================

# Для дневных отчетов
DAILY_REPORT_EXTRACTION = """
Это дневной отчет по форме "Таблица для дневного отчета ПУ".

Особенности:
- Дата обычно в ячейке A2 или в имени файла
- Подразделение в строке 3, начинается с "ПУ"
- Заголовки в строке 4
- Данные с строки 6
- Колонка "Итого" содержит work_per_day
- Следующая колонка содержит work_from_start
- Колонка "Остаток" содержит remaining_work

Извлеки данные:
{table_data}
"""

# Для оперативной отчетности
OPERATIONAL_REPORT_EXTRACTION = """
Это оперативная отчетность в разрезе ТО и культур.

Особенности:
- Многолистовой файл (каждый лист = культура)
- Дата в ячейке B2
- Операции в строке 3 (несколько операций в ряд)
- Предприятия в колонке A (с строки 6)
- Для каждой операции: план (всего) и факт (на дату)
- Пропускать строки с "Итого"

Извлеки данные:
Лист: {sheet_name}
Данные: {table_data}
"""

# ============================================================================
# RE-PROMPTING (при ошибках)
# ============================================================================

REPROMPT_INVALID_JSON = """
Предыдущий ответ не был валидным JSON.

Ошибка: {error_message}

Твой ответ был:
{previous_response}

Пожалуйста, верни ТОЛЬКО валидный JSON без дополнительного текста.
Формат: {expected_format}
"""

REPROMPT_MISSING_FIELDS = """
В ответе отсутствуют обязательные поля.

Полученные данные: {received_data}
Отсутствуют поля: {missing_fields}

Пожалуйста, добавь отсутствующие поля и верни полный JSON.
"""

REPROMPT_WRONG_TYPES = """
Некоторые поля имеют неверный тип данных.

Ошибки типов: {type_errors}

Пожалуйста, исправь типы данных:
- Даты должны быть строками в формате "YYYY-MM-DD"
- Числа должны быть float/int
- Названия должны быть строками

Исправленный JSON:
"""

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def format_sample_data(sample_rows: list, max_rows: int = 20) -> str:
    """
    Форматирует образец данных для промпта.
    
    Args:
        sample_rows: список строк из Excel
        max_rows: максимальное количество строк
    
    Returns:
        Отформатированная строка для промпта
    """
    formatted = []
    for i, row in enumerate(sample_rows[:max_rows], start=1):
        # Фильтруем None и форматируем
        row_values = [str(cell) if cell is not None else "" for cell in row]
        formatted.append(f"Строка {i}: {' | '.join(row_values)}")
    
    return "\n".join(formatted)


def format_structure_json(structure: dict) -> str:
    """
    Форматирует JSON структуры для промпта.
    
    Args:
        structure: словарь со структурой файла
    
    Returns:
        JSON строка с отступами
    """
    import json
    return json.dumps(structure, indent=2, ensure_ascii=False)


def create_fewshot_examples(examples: list) -> str:
    """
    Создает few-shot примеры для промпта.
    
    Args:
        examples: список примеров [{"input": ..., "output": ...}, ...]
    
    Returns:
        Отформатированные примеры
    """
    formatted = []
    for i, example in enumerate(examples, start=1):
        formatted.append(f"## Пример {i}:")
        formatted.append(f"Входные данные:\n{example['input']}")
        formatted.append(f"\nВыходные данные:\n{example['output']}")
        formatted.append("")
    
    return "\n".join(formatted)


def estimate_prompt_tokens(prompt: str) -> int:
    """
    Грубая оценка количества токенов в промпте.
    
    Для русского текста: ~1 токен на 2-3 символа
    
    Args:
        prompt: текст промпта
    
    Returns:
        Примерное количество токенов
    """
    # Простая эвристика для русского текста
    chars = len(prompt)
    return chars // 2


# ============================================================================
# СЛОВАРЬ ПРОМПТОВ ДЛЯ УДОБНОГО ДОСТУПА
# ============================================================================

PROMPTS = {
    # System prompts
    "system_analyst": SYSTEM_PROMPT_ANALYST,
    "system_validator": SYSTEM_PROMPT_VALIDATOR,
    
    # Structure analysis
    "structure_v1": STRUCTURE_ANALYSIS_PROMPT_V1,
    "structure_v2_simple": STRUCTURE_ANALYSIS_PROMPT_V2_SIMPLE,
    
    # Data extraction
    "extraction_v1": EXTRACTION_PROMPT_V1,
    "extraction_v2_fewshot": EXTRACTION_PROMPT_V2_FEWSHOT,
    
    # Specialized
    "daily_report": DAILY_REPORT_EXTRACTION,
    "operational_report": OPERATIONAL_REPORT_EXTRACTION,
    
    # Validation
    "validation": VALIDATION_PROMPT,
    
    # Re-prompting
    "reprompt_json": REPROMPT_INVALID_JSON,
    "reprompt_fields": REPROMPT_MISSING_FIELDS,
    "reprompt_types": REPROMPT_WRONG_TYPES,
}


def get_prompt(name: str, **kwargs) -> str:
    """
    Получить промпт по имени с подстановкой параметров.
    
    Args:
        name: имя промпта из словаря PROMPTS
        **kwargs: параметры для форматирования
    
    Returns:
        Отформатированный промпт
    
    Example:
        >>> prompt = get_prompt("structure_v1", 
        ...                     sample_data="...",
        ...                     file_name="report.xlsx")
    """
    if name not in PROMPTS:
        raise ValueError(f"Промпт '{name}' не найден. Доступные: {list(PROMPTS.keys())}")
    
    template = PROMPTS[name]
    return template.format(**kwargs)


# ============================================================================
# КОНФИГУРАЦИЯ ПРОМПТОВ
# ============================================================================

class PromptsConfig:
    """Конфигурация для выбора версий промптов"""
    
    # Какую версию промптов использовать
    STRUCTURE_ANALYSIS_VERSION = "v1"  # "v1" или "v2_simple"
    EXTRACTION_VERSION = "v1"  # "v1" или "v2_fewshot"
    
    # Параметры
    MAX_SAMPLE_ROWS = 20  # Сколько строк отправлять для анализа
    MAX_RETRY_REPROMPTS = 2  # Сколько раз повторять при ошибках
    
    # Специализация по типам файлов
    USE_SPECIALIZED_PROMPTS = True  # Использовать специализированные промпты
    
    @classmethod
    def get_structure_prompt(cls):
        """Получить текущий промпт для анализа структуры"""
        if cls.STRUCTURE_ANALYSIS_VERSION == "v1":
            return STRUCTURE_ANALYSIS_PROMPT_V1
        elif cls.STRUCTURE_ANALYSIS_VERSION == "v2_simple":
            return STRUCTURE_ANALYSIS_PROMPT_V2_SIMPLE
        else:
            raise ValueError(f"Неизвестная версия: {cls.STRUCTURE_ANALYSIS_VERSION}")
    
    @classmethod
    def get_extraction_prompt(cls, file_type: str = None):
        """
        Получить промпт для извлечения данных.
        
        Args:
            file_type: тип файла ("daily_report", "operational_report", или None)
        """
        # Если есть специализированный промпт - используем его
        if cls.USE_SPECIALIZED_PROMPTS and file_type:
            if file_type == "daily_report":
                return DAILY_REPORT_EXTRACTION
            elif file_type == "operational_report":
                return OPERATIONAL_REPORT_EXTRACTION
        
        # Иначе общий промпт
        if cls.EXTRACTION_VERSION == "v1":
            return EXTRACTION_PROMPT_V1
        elif cls.EXTRACTION_VERSION == "v2_fewshot":
            return EXTRACTION_PROMPT_V2_FEWSHOT
        else:
            raise ValueError(f"Неизвестная версия: {cls.EXTRACTION_VERSION}")

