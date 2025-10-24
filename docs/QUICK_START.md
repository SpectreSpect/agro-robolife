# Quick Start Guide - LLM Integration

Краткое руководство для быстрого старта интеграции LLM-based парсинга.

---

## 🚀 Быстрый старт (30 минут)

### Шаг 1: Установка зависимостей

```bash
# Активировать виртуальное окружение (если есть)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить новые зависимости
pip install openai tiktoken pydantic tenacity python-dotenv
```

---

### Шаг 2: Создать `.env` файл

```bash
# В корне проекта создать .env
touch .env
```

Содержимое `.env`:
```env
LLM_API_KEY=shds-394Eyp7326LMrK0NuM4AR8ywac6
LLM_BASE_URL=https://gptunnel.ru/v1
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=16000
LLM_TEMPERATURE=0.1
LLM_MAX_RETRIES=3
LLM_TIMEOUT=60
LLM_ENABLE_CACHE=true
LLM_LOG_REQUESTS=true
```

---

### Шаг 3: Создать базовый LLMClient

```bash
# Создать файл
touch src/data_processing/llm_client.py
```

Минимальная реализация:

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL")
        )
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    def send_request(self, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=float(os.getenv("LLM_TEMPERATURE", 0.1))
        )
        
        return response.choices[0].message.content
```

---

### Шаг 4: Тест подключения

```bash
# Создать тестовый скрипт
touch test_llm_connection.py
```

Содержимое:

```python
from src.data_processing.llm_client import LLMClient

def test_connection():
    client = LLMClient()
    
    response = client.send_request(
        prompt="Привет! Ответь одним словом: работает ли подключение?",
        system_prompt="Ты - помощник для тестирования API."
    )
    
    print("✅ Подключение работает!")
    print(f"Ответ: {response}")

if __name__ == "__main__":
    test_connection()
```

Запуск:
```bash
python test_llm_connection.py
```

---

### Шаг 5: Создать простой парсер (MVP)

```bash
touch src/data_processing/llm_parser.py
```

Минимальная версия:

```python
import json
import openpyxl
from pathlib import Path
from typing import List, Dict, Any
from .llm_client import LLMClient

class LLMParser:
    def __init__(self):
        self.client = LLMClient()
    
    def parse_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Парсит Excel файл с помощью LLM"""
        
        # 1. Читаем первые 20 строк
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb[wb.sheetnames[0]]
        
        sample_data = []
        for row in ws.iter_rows(max_row=20, values_only=True):
            sample_data.append(row)
        
        # 2. Формируем промпт
        prompt = self._create_extraction_prompt(sample_data)
        
        # 3. Отправляем LLM
        response = self.client.send_request(prompt)
        
        # 4. Парсим JSON
        records = self._parse_json_response(response)
        
        wb.close()
        return records
    
    def _create_extraction_prompt(self, sample_data) -> str:
        # Конвертируем данные в текст
        data_text = "\n".join([str(row) for row in sample_data])
        
        return f"""
Извлеки сельскохозяйственные данные из таблицы в JSON формат.

Таблица:
{data_text}

Верни массив JSON объектов в формате:
[
  {{
    "operation_date": "YYYY-MM-DD",
    "department_name": "название подразделения",
    "operation_name": "название операции",
    "crop_name": "название культуры",
    "work_per_day": число,
    "work_from_start": число,
    "remaining_work": число
  }}
]

ВАЖНО: Верни только валидный JSON, без дополнительного текста.
"""
    
    def _parse_json_response(self, response: str) -> List[Dict]:
        # Убираем markdown если есть
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        
        return json.loads(response)
```

---

### Шаг 6: Интеграция с DataParser

Обновить `src/data_processing/data_parser.py`:

```python
# Добавить в начало файла
try:
    from .llm_parser import LLMParser
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

class DataParser:
    def __init__(self, data_dir: Path, use_llm: bool = False):
        self.data_dir = data_dir
        self.use_llm = use_llm and LLM_AVAILABLE
        
        if self.use_llm:
            logger.info("🤖 Используем LLM-based парсинг")
            self.llm_parser = LLMParser()
        else:
            logger.info("📋 Используем legacy парсеры")
            self.llm_parser = None
    
    def parse_all_files(self) -> List[Dict[str, Any]]:
        all_data = []
        
        if self.use_llm:
            # LLM парсинг
            excel_files = list(self.data_dir.glob("*.xlsx"))
            for file_path in excel_files:
                try:
                    records = self.llm_parser.parse_file(file_path)
                    all_data.extend(records)
                    logger.info(f"✅ LLM parsed {file_path.name}: {len(records)} records")
                except Exception as e:
                    logger.error(f"❌ LLM parsing failed for {file_path.name}: {e}")
                    # Fallback to legacy
                    logger.info("⚠️ Falling back to legacy parser")
                    all_data.extend(self._legacy_parse(file_path))
        else:
            # Существующая логика
            all_data = self._legacy_parse_all()
        
        return all_data
    
    def _legacy_parse_all(self):
        # Существующий код
        # ... (не трогаем)
        pass
```

---

### Шаг 7: Тестирование на реальном файле

```bash
# Создать тестовый скрипт
touch test_llm_parser.py
```

```python
from pathlib import Path
from src.data_processing import DataParser
import logging

logging.basicConfig(level=logging.INFO)

def test_llm_parser():
    # Тест на одном файле
    parser = DataParser(Path("data"), use_llm=True)
    
    result = parser.parse_all_files()
    
    print(f"\n✅ Извлечено {len(result)} записей")
    
    if result:
        print("\nПример первой записи:")
        print(result[0])

if __name__ == "__main__":
    test_llm_parser()
```

Запуск:
```bash
python test_llm_parser.py
```

---

### Шаг 8: Интеграция в main.py

Обновить `src/main.py`:

```python
# Добавить флаг для LLM
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="Use LLM-based parsing")
    args = parser.parse_args()
    
    # ...
    
    # Изменить создание парсера
    data_parser = DataParser(Path("data"), use_llm=args.llm)
    
    # Остальной код без изменений
    # ...
```

Запуск с LLM:
```bash
python src/main.py --llm
```

Запуск без LLM (legacy):
```bash
python src/main.py
```

---

## 📊 Проверка результатов

### Сравнение legacy vs LLM

```bash
# 1. Запуск legacy
python src/main.py > legacy_output.txt

# 2. Запуск LLM
python src/main.py --llm > llm_output.txt

# 3. Сравнение
diff legacy_output.txt llm_output.txt
```

---

## 🔍 Отладка

### Логи

LLM запросы логируются в `agro_processing.log`:

```bash
tail -f agro_processing.log
```

### Просмотр токенов и стоимости

Добавить в `llm_client.py`:

```python
def send_request(self, prompt: str, system_prompt: str = None) -> str:
    # ... существующий код ...
    
    # Логируем использование
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    
    cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000
    
    print(f"💰 Tokens: {input_tokens} in + {output_tokens} out = ${cost:.4f}")
    
    return response.choices[0].message.content
```

---

## ⚠️ Известные проблемы

### 1. Rate Limit
**Проблема:** `429 Too Many Requests`

**Решение:**
```python
# Добавить в llm_client.py
import time
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def send_request(self, prompt: str, system_prompt: str = None) -> str:
    # ... код ...
```

### 2. Invalid JSON
**Проблема:** LLM возвращает невалидный JSON

**Решение:**
```python
def _parse_json_response(self, response: str) -> List[Dict]:
    try:
        # Попытка 1: обычный парсинг
        return json.loads(response)
    except json.JSONDecodeError:
        # Попытка 2: извлечь JSON из markdown
        match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # Попытка 3: извлечь массив
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        
        raise ValueError(f"Cannot parse JSON from response: {response[:100]}")
```

### 3. Timeout
**Проблема:** Долгий ответ от API

**Решение:**
```python
response = self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    temperature=float(os.getenv("LLM_TEMPERATURE", 0.1)),
    timeout=60  # секунд
)
```

---

## 📈 Следующие шаги

После успешного MVP:

1. ✅ **Улучшить промпты** - добавить примеры (few-shot)
2. ✅ **Добавить кэширование** - для экономии
3. ✅ **Расширить валидацию** - Pydantic models
4. ✅ **Мониторинг** - dashboard с метриками
5. ✅ **Тесты** - unit + integration

Переходите к полному плану: [LLM_INTEGRATION_PLAN.md](LLM_INTEGRATION_PLAN.md)

---

## 🆘 Помощь

**Проблемы с API:**
- Документация gptunnel: https://gptunnel.ru/docs
- Проверить баланс: https://gptunnel.ru/dashboard

**Проблемы с кодом:**
- Посмотреть логи: `agro_processing.log`
- Запустить с отладкой: `python -m pdb src/main.py --llm`

**Вопросы:**
- Открыть issue в проекте
- Проверить [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

**Время выполнения Quick Start:** 30-45 минут  
**Результат:** Работающий MVP LLM-based парсера

