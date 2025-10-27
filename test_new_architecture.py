"""
Скрипт для тестирования новой архитектуры v3.0
Проверяет основные функции системы
"""

import requests
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

def print_test(test_name):
    print(f"\n{'='*60}")
    print(f"ТЕСТ: {test_name}")
    print('='*60)

def test_api_health():
    """Проверка доступности API"""
    print_test("Проверка доступности API")
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            print("✅ API доступен")
            return True
        else:
            print(f"❌ Ошибка: статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")
        print("⚠️ Убедитесь, что сервер запущен (python app.py)")
        return False

def test_get_files():
    """Получение списка файлов"""
    print_test("Получение списка файлов")
    try:
        response = requests.get(f"{BASE_URL}/api/files")
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            print(f"✅ Получено файлов: {len(files)}")
            for file in files[:5]:  # Показываем первые 5
                print(f"  - {file['name']} ({file['size']} байт)")
            return True
        else:
            print(f"❌ Ошибка: статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_get_schedule():
    """Получение текущего расписания"""
    print_test("Получение текущего расписания")
    try:
        response = requests.get(f"{BASE_URL}/api/schedule")
        if response.status_code == 200:
            data = response.json()
            if data.get('is_enabled'):
                print("✅ Расписание активно")
                print(f"  Тип: {data.get('schedule_type')}")
                print(f"  Email: {data.get('recipient_email')}")
                if data.get('schedule_type') == 'one_time':
                    print(f"  Время: {data.get('scheduled_time')}")
                else:
                    print(f"  Время: {data.get('periodic_time')}")
            else:
                print("✅ Расписание не установлено")
            return True
        else:
            print(f"❌ Ошибка: статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_get_reports():
    """Получение истории отчетов"""
    print_test("Получение истории отчетов")
    try:
        response = requests.get(f"{BASE_URL}/api/reports")
        if response.status_code == 200:
            reports = response.json()
            print(f"✅ Получено отчетов: {len(reports)}")
            for report in reports[:3]:  # Показываем первые 3
                print(f"  - ID: {report['id']}, Статус: {report['status']}, Файл: {report.get('output_file', 'N/A')}")
            return True
        else:
            print(f"❌ Ошибка: статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_countdown():
    """Проверка таймера обратного отсчета"""
    print_test("Проверка таймера обратного отсчета")
    try:
        response = requests.get(f"{BASE_URL}/api/schedule/countdown")
        if response.status_code == 200:
            data = response.json()
            if data.get('active'):
                seconds = data.get('seconds_left', 0)
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                secs = seconds % 60
                print(f"✅ До генерации отчета: {hours}ч {minutes}м {secs}с")
            else:
                print("✅ Таймер неактивен (расписание не установлено)")
            return True
        else:
            print(f"❌ Ошибка: статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_folders():
    """Проверка наличия необходимых папок"""
    print_test("Проверка структуры папок")
    folders = ['shared_files', 'archived_files', 'outputs', 'templates']
    all_ok = True
    for folder in folders:
        path = Path(folder)
        if path.exists():
            print(f"✅ {folder}/ существует")
        else:
            print(f"❌ {folder}/ не найдена")
            all_ok = False
    return all_ok

def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ НОВОЙ АРХИТЕКТУРЫ v3.0")
    print("="*60)
    
    results = []
    
    # Проверка папок (не требует запущенного сервера)
    results.append(("Структура папок", test_folders()))
    
    # Проверка API (требует запущенный сервер)
    if test_api_health():
        results.append(("Список файлов", test_get_files()))
        results.append(("Расписание", test_get_schedule()))
        results.append(("История отчетов", test_get_reports()))
        results.append(("Таймер", test_countdown()))
    else:
        print("\n⚠️ Сервер не запущен. Остальные тесты пропущены.")
    
    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print("\n" + "-"*60)
    print(f"Пройдено: {passed}/{total}")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
    else:
        print("⚠️ Некоторые тесты не прошли. Проверьте логи.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

