import os
import json
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
from ai_processor import AIProcessor
from datetime import datetime

load_dotenv()

class TaskProcessor:
    def __init__(self, db):
        self.data_file_path = os.getenv("DATA_FILE_PATH")
        self.db = db
        self.ai_processor = AIProcessor()
        self.last_processed_id = None
        
    def read_tasks(self) -> Dict[str, Any]:
        try:
            with open(self.data_file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            print(f"Ошибка при чтении файла с заказами: {e}")
            return {}
    
    def get_latest_task_id(self) -> Optional[str]:
        tasks = self.read_tasks()
        if not tasks:
            return None
        
        latest_task_id = None
        latest_date = None
        
        for task_id, task in tasks.items():
            publication_date = task.get('publication_date', '')
            if not publication_date:
                continue
                
            date_obj = self.parse_publication_date(publication_date)
            
            if latest_date is None or date_obj > latest_date:
                latest_date = date_obj
                latest_task_id = task_id
        
        return latest_task_id
    
    def get_new_tasks(self, last_id: Optional[str] = None) -> Dict[str, Any]:
        if last_id is None and self.last_processed_id is not None:
            last_id = self.last_processed_id
            
        tasks = self.read_tasks()
        if not tasks:
            return {}
        
        if not last_id or last_id not in tasks:
            latest_id = self.get_latest_task_id()
            return {latest_id: tasks[latest_id]} if latest_id else {}
        
        sorted_tasks = []
        for task_id, task in tasks.items():
            sorted_tasks.append((task_id, task))
        
        sorted_tasks.sort(key=lambda x: self.parse_publication_date(x[1].get('publication_date', '')))
        
        last_index = -1
        for index, (task_id, _) in enumerate(sorted_tasks):
            if task_id == last_id:
                last_index = index
                break
                
        if last_index == -1:
            return {}
        
        new_tasks = {}
        for i in range(last_index + 1, len(sorted_tasks)):
            task_id, task = sorted_tasks[i]
            new_tasks[task_id] = task
        
        return new_tasks
    
    def filter_task_for_user(self, task: Dict[str, Any], user_settings: Dict[str, Any]) -> bool:
        keywords = user_settings.get('keywords', [])
        if keywords:
            description = task.get('full_description', '').lower()
            if not any(keyword.lower() in description for keyword in keywords):
                return False
        
        price_filters = user_settings.get('price_filters', ['any'])
        price = task.get('price', 0)
        price_text = task.get('price_text', '').lower()
        
        if 'any' in price_filters:
            return True
        
        if 'negotiated' in price_filters and 'договоренности' in price_text:
            return True
        
        if 'min_price' in price_filters:
            min_price = user_settings.get('price_min', 0)
            if price >= min_price:
                return True
        
        return False
    
    def process_task_for_notification(self, task_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
        ai_description = self.ai_processor.process_task_description(task.get('full_description', ''))
        
        return {
            'task_id': task_id,
            'ai_description': ai_description,
            'price_text': task.get('price_text', 'Цена не указана'),
            'price': task.get('price', 0),
            'publication_date': task.get('publication_date', ''),
            'url': task.get('url', '')
        }
    
    def parse_publication_date(self, date_str: str) -> datetime:
        if not date_str or date_str.strip() == '':
            return datetime.now()
            
        try:
            main_date_str = date_str.split('[')[0].strip()
            
            pattern = r'(\d{2}\.\d{2}\.\d{4})\s*\|\s*(\d{2}:\d{2})'
            match = re.search(pattern, main_date_str)
            
            if match:
                date_part, time_part = match.groups()
                return datetime.strptime(f"{date_part} {time_part}", "%d.%m.%Y %H:%M")
            
            return datetime.strptime(main_date_str, "%d.%m.%Y | %H:%M")
            
        except Exception as e:
            print(f"Ошибка при парсинге даты '{date_str}': {e}")
            return datetime.now()
    
    def get_notifications_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        user_settings = self.db.get_user_settings(user_id)
        if not user_settings:
            return []
        
        notifications = []
        last_sent_id = user_settings.get('last_sent_id', None)
        last_sent_descriptions = set()
        
        tasks = self.read_tasks()
        if not tasks:
            return []
            
        id_to_description = {task_id: task.get('full_description', '') 
                           for task_id, task in tasks.items()}
        
        is_first_run = not last_sent_id or last_sent_id not in tasks
        
        if not is_first_run:
            sorted_tasks = []
            for task_id, task in tasks.items():
                sorted_tasks.append((task_id, task))
            
            sorted_tasks.sort(key=lambda x: self.parse_publication_date(x[1].get('publication_date', '')))
            
            last_index = -1
            for index, (task_id, _) in enumerate(sorted_tasks):
                if task_id == last_sent_id:
                    last_index = index
                    break
                    
            for i in range(last_index + 1):
                task_id, _ = sorted_tasks[i]
                description = id_to_description.get(task_id, '')
                if description:
                    last_sent_descriptions.add(description)
        
        if is_first_run:
            sorted_tasks = []
            for task_id, task in tasks.items():
                sorted_tasks.append((task_id, task))
            
            sorted_tasks.sort(key=lambda x: self.parse_publication_date(x[1].get('publication_date', '')))
            
            if sorted_tasks:
                task_id, task = sorted_tasks[-1]
                if self.filter_task_for_user(task, user_settings):
                    notification = self.process_task_for_notification(task_id, task)
                    notifications.append(notification)
            return notifications
        
        sorted_tasks = []
        for task_id, task in tasks.items():
            sorted_tasks.append((task_id, task))
        
        sorted_tasks.sort(key=lambda x: self.parse_publication_date(x[1].get('publication_date', '')))
        
        last_index = -1
        for index, (task_id, _) in enumerate(sorted_tasks):
            if task_id == last_sent_id:
                last_index = index
                break
        
        if last_index == -1:
            if sorted_tasks:
                task_id, task = sorted_tasks[-1]
                if self.filter_task_for_user(task, user_settings):
                    notification = self.process_task_for_notification(task_id, task)
                    notifications.append(notification)
            return notifications
        
        for i in range(last_index + 1, len(sorted_tasks)):
            task_id, task = sorted_tasks[i]
            
            current_description = task.get('full_description', '')
            
            if current_description in last_sent_descriptions:
                continue
                
            if self.filter_task_for_user(task, user_settings):
                notification = self.process_task_for_notification(task_id, task)
                notifications.append(notification)
                
                if current_description:
                    last_sent_descriptions.add(current_description)
                
        return notifications 