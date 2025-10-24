"""
Простой тест подключения к gptunnel API (без emoji для Windows).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import logging
from data_processing.llm_client import LLMClient
from data_processing.llm_config import get_llm_config

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    print("\n" + "=" * 80)
    print("TEST: LLM Connection")
    print("=" * 80)
    
    try:
        # Загружаем конфигурацию
        print("\n1. Loading config...")
        config = get_llm_config()
        print(f"   OK: {config.model} @ {config.base_url}")
        
        # Создаем клиент
        print("\n2. Creating LLM client...")
        client = LLMClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
        )
        print(f"   OK: {client}")
        
        # Тестовый запрос
        print("\n3. Sending test request...")
        response = client.send_request(
            prompt="Say 'OK' if connection works.",
            system_prompt="You are a helpful assistant."
        )
        print(f"   Response: {response}")
        
        # Статистика
        stats = client.get_statistics()
        print(f"\n4. Statistics:")
        print(f"   Requests: {stats['total_requests']}")
        print(f"   Tokens: {stats['total_input_tokens']} + {stats['total_output_tokens']}")
        print(f"   Cost: ${stats['total_cost']:.4f}")
        
        print("\n" + "=" * 80)
        print("SUCCESS! LLM integration is working!")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nPossible issues:")
        print("  1. LLM_API_KEY not set in .env")
        print("  2. API key is invalid")
        print("  3. Network issues")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

