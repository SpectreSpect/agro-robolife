"""
Конфигурация для LLM клиента.

Использует Pydantic для валидации настроек из .env файла.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    """
    Конфигурация LLM клиента.
    
    Параметры загружаются из переменных окружения с префиксом LLM_.
    Например: LLM_API_KEY, LLM_MODEL, и т.д.
    """
    
    # API настройки
    api_key: str = Field(
        ...,
        description="API ключ для gptunnel.ru"
    )
    
    base_url: str = Field(
        default="https://gptunnel.ru/v1",
        description="Base URL для API"
    )
    
    model: str = Field(
        default="gpt-4o-mini",
        description="Модель для использования (gpt-4o-mini, gpt-3.5-turbo, gpt-4o)"
    )
    
    # Параметры генерации
    max_tokens: int = Field(
        default=16000,
        ge=1,
        le=128000,
        description="Максимальное количество токенов в ответе"
    )
    
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature для генерации (0.0-2.0, чем ниже - тем точнее)"
    )
    
    # Сетевые настройки
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Максимальное количество попыток при ошибке"
    )
    
    timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Timeout для запросов в секундах"
    )
    
    # Кэширование и логирование
    enable_cache: bool = Field(
        default=True,
        description="Включить кэширование ответов LLM"
    )
    
    log_requests: bool = Field(
        default=True,
        description="Логировать все запросы и ответы"
    )
    
    # Fallback
    fallback_to_legacy: bool = Field(
        default=True,
        description="Использовать legacy парсеры при ошибках LLM"
    )
    
    # Дополнительные настройки
    log_file: str = Field(
        default="llm_requests.log",
        description="Файл для логов LLM запросов"
    )
    
    class Config:
        env_file = ".env"
        env_prefix = "LLM_"
        case_sensitive = False
        extra = "ignore"
    
    def __repr__(self) -> str:
        # Не показываем API ключ в repr
        return (
            f"LLMConfig("
            f"model={self.model}, "
            f"base_url={self.base_url}, "
            f"cache={self.enable_cache}, "
            f"fallback={self.fallback_to_legacy}"
            f")"
        )


def get_llm_config() -> LLMConfig:
    """
    Создает и возвращает конфигурацию LLM.
    
    Returns:
        LLMConfig: Объект конфигурации
    
    Raises:
        ValueError: Если не удалось загрузить конфигурацию
    
    Example:
        >>> config = get_llm_config()
        >>> print(config.model)
        'gpt-4o-mini'
    """
    try:
        return LLMConfig()
    except Exception as e:
        raise ValueError(
            f"Не удалось загрузить конфигурацию LLM: {e}\n"
            f"Убедитесь, что файл .env существует и содержит LLM_API_KEY"
        )


# Для удобства импорта
__all__ = ["LLMConfig", "get_llm_config"]

