import os
import time
import asyncio
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

load_dotenv()

loop = asyncio.new_event_loop()

def run_async_callback(callback):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(callback())

class TaskFileHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
        self.last_modified = time.time()
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(os.getenv("DATA_FILE_PATH").split('/')[-1]):
            current_time = time.time()
            if current_time - self.last_modified > 1:
                self.last_modified = current_time
                thread = Thread(target=run_async_callback, args=(self.callback,))
                thread.daemon = True
                thread.start()
                print(f"Файл {event.src_path} изменен, запущена обработка обновлений")

class FileMonitor:
    def __init__(self, callback):
        data_file_path = os.getenv("DATA_FILE_PATH")
        self.file_path = os.path.abspath(data_file_path)
        self.directory = os.path.dirname(self.file_path)
        self.event_handler = TaskFileHandler(callback)
        self.observer = Observer()
        
    def start(self):
        self.observer.schedule(self.event_handler, self.directory, recursive=False)
        self.observer.start()
        print(f"Начат мониторинг файла: {self.file_path}")
        
    def stop(self):
        self.observer.stop()
        self.observer.join()
        print("Мониторинг файла остановлен") 