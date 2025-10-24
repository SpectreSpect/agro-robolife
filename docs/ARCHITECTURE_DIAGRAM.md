# Архитектура LLM-based парсинга

## Текущая архитектура (до изменений)

```
┌─────────────────────────────────────────────────────────────────┐
│                         ТЕКУЩАЯ СИСТЕМА                          │
└─────────────────────────────────────────────────────────────────┘

   Excel файлы (data/)
        │
        ├─ Таблица_для_дневного_отчета_*.xlsx
        ├─ Оперативная_отчетность_*.xlsx
        └─ ...
        │
        ▼
   ┌──────────────┐
   │ DataReader   │ ← читает файлы, создает метаданные
   └──────┬───────┘
          │
          ▼
   ┌──────────────────────┐
   │    DataParser        │
   │                      │
   │  ┌────────────────┐  │
   │  │ DailyReport    │  │ ← жесткий парсинг по позициям
   │  │ Parser         │  │
   │  └────────────────┘  │
   │                      │
   │  ┌────────────────┐  │
   │  │ Operational    │  │ ← жесткий парсинг по позициям
   │  │ ReportParser   │  │
   │  └────────────────┘  │
   └──────────┬───────────┘
              │
              ▼
        Структурированные данные
        [{operation_date, department_name, ...}, ...]
              │
              ▼
   ┌──────────────┐
   │ TableBuilder │ ← создает Excel с pivot tables
   └──────┬───────┘
          │
          ▼
   output_processed_*.xlsx
```

**Проблемы текущей архитектуры:**
- ❌ Жесткая привязка к структуре файлов
- ❌ Нужно писать новый парсер для каждого формата
- ❌ Хрупкий код (сдвиг колонок = поломка)
- ❌ Невозможно обработать нестандартные файлы

---

## Целевая архитектура (после изменений)

```
┌─────────────────────────────────────────────────────────────────┐
│                      НОВАЯ СИСТЕМА (LLM)                         │
└─────────────────────────────────────────────────────────────────┘

   Excel файлы (любой структуры)
        │
        ▼
   ┌────────────────────┐
   │   DataReader       │ ← расширенная версия
   │                    │
   │  • извлекает       │
   │    метаданные      │
   │  • первые N строк  │
   │  • типы колонок    │
   │  • merged cells    │
   │  • структура       │
   └────────┬───────────┘
            │
            ▼
   ┌────────────────────────────────────┐
   │         LLMParser                  │
   │                                    │
   │  Шаг 1: Анализ структуры          │
   │  ┌──────────────────────────────┐ │
   │  │  LLM: "Где данные?"          │ │
   │  │  Input: метаданные + sample  │ │
   │  │  Output: структура JSON      │ │
   │  └────────────┬─────────────────┘ │
   │               │                   │
   │  Шаг 2: Извлечение данных        │
   │  ┌────────────▼─────────────────┐ │
   │  │  LLM: "Извлеки данные"       │ │
   │  │  Input: структура + все      │ │
   │  │         данные               │ │
   │  │  Output: записи JSON         │ │
   │  └────────────┬─────────────────┘ │
   │               │                   │
   │  Шаг 3: Валидация                │
   │  ┌────────────▼─────────────────┐ │
   │  │  Pydantic models             │ │
   │  │  + бизнес-правила            │ │
   │  └────────────┬─────────────────┘ │
   └───────────────┼───────────────────┘
                   │
                   ▼
            ┌──────────────┐
            │  LLMClient   │ ← обертка над API
            │              │
            │  • OpenAI    │
            │    SDK       │
            │  • Retry     │
            │  • Cache     │
            │  • Logging   │
            └──────┬───────┘
                   │
                   ▼
         gptunnel API (gpt-4o-mini)
                   │
                   ▼
        Структурированные данные
        [{operation_date, department_name, ...}, ...]
                   │
                   ▼
            ┌──────────────┐
            │ TableBuilder │ ← БЕЗ ИЗМЕНЕНИЙ
            └──────┬───────┘
                   │
                   ▼
          output_processed_*.xlsx
```

**Преимущества новой архитектуры:**
- ✅ Обработка файлов любой структуры
- ✅ Не нужно писать парсеры для новых форматов
- ✅ Устойчивость к изменениям структуры
- ✅ Самообучение через промпт-инженеринг
- ✅ Легко расширяется новыми полями

---

## Детальная архитектура компонентов

### 1. LLMClient

```
┌─────────────────────────────────────────┐
│           LLMClient                     │
├─────────────────────────────────────────┤
│                                         │
│  Config                                 │
│  ├─ API key                             │
│  ├─ Base URL (gptunnel)                 │
│  ├─ Model (gpt-4o-mini)                 │
│  └─ Parameters (temp, max_tokens)       │
│                                         │
│  Methods                                │
│  ├─ send_request(prompt)                │
│  │   ├─ validate input                  │
│  │   ├─ estimate tokens                 │
│  │   ├─ call API (with retry)           │
│  │   ├─ parse response                  │
│  │   └─ log & cache                     │
│  │                                      │
│  ├─ parse_json_response(text)           │
│  │   ├─ extract JSON from markdown      │
│  │   ├─ validate JSON schema            │
│  │   └─ handle parsing errors           │
│  │                                      │
│  └─ calculate_cost(tokens)              │
│      └─ track spending                  │
│                                         │
│  Error Handling                         │
│  ├─ Rate limit → exponential backoff    │
│  ├─ Timeout → retry with longer timeout │
│  ├─ Invalid JSON → re-prompt            │
│  └─ API error → fallback to legacy      │
└─────────────────────────────────────────┘
```

### 2. LLMParser

```
┌─────────────────────────────────────────────┐
│             LLMParser                       │
├─────────────────────────────────────────────┤
│                                             │
│  parse_file(file_path, metadata)            │
│      │                                      │
│      ├─> 1. _analyze_structure()            │
│      │      │                               │
│      │      ├─ формирует промпт             │
│      │      ├─ отправляет LLM               │
│      │      ├─ парсит JSON ответ            │
│      │      └─ кэширует структуру           │
│      │                                      │
│      ├─> 2. _extract_raw_data()             │
│      │      │                               │
│      │      ├─ читает все данные из Excel   │
│      │      ├─ применяет структуру          │
│      │      └─ форматирует для LLM          │
│      │                                      │
│      ├─> 3. _llm_extract()                  │
│      │      │                               │
│      │      ├─ формирует промпт с данными   │
│      │      ├─ отправляет LLM               │
│      │      └─ получает массив записей      │
│      │                                      │
│      ├─> 4. _validate_records()             │
│      │      │                               │
│      │      ├─ проверка типов (Pydantic)    │
│      │      ├─ бизнес-правила               │
│      │      ├─ удаление дубликатов          │
│      │      └─ фильтрация пустых            │
│      │                                      │
│      └─> 5. _post_process()                 │
│             │                               │
│             ├─ нормализация дат             │
│             ├─ округление чисел             │
│             ├─ стандартизация названий      │
│             └─ расчет completion_percent    │
│                                             │
└─────────────────────────────────────────────┘
```

### 3. DataReader (расширенный)

```
┌─────────────────────────────────────────┐
│        DataReader (enhanced)            │
├─────────────────────────────────────────┤
│                                         │
│  Существующие методы:                   │
│  ├─ get_excel_files()                   │
│  ├─ read_excel_file()                   │
│  └─ _determine_file_type()              │
│                                         │
│  НОВЫЕ методы:                          │
│  │                                      │
│  ├─ extract_cell_values(ws, N)          │
│  │   └─ первые N строк/колонок          │
│  │                                      │
│  ├─ detect_header_rows(ws)              │
│  │   ├─ ищет строку с заголовками       │
│  │   └─ эвристики (жирный, большой)     │
│  │                                      │
│  ├─ extract_sheet_structure(ws)         │
│  │   ├─ определяет типы колонок         │
│  │   ├─ находит числовые области        │
│  │   └─ определяет группировку          │
│  │                                      │
│  ├─ get_merged_cells_info(ws)           │
│  │   └─ список объединенных ячеек       │
│  │                                      │
│  └─ extract_formulas(ws)                │
│      └─ извлекает формулы               │
│                                         │
│  Output format (extended):               │
│  {                                      │
│    file_name, file_path, file_type,     │
│    sheets: {                            │
│      sheet_name: {                      │
│        shape, columns,                  │
│        sample_data,      ← первые N     │
│        header_row,       ← NEW          │
│        data_start_row,   ← NEW          │
│        merged_cells,     ← NEW          │
│        column_types,     ← NEW          │
│        structure_hints   ← NEW          │
│      }                                  │
│    }                                    │
│  }                                      │
└─────────────────────────────────────────┘
```

---

## Поток данных (Data Flow)

```
┌──────────────────────────────────────────────────────────────┐
│                     DATA FLOW DIAGRAM                         │
└──────────────────────────────────────────────────────────────┘

1. ЧТЕНИЕ ФАЙЛА
   ┌─────────────┐
   │ Excel File  │
   └──────┬──────┘
          │
          ▼
   [DataReader.read_excel_file()]
          │
          ├─ openpyxl.load_workbook()
          ├─ extract_cell_values() → первые 20 строк
          ├─ detect_header_rows() → row: 3
          ├─ extract_sheet_structure() → column types
          └─ get_merged_cells_info() → merged ranges
          │
          ▼
   {file_metadata}  ← расширенная структура

2. АНАЛИЗ СТРУКТУРЫ (LLM CALL #1)
   ┌──────────────────────┐
   │  file_metadata       │
   │  + sample_data       │
   └──────┬───────────────┘
          │
          ▼
   [LLMParser._analyze_structure()]
          │
          ├─ создает промпт: STRUCTURE_ANALYSIS_PROMPT
          ├─ добавляет sample_data (первые 20 строк)
          ├─ вызывает LLMClient.send_request()
          │
          ▼
   ┌──────────────────────┐
   │  gptunnel API        │
   │  gpt-4o-mini         │
   └──────┬───────────────┘
          │
          ▼
   {structure}  ← JSON с описанием структуры:
   {
     "file_type": "daily_report",
     "date_location": {"row": 2, "col": 1},
     "department_location": {"row": 3, "col": 1},
     "header_row": 4,
     "data_start_row": 6,
     "columns": {
       "operation": 1,
       "crop": 2,
       "work_per_day": 7,
       "work_from_start": 8,
       "remaining": 9
     }
   }

3. ИЗВЛЕЧЕНИЕ ДАННЫХ
   ┌──────────────────────┐
   │  structure           │
   │  + raw Excel data    │
   └──────┬───────────────┘
          │
          ▼
   [LLMParser._extract_raw_data()]
          │
          ├─ читает данные по структуре
          ├─ форматирует в текст для LLM
          │
          ▼
   ┌──────────────────────────┐
   │ "Row 6: Посев, Пшеница,  │
   │  plan=100, fact=80       │
   │ Row 7: Уборка, Ячмень,   │
   │  plan=50, fact=30        │
   │ ..."                     │
   └──────┬───────────────────┘
          │
          ▼
   [LLMParser._llm_extract()] (LLM CALL #2)
          │
          ├─ создает промпт: EXTRACTION_PROMPT
          ├─ добавляет структуру + данные
          ├─ вызывает LLMClient.send_request()
          │
          ▼
   ┌──────────────────────┐
   │  gptunnel API        │
   │  gpt-4o-mini         │
   └──────┬───────────────┘
          │
          ▼
   [
     {
       "operation_date": "2025-07-16",
       "department_name": "ПУ Север",
       "operation_name": "Посев",
       "crop_name": "Пшеница",
       "work_per_day": 20.0,
       "work_from_start": 80.0,
       "remaining_work": 20.0
     },
     {...}
   ]

4. ВАЛИДАЦИЯ
   ┌──────────────────────┐
   │  raw records         │
   └──────┬───────────────┘
          │
          ▼
   [LLMParser._validate_records()]
          │
          ├─ Pydantic validation
          ├─ check required fields
          ├─ validate types
          ├─ business rules
          └─ remove duplicates
          │
          ▼
   [valid_records]  ← только валидные

5. ПОСТОБРАБОТКА
   ┌──────────────────────┐
   │  valid_records       │
   └──────┬───────────────┘
          │
          ▼
   [LLMParser._post_process()]
          │
          ├─ normalize dates
          ├─ calculate completion_percent
          ├─ round numbers
          └─ standardize names
          │
          ▼
   [final_records]  ← готовые данные

6. АГРЕГАЦИЯ
   ┌──────────────────────┐
   │  records from        │
   │  multiple files      │
   └──────┬───────────────┘
          │
          ▼
   [DataParser.parse_all_files()]
          │
          └─ объединяет все записи
          │
          ▼
   [all_data]  ← массив всех записей

7. ПОСТРОЕНИЕ ТАБЛИЦЫ
   ┌──────────────────────┐
   │  all_data            │
   └──────┬───────────────┘
          │
          ▼
   [TableBuilder.build_table()]
          │
          ├─ создает DataFrame
          ├─ копирует шаблон
          ├─ заполняет данными
          ├─ обновляет pivot tables
          └─ сохраняет Excel
          │
          ▼
   output_processed_*.xlsx  ← финальный файл
```

---

## Обработка ошибок (Error Flow)

```
┌─────────────────────────────────────────────────┐
│            ERROR HANDLING FLOW                   │
└─────────────────────────────────────────────────┘

         LLM Call
            │
            ▼
      ┌──────────┐
      │ API Call │
      └────┬─────┘
           │
           ├─> SUCCESS ─────────────────────────> continue
           │
           ├─> TIMEOUT
           │   │
           │   └─> retry with longer timeout (3x)
           │       │
           │       ├─> success ──────────────────> continue
           │       └─> fail ───> log + fallback
           │
           ├─> RATE_LIMIT
           │   │
           │   └─> exponential backoff + retry (5x)
           │       │
           │       ├─> success ──────────────────> continue
           │       └─> fail ───> log + fallback
           │
           ├─> INVALID_JSON
           │   │
           │   └─> re-prompt with error message (2x)
           │       │
           │       ├─> success ──────────────────> continue
           │       └─> fail ───> log + fallback
           │
           └─> OTHER_ERROR
               │
               └─> log + immediate fallback

Fallback Strategy:
    │
    ├─> Try legacy parser (if available)
    │   ├─> DailyReportParser
    │   └─> OperationalReportParser
    │
    └─> Skip file + log error
```

---

## Кэширование (Caching Strategy)

```
┌─────────────────────────────────────────┐
│          CACHE ARCHITECTURE             │
└─────────────────────────────────────────┘

1. Structure Cache (долгоживущий)
   ┌──────────────────────────┐
   │  Key: file_hash          │
   │  Value: structure_json   │
   │  TTL: 30 days            │
   └──────────────────────────┘
   
   • Кэш инвалидируется при изменении файла
   • Хранится в SQLite или Redis
   • Ускоряет повторную обработку файлов

2. LLM Response Cache (среднесрочный)
   ┌──────────────────────────┐
   │  Key: prompt_hash        │
   │  Value: llm_response     │
   │  TTL: 7 days             │
   └──────────────────────────┘
   
   • Кэш для идентичных промптов
   • Экономит деньги на API
   • Хранится в памяти + диск

3. File Metadata Cache (краткосрочный)
   ┌──────────────────────────┐
   │  Key: file_path          │
   │  Value: metadata         │
   │  TTL: 1 hour             │
   └──────────────────────────┘
   
   • Для быстрого доступа
   • Только в памяти
```

---

## Мониторинг и метрики

```
┌─────────────────────────────────────────┐
│         MONITORING DASHBOARD            │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  API Usage Statistics                   │
├─────────────────────────────────────────┤
│  • Total requests: 1,234                │
│  • Success rate: 98.5%                  │
│  • Avg response time: 2.3s              │
│  • Total tokens used: 1.2M              │
│  • Total cost: $3.45                    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Parsing Quality                        │
├─────────────────────────────────────────┤
│  • Files processed: 456                 │
│  • Records extracted: 12,345            │
│  • Validation errors: 23 (0.2%)         │
│  • Fallback to legacy: 5 (1.1%)         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Performance                            │
├─────────────────────────────────────────┤
│  • Avg time per file: 4.5s              │
│  • Cache hit rate: 45%                  │
│  • LLM calls saved by cache: 234        │
│  • Cost saved by cache: $0.67           │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Recent Errors                          │
├─────────────────────────────────────────┤
│  • 2025-10-24 10:23 - Rate limit        │
│  • 2025-10-24 09:15 - Invalid JSON      │
│  • 2025-10-23 15:42 - Timeout           │
└─────────────────────────────────────────┘
```

---

## Сравнение: До vs После

| Аспект | До (жесткие парсеры) | После (LLM) |
|--------|----------------------|-------------|
| **Гибкость** | ❌ Только известные форматы | ✅ Любые форматы |
| **Поддержка** | ❌ Код для каждого формата | ✅ Промпт-инженеринг |
| **Хрупкость** | ❌ Ломается при изменениях | ✅ Адаптируется |
| **Скорость** | ✅ Мгновенно | ⚠️ 2-5 секунд на файл |
| **Стоимость** | ✅ Бесплатно | ⚠️ ~$0.003 на файл |
| **Точность** | ✅ 100% для известных | ✅ 95-98% для любых |
| **Масштаб** | ❌ Сложно расширять | ✅ Легко добавлять поля |
| **Логи** | ⚠️ Базовые | ✅ Детальные + мониторинг |

---

**Вывод:** LLM-based парсинг даёт радикальное улучшение гибкости при минимальных затратах (~$3/месяц) и приемлемой скорости.

