#!/usr/bin/env python
import os
import sys
import time
import asyncio
import threading
import subprocess
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class ProjectLauncher:
    def __init__(self):
        self.processes = {}
        self.stop_event = threading.Event()
        
    def start_parser(self):
        print("\n[ЗАПУСК] Запускаем парсер FL.ru...")
        
        parser_path = Path("FL/parser.py").absolute()
        if not parser_path.exists():
            print(f"[ОШИБКА] Файл парсера не найден: {parser_path}")
            return None
            
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        try:
            process = subprocess.Popen(
                [sys.executable, str(parser_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                cwd=os.path.dirname(parser_path)
            )
            
            self.processes["parser"] = process
            print(f"[УСПЕХ] Парсер FL.ru запущен (PID: {process.pid})")
            
            threading.Thread(
                target=self._read_output,
                args=(process, "[ПАРСЕР]"),
                daemon=True
            ).start()
            
            return process
        except Exception as e:
            print(f"[КРИТИЧЕСКАЯ ОШИБКА] Не удалось запустить парсер: {e}")
            return None
    
    def start_telegram_bot(self):
        print("\n[ЗАПУСК] Запускаем Telegram бота...")
        
        bot_path = Path("TelegramBot/bot.py").absolute()
        if not bot_path.exists():
            print(f"[ОШИБКА] Файл Telegram бота не найден: {bot_path}")
            return None
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        try:
            process = subprocess.Popen(
                [sys.executable, str(bot_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                cwd=os.path.dirname(bot_path)
            )
            
            self.processes["telegram_bot"] = process
            print(f"[УСПЕХ] Telegram бот запущен (PID: {process.pid})")
            
            threading.Thread(
                target=self._read_output,
                args=(process, "[ТГ-БОТ]"),
                daemon=True
            ).start()
            
            return process
        except Exception as e:
            print(f"[КРИТИЧЕСКАЯ ОШИБКА] Не удалось запустить Telegram бота: {e}")
            return None
    
    def _read_output(self, process, prefix):
        try:
            for line in iter(process.stdout.readline, ''):
                if self.stop_event.is_set():
                    break
                if line:
                    try:
                        print(f"{prefix} {line.rstrip()}")
                    except UnicodeEncodeError:
                        try:
                            print(f"{prefix} {line.encode('cp866', errors='replace').decode('cp866', errors='replace').rstrip()}")
                        except:
                            print(f"{prefix} [Ошибка отображения строки вывода]")
        except Exception as e:
            print(f"{prefix} [ОШИБКА ЧТЕНИЯ] {e}")
    
    def start_all(self):
        print("\n=== ЗАПУСК КОМПОНЕНТОВ ПРОЕКТА ===")
        print(f"[ИНФОРМАЦИЯ] Текущая директория: {os.getcwd()}")
        print(f"[ИНФОРМАЦИЯ] Директория Python: {sys.executable}")
        
        if any(ord(c) > 127 for c in os.getcwd()):
            print("\n[ПРЕДУПРЕЖДЕНИЕ] Путь к проекту содержит кириллические символы.")
            print("[ПРЕДУПРЕЖДЕНИЕ] Это может вызвать проблемы с запуском компонентов.")
            print("[РЕКОМЕНДАЦИЯ] Переместите проект в директорию с латинскими символами в пути (например, C:\\Projects\\FLParser).")
            print("[ИНФОРМАЦИЯ] Попытка запуска будет продолжена, но могут возникнуть ошибки.\n")
        
        parser = self.start_parser()
        time.sleep(2)
        
        bot = self.start_telegram_bot()
        time.sleep(2)
        
        components = {
            "Парсер FL.ru": parser,
            "Telegram бот": bot,
        }
        
        failed_components = [name for name, proc in components.items() if proc is None]
        
        if failed_components:
            print("\n[ПРЕДУПРЕЖДЕНИЕ] Не удалось запустить следующие компоненты:")
            for name in failed_components:
                print(f"  - {name}")
            print("\nРекомендации:")
            print("1. Проверьте наличие всех необходимых файлов")
            print("2. Установите требуемые зависимости: pip install -r requirements.txt")
            print("3. Переместите проект в директорию без кириллицы в пути")
        else:
            print("\n[УСПЕХ] Все компоненты успешно запущены!")
        
        print("\n=== ВСЕ КОМПОНЕНТЫ ЗАПУЩЕНЫ ===")
        print("Нажмите Ctrl+C для остановки всех процессов")
        
        try:
            while True:
                for name, process in list(self.processes.items()):
                    if process.poll() is not None:
                        print(f"\n[ПРЕДУПРЕЖДЕНИЕ] Процесс {name} завершился с кодом {process.poll()}")
                        del self.processes[name]
                
                if not self.processes:
                    print("\n[ПРЕДУПРЕЖДЕНИЕ] Все процессы завершились. Программа будет остановлена.")
                    break
                    
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_all()
    
    def stop_all(self):
        print("\n\n=== ОСТАНОВКА КОМПОНЕНТОВ ПРОЕКТА ===")
        self.stop_event.set()
        
        for name, process in self.processes.items():
            print(f"[ОСТАНОВКА] Останавливаем {name}...")
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"[ОСТАНОВЛЕН] {name} успешно остановлен")
            except subprocess.TimeoutExpired:
                print(f"[ПРИНУДИТЕЛЬНО] {name} не завершился, принудительное завершение...")
                process.kill()
            except Exception as e:
                print(f"[ОШИБКА] Ошибка при остановке {name}: {e}")
        
        print("\n=== ВСЕ КОМПОНЕНТЫ ОСТАНОВЛЕНЫ ===")

if __name__ == "__main__":
    try:
        launcher = ProjectLauncher()
        launcher.start_all()
    except Exception as e:
        print(f"\n[КРИТИЧЕСКАЯ ОШИБКА] Произошла непредвиденная ошибка: {e}")
        import traceback
        traceback.print_exc()