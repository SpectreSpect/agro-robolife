"""
LLM Client для работы с gptunnel API.

Предоставляет обертку над OpenAI SDK для работы с gptunnel.ru API.
Включает retry логику, логирование, подсчет токенов и стоимости.
"""

import os
import json
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

try:
    from openai import OpenAI
    from openai import OpenAIError, APIError, RateLimitError, APITimeoutError
except ImportError:
    raise ImportError(
        "Требуется установить openai: pip install openai"
    )

try:
    import tiktoken
except ImportError:
    tiktoken = None

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Клиент для работы с LLM через gptunnel API.
    
    Функции:
    - Отправка запросов к LLM
    - Retry логика с exponential backoff
    - Логирование всех запросов/ответов
    - Подсчет токенов и стоимости
    - Кэширование ответов
    """
    
    # Ценообразование (за 1M токенов)
    PRICING = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "gpt-4o": {"input": 5.00, "output": 15.00},
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 16000,
        timeout: int = 60,
        max_retries: int = 3,
        log_requests: bool = True,
    ):
        """
        Инициализация LLM клиента.
        
        Args:
            api_key: API ключ (если None - берется из env)
            base_url: Base URL для API (если None - берется из env)
            model: Модель для использования
            temperature: Temperature для генерации (0.0-2.0)
            max_tokens: Максимальное количество токенов в ответе
            timeout: Timeout для запросов (секунды)
            max_retries: Максимальное количество повторов при ошибке
            log_requests: Логировать ли запросы/ответы
        """
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://gptunnel.ru/v1")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.log_requests = log_requests
        
        if not self.api_key:
            raise ValueError(
                "API ключ не найден. Установите LLM_API_KEY в .env или передайте в конструктор."
            )
        
        # Инициализация OpenAI клиента
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )
        
        # Статистика
        self.total_requests = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.failed_requests = 0
        
        # Кэш для ответов (простой in-memory кэш)
        self.cache: Dict[str, Any] = {}
        self.cache_enabled = os.getenv("LLM_ENABLE_CACHE", "true").lower() == "true"
        
        # Настройка логирования запросов
        if self.log_requests:
            self._setup_request_logger()
        
        logger.info(
            f"LLM Client инициализирован: model={self.model}, "
            f"base_url={self.base_url}, cache={self.cache_enabled}"
        )
    
    def _setup_request_logger(self):
        """Настраивает отдельный логгер для запросов к LLM"""
        self.request_logger = logging.getLogger("llm_requests")
        
        # Если еще не настроен
        if not self.request_logger.handlers:
            log_file = os.getenv("LLM_LOG_FILE", "llm_requests.log")
            handler = logging.FileHandler(log_file, encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.request_logger.addHandler(handler)
            self.request_logger.setLevel(logging.INFO)
    
    def _get_cache_key(self, prompt: str, system_prompt: Optional[str]) -> str:
        """Создает ключ кэша на основе промпта"""
        import hashlib
        content = f"{system_prompt or ''}|{prompt}|{self.model}|{self.temperature}"
        return hashlib.md5(content.encode()).hexdigest()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        reraise=True,
    )
    def send_request(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_cache: bool = True,
    ) -> str:
        """
        Отправляет запрос к LLM.
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (опционально)
            use_cache: Использовать ли кэш
        
        Returns:
            Ответ от LLM
        
        Raises:
            OpenAIError: При ошибке API
            ValueError: При невалидных параметрах
        """
        start_time = time.time()
        
        # Проверяем кэш
        if use_cache and self.cache_enabled:
            cache_key = self._get_cache_key(prompt, system_prompt)
            if cache_key in self.cache:
                logger.debug("Ответ взят из кэша")
                if self.log_requests:
                    self.request_logger.info(
                        f"CACHE HIT: {cache_key[:16]}... "
                        f"(prompt_len={len(prompt)})"
                    )
                return self.cache[cache_key]
        
        # Формируем сообщения
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Логируем запрос
        if self.log_requests:
            self.request_logger.info("=" * 80)
            self.request_logger.info(f"NEW REQUEST to {self.model}")
            self.request_logger.info(f"System: {system_prompt[:100] if system_prompt else 'None'}...")
            self.request_logger.info(f"Prompt (len={len(prompt)}): {prompt[:200]}...")
        
        try:
            # Отправляем запрос
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            # Извлекаем ответ
            content = response.choices[0].message.content
            
            # Обновляем статистику
            self.total_requests += 1
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            
            # Рассчитываем стоимость
            cost = self._calculate_cost(input_tokens, output_tokens)
            self.total_cost += cost
            
            elapsed_time = time.time() - start_time
            
            # Логируем ответ
            if self.log_requests:
                self.request_logger.info(
                    f"RESPONSE (time={elapsed_time:.2f}s, "
                    f"tokens={input_tokens}+{output_tokens}={input_tokens+output_tokens}, "
                    f"cost=${cost:.4f}): {content[:200]}..."
                )
            
            logger.debug(
                f"LLM запрос выполнен за {elapsed_time:.2f}s, "
                f"токены: {input_tokens}→{output_tokens}, стоимость: ${cost:.4f}"
            )
            
            # Сохраняем в кэш
            if use_cache and self.cache_enabled:
                cache_key = self._get_cache_key(prompt, system_prompt)
                self.cache[cache_key] = content
            
            return content
            
        except RateLimitError as e:
            self.failed_requests += 1
            logger.warning(f"Rate limit достигнут, повтор через несколько секунд: {e}")
            if self.log_requests:
                self.request_logger.warning(f"RATE LIMIT: {e}")
            raise
            
        except APITimeoutError as e:
            self.failed_requests += 1
            logger.warning(f"Timeout при запросе к API: {e}")
            if self.log_requests:
                self.request_logger.warning(f"TIMEOUT: {e}")
            raise
            
        except APIError as e:
            self.failed_requests += 1
            logger.error(f"Ошибка API: {e}")
            if self.log_requests:
                self.request_logger.error(f"API ERROR: {e}")
            raise
            
        except Exception as e:
            self.failed_requests += 1
            logger.error(f"Неожиданная ошибка при запросе к LLM: {e}")
            if self.log_requests:
                self.request_logger.error(f"UNEXPECTED ERROR: {e}")
            raise
    
    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит JSON из ответа LLM.
        
        LLM часто оборачивает JSON в markdown блоки или добавляет текст.
        Эта функция пытается извлечь JSON из различных форматов.
        
        Args:
            response: Ответ от LLM
        
        Returns:
            Распарсенный JSON объект
        
        Raises:
            ValueError: Если не удалось распарсить JSON
        """
        import re
        
        response = response.strip()
        
        # Попытка 1: Прямой парсинг
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Попытка 2: Извлечение из markdown блока ```json ... ```
        match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Попытка 3: Извлечение из любого блока ``` ... ```
        match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Попытка 4: Поиск JSON объекта или массива
        match = re.search(r'(\{.*\}|\[.*\])', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Не удалось распарсить
        raise ValueError(
            f"Не удалось извлечь JSON из ответа LLM. "
            f"Ответ: {response[:200]}..."
        )
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Рассчитывает стоимость запроса"""
        if self.model not in self.PRICING:
            logger.warning(f"Неизвестная модель для расчета стоимости: {self.model}")
            return 0.0
        
        pricing = self.PRICING[self.model]
        cost = (
            input_tokens * pricing["input"] / 1_000_000 +
            output_tokens * pricing["output"] / 1_000_000
        )
        return cost
    
    def estimate_tokens(self, text: str) -> int:
        """
        Оценивает количество токенов в тексте.
        
        Использует tiktoken если доступен, иначе грубую эвристику.
        
        Args:
            text: Текст для оценки
        
        Returns:
            Примерное количество токенов
        """
        if tiktoken is not None:
            try:
                encoding = tiktoken.encoding_for_model(self.model)
                return len(encoding.encode(text))
            except Exception:
                pass
        
        # Грубая эвристика для русского текста: ~2-3 символа на токен
        return len(text) // 2
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику использования API"""
        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                (self.total_requests - self.failed_requests) / self.total_requests * 100
                if self.total_requests > 0 else 0
            ),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": self.total_cost,
            "avg_cost_per_request": (
                self.total_cost / self.total_requests
                if self.total_requests > 0 else 0
            ),
            "cache_size": len(self.cache),
            "cache_enabled": self.cache_enabled,
        }
    
    def clear_cache(self):
        """Очищает кэш"""
        self.cache.clear()
        logger.info("Кэш LLM очищен")
    
    def __repr__(self) -> str:
        return (
            f"LLMClient(model={self.model}, "
            f"requests={self.total_requests}, "
            f"cost=${self.total_cost:.4f})"
        )

