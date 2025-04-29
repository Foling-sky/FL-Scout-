import asyncio
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import random
import time
import json
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from yarl import URL
import undetected_chromedriver as uc
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class WorkzilaParser:
    def __init__(self, config_path: str = "config.json", cookies_path: str = "www.fl.ru_cookies.txt"):
        self.base_url = "https://www.fl.ru"
        self.ua = UserAgent()
        self.session = None
        self.config = self.load_config(config_path)
        self.cookies = self.load_cookies(cookies_path)
        self.processed_tasks = self.load_processed_tasks()
        self.categories = [
            {"name": "Сайты", "option_id": "vs1___option-0"},
            {"name": "Программирование", "option_id": "vs1___option-2"},
            {"name": "AI — искусственный интеллект", "option_id": "vs1___option-11"},
            {"name": "Социальные сети", "option_id": "vs1___option-12"},
            {"name": "Мессенджеры", "option_id": "vs1___option-14"},
            {"name": "Браузеры", "option_id": "vs1___option-17"},
            {"name": "Крипто и блокчейн", "option_id": "vs1___option-18"},
            {"name": "Интернет-магазины", "option_id": "vs1___option-20"},
            {"name": "Автоматизация бизнеса", "option_id": "vs1___option-21"}
        ]
        
    def load_config(self, config_path: str) -> Dict:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_cookies(self, cookies_path: str) -> Dict[str, str]:
        cookies = {}
        try:
            print(f"Пытаемся загрузить куки из файла: {cookies_path}")
            with open(cookies_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if not line.startswith('#'):
                        fields = line.strip().split('\t')
                        if len(fields) >= 7:
                            domain = fields[0]
                            path = fields[2]
                            name = fields[5]
                            value = fields[6]
                            
                            if domain.endswith('fl.ru'):
                                cookies[name] = value
                                print(f"✓ Загружен куки: {name}")
                                
            if not cookies:
                print("\nВ файле нет куки для fl.ru!")
            else:
                print(f"\nЗагружено {len(cookies)} куки")
                
        except FileNotFoundError:
            print(f"Файл с куки не найден: {cookies_path}")
        except Exception as e:
            print(f"Ошибка при загрузке куки: {str(e)}")
        
        return cookies

    def load_processed_tasks(self) -> Dict[str, Dict]:
        try:
            if os.path.exists('processed_tasks.json'):
                with open('processed_tasks.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Ошибка при загрузке истории заданий: {str(e)}")
            return {}
            
    def parse_publication_date(self, date_str: str) -> datetime:
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
    
    def save_processed_tasks(self):
        try:
            for task_id, task_data in self.processed_tasks.items():
                if 'responses_count' in task_data:
                    del task_data['responses_count']
                if 'responses_info' in task_data:
                    del task_data['responses_info']
            
            sorted_tasks = sorted(
                self.processed_tasks.items(),
                key=lambda x: self.parse_publication_date(x[1].get('publication_date', '')),
                reverse=True
            )
            
            self.processed_tasks = dict(sorted_tasks)
            
            print(f"Сохранено {len(self.processed_tasks)} заказов")
                    
            with open('processed_tasks.json', 'w', encoding='utf-8') as f:
                json.dump(self.processed_tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка при сохранении истории заданий: {str(e)}")

    def is_task_processed(self, task_id: str, task_data: Dict) -> bool:
        if task_id in self.processed_tasks:
            return True
        return False
    
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
            
            for name, value in self.cookies.items():
                self.session.cookie_jar.update_cookies(
                    {name: value},
                    URL(self.base_url)
                )
            
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'Host': 'www.fl.ru',
                'Origin': 'https://www.fl.ru'
            }
            
            self.session.headers.update(headers)
    
    async def close_session(self):
        if self.session:
            if not self.session.closed:
                await self.session.close()
            self.session = None

    def get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
            "Referer": f"{self.base_url}/projects/",
        }
    
    async def check_auth(self) -> bool:
        url = f"{self.base_url}/projects/"
        try:
            await self.init_session()
            
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Referer': self.base_url,
                'Host': 'www.fl.ru',
                'Origin': 'https://www.fl.ru'
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    auth_markers = [
                        'name=""',
                        'id=""',
                        'class="b-layout__header_auth"',
                        'class="b-layout__header_auth_wrapper"'
                    ]
                    
                    for marker in auth_markers:
                        if marker in html:
                            print(f"Успешная авторизация на FL.ru! (найден маркер: {marker})")
                            return True
                            
                    print("Авторизация не удалась. Маркеры авторизации не найдены.")
                    print("Проверьте актуальность куки или попробуйте обновить их.")
                else:
                    print(f"Ошибка при проверке авторизации: статус {response.status}")
                    
        except Exception as e:
            print(f"Ошибка при проверке авторизации: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
        return False
    
    async def fetch_page(self, url: str) -> Optional[str]:
        await self.init_session()
        try:
            await asyncio.sleep(random.uniform(1, 3))
            async with self.session.get(url, headers=self.get_headers()) as response:
                if response.status == 200:
                    return await response.text()
                print(f"Ошибка при получении страницы {url}: {response.status}")
                return None
        except Exception as e:
            print(f"Ошибка при запросе {url}: {str(e)}")
            return None
    
    async def parse_detailed_task(self, task_url: str) -> Dict:
        print(f"Получаю детальную информацию о заказе: {task_url}")
        
        detailed_info = {
            "full_description": "",
            "responses_count": 0,
            "responses_info": "",
            "publication_date": "",
            "publication_info": "",
            "has_executor": False
        }
        
        try:
            html = await self.fetch_page(task_url)
            if not html:
                print("Не удалось получить страницу заказа")
                return detailed_info
                
            soup = BeautifulSoup(html, 'html.parser')
            
            executor_block = soup.select_one('div.d-flex.align-items-center:has(svg[width="32"][height="32"] use[xlink\\:href="#user_chosen"])')
            if executor_block:
                detailed_info["has_executor"] = True
                print("Исполнитель уже определен для этого заказа")
                return detailed_info
            
            description_block = soup.select_one('div[id^="projectp"]')
            if description_block:
                detailed_info["full_description"] = description_block.text.strip()
            
            responses_block = soup.select_one('div.text-4.d-flex.align-items-center')
            if responses_block:
                responses_text = responses_block.text.strip()
                if responses_text:
                    detailed_info["responses_info"] = responses_text
                    
                    try:
                        import re
                        numbers = re.findall(r'\d+', responses_text)
                        if numbers:
                            detailed_info["responses_count"] = int(numbers[0])
                    except Exception as e:
                        print(f"Ошибка при извлечении количества откликов: {str(e)}")
            
            publication_block = soup.select_one('div.b-layout__txt.b-layout__txt_padbot_30.mt-32')
            if publication_block:
                publication_info = publication_block.text.strip()
                detailed_info["publication_info"] = publication_info
                
                date_block = publication_block.select_one('div.text-5')
                if date_block:
                    detailed_info["publication_date"] = date_block.text.strip()
            
            budget_block = soup.select_one('div.text-4.mb-4')
            if budget_block:
                budget_info = budget_block.text.strip()
                detailed_info["budget_info"] = budget_info
                
            return detailed_info
            
        except Exception as e:
            print(f"Ошибка при парсинге детальной информации о заказе: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return detailed_info

    def save_task(self, task: Dict):
        task_id = task['id']
        
        if self.is_task_processed(task_id, task):
            print(f"Задание {task_id} уже было обработано ранее")
            return False
            
        self.processed_tasks[task_id] = {
            'price': task['price'],
            'price_text': task['price_text'],
            'payment_type': task['payment_type'],
            'description': task['description'],
            'title': task['title'],
            'url': task['url'],
            'posted_time': task['posted_time'],
            'views': task['views'],
            'responses': task['responses'],
            'full_description': task.get('full_description', ''),
            'publication_date': task.get('publication_date', ''),
            'processed_at': datetime.now().isoformat()
        }
        
        self.save_processed_tasks()
        return True
    
    async def parse_tasks(self) -> Tuple[List[Dict], Dict]:
        print("\nНачинаю парсинг ленты заданий...")
        driver = None
        tasks = []
        
        stats = {
            'found': 0,
            'new': 0,
            'duplicates': 0,
            'skipped': 0,
            'has_executor': 0,
            'detailed_info_obtained': 0
        }
        
        try:
            options = uc.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--start-maximized")
            
            print("Запускаю браузер в фоновом режиме...")
            driver = uc.Chrome(
                options=options,
                headless=True
            )
            
            print("Открываю начальную страницу...")
            driver.get(self.base_url)
            time.sleep(2)
            
            url = f"{self.base_url}/projects/"
            print(f"\nПереходим на страницу с заданиями: {url}")
            driver.get(url)
            time.sleep(5)
            
            print("\nНачинаю выбор категорий...")
            for category in self.categories:
                try:
                    dropdown = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "#vs1__combobox"))
                    )
                    dropdown.click()
                    print(f"Открыл выпадающий список для выбора категории: {category['name']}")
                    time.sleep(1)
                    
                    options = WebDriverWait(driver, 5).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".vs__dropdown-option"))
                    )
                    
                    found = False
                    for option in options:
                        if category['name'] in option.text:
                            option.click()
                            print(f"✓ Выбрана категория: {category['name']}")
                            found = True
                            time.sleep(1.5)
                            break
                    
                    if not found:
                        print(f"✗ Не удалось найти категорию: {category['name']}")
                        driver.find_element(By.TAG_NAME, "body").click()
                except Exception as e:
                    print(f"✗ Ошибка при выборе категории {category['name']}: {str(e)}")
                    try:
                        driver.find_element(By.TAG_NAME, "body").click()
                    except:
                        pass
            
            print("\nПрименяю выбранные фильтры...")
            try:
                apply_button = None
                selectors = [
                    ".ui-button.mt-36.w-100._responsive._primary._md",
                    "//button[contains(., 'Применить фильтр')]",
                    "//button[contains(@class, 'ui-button') and .//div[contains(text(), 'Применить фильтр')]]"
                ]
                
                for selector in selectors:
                    try:
                        if selector.startswith("//"):
                            button = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            button = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                        
                        if button:
                            apply_button = button
                            print(f"✓ Найдена кнопка 'Применить фильтр' с селектором: {selector}")
                            break
                    except:
                        continue
                
                if apply_button:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_button)
                    time.sleep(1)
                    
                    apply_button.click()
                    print("✓ Кнопка 'Применить фильтр' нажата")
                    
                    time.sleep(5)
                else:
                    print("✗ Кнопка 'Применить фильтр' не найдена. Парсинг невозможен.")
                    return [], stats
            except Exception as e:
                print(f"✗ Ошибка при нажатии на кнопку 'Применить фильтр': {str(e)}")
                print("Парсинг невозможен без применения фильтров.")
                return [], stats
            
            print("Ожидаем загрузку результатов после применения фильтров...")
            time.sleep(5)
            
            print("\nПолучаю список заданий...")
            task_elements = driver.find_elements(By.CSS_SELECTOR, 'div[qa-project-name^="project-item"]')
            stats['found'] = len(task_elements)
            
            if stats['found'] > 0:
                print(f"✓ Найдено {stats['found']} заданий")
                
                for element in task_elements:
                    try:
                        task_id = element.get_attribute('id').replace('project-item', '')
                        
                        has_executor = False
                        try:
                            executor_text = element.text
                            if "Исполнитель определён" in executor_text:
                                has_executor = True
                                stats['has_executor'] += 1
                                print(f"Задание {task_id} уже имеет исполнителя, пропускаем")
                                continue
                        except:
                            pass
                        
                        title_elem = element.find_element(By.CSS_SELECTOR, '.b-post__title a')
                        title = title_elem.text.strip()
                        task_url = title_elem.get_attribute('href')
                        
                        price_elem = element.find_element(By.CSS_SELECTOR, '.b-post__price .text-4')
                        price_text = price_elem.text.strip()
                        
                        hourly_markers = ['₽/час', 'р/час', 'руб/час', 'р/ч']
                        fixed_markers = ['/заказ', 'за проект']
                        
                        is_hourly = any(keyword in price_text.lower() for keyword in hourly_markers)
                        is_fixed = any(keyword in price_text.lower() for keyword in fixed_markers)
                        
                        try:
                            if 'договоренности' in price_text.lower():
                                price = 0
                                task_type = "negotiated"
                            elif '—' in price_text:
                                price_range = price_text.split('—')[0].strip()
                                price = int(''.join(filter(str.isdigit, price_range)))
                                
                                if is_hourly:
                                    task_type = "hourly"
                                elif is_fixed:
                                    task_type = "fixed"
                                else:
                                    task_type = "fixed"
                            else:
                                price = int(''.join(filter(str.isdigit, price_text)))
                                
                                if is_hourly:
                                    task_type = "hourly"
                                elif is_fixed:
                                    task_type = "fixed"
                                else:
                                    task_type = "fixed"
                                
                        except:
                            if 'договоренности' in price_text.lower():
                                price = 0
                                task_type = "negotiated"
                            else:
                                price = 0
                                task_type = "unknown"
                        
                        description = element.find_element(By.CSS_SELECTOR, '.b-post__txt.text-5').text.strip()
                        
                        time_elem = element.find_element(By.CSS_SELECTOR, '.text-gray-opacity-4')
                        posted_time = time_elem.text.strip()
                        
                        try:
                            views_elem = element.find_element(By.CSS_SELECTOR, 'span[title="Количество просмотров"] + .text-7')
                            views = views_elem.text.strip()
                        except:
                            views = "Нет данных"
                        
                        try:
                            responses_elem = element.find_element(By.CSS_SELECTOR, 'span[data-id="fl-view-count-href"]')
                            responses = responses_elem.text.strip()
                        except:
                            responses = "Нет ответов"
                        
                        task = {
                            'id': task_id,
                            'title': title,
                            'price': price,
                            'price_text': price_text,
                            'payment_type': task_type,
                            'description': description,
                            'url': task_url,
                            'posted_time': posted_time,
                            'views': views,
                            'responses': responses,
                            'parsed_at': datetime.now().isoformat()
                        }
                        
                        print(f"\nОбработка задания: {title}")
                        print(f"Цена: {price_text}")
                        
                        if self.is_task_processed(task_id, task):
                            stats['duplicates'] += 1
                            print(f"→ Дубликат задания")
                        else:
                            print(f"→ Получение детальной информации о заказе")
                            detailed_info = await self.parse_detailed_task(task_url)
                            
                            if detailed_info.get("has_executor", False):
                                stats['has_executor'] += 1
                                print(f"→ Задание {task_id} имеет исполнителя, пропускаем")
                                continue
                            
                            task.update({
                                'full_description': detailed_info.get('full_description', ''),
                                'responses_count': detailed_info.get('responses_count', 0),
                                'responses_info': detailed_info.get('responses_info', ''),
                                'publication_date': detailed_info.get('publication_date', '')
                            })
                            
                            stats['detailed_info_obtained'] += 1
                            
                            if self.save_task(task):
                                stats['new'] += 1
                                tasks.append(task)
                                print(f"→ Задание сохранено с детальной информацией")
                            
                    except Exception as e:
                        print(f"Ошибка при обработке задания: {str(e)}")
                        continue
                
                print(f"\nСтатистика парсинга:")
                print(f"Найдено заданий: {stats['found']}")
                print(f"Новых заданий: {stats['new']}")
                print(f"Дубликатов: {stats['duplicates']}")
                print(f"Пропущено с исполнителем: {stats['has_executor']}")
                print(f"Пропущено по другим причинам: {stats['skipped']}")
                print(f"Получено детальной информации: {stats['detailed_info_obtained']}")
                
            else:
                print("✗ Задания не найдены")
            
            return tasks, stats
                
        except Exception as e:
            print(f"Ошибка при парсинге заданий: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return [], stats
            
        finally:
            if driver:
                try:
                    driver.quit()
                    print("Браузер закрыт.")
                except Exception:
                    pass

    async def debug_in_browser(self):
        print("Открываю браузер для отладки...")
        
        try:
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            driver = uc.Chrome(
                options=options,
                version_main=131
            )
            
            try:
                print("Открываю начальную страницу...")
                driver.get(self.base_url)
                time.sleep(2)
                
                print("Перехожу на страницу FL.ru...")
                driver.get(f"{self.base_url}/projects/")
                time.sleep(3)
                
                print("\nХотите выбрать категории? (y/n):")
                choice = input().lower()
                
                if choice == 'y':
                    try:
                        print("Открываю выпадающий список категорий...")
                        category_dropdown = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "#vs1__combobox"))
                        )
                        category_dropdown.click()
                        time.sleep(1)
                        print("✓ Выпадающий список категорий открыт")
                        
                        print("\nВыбираю заданные категории:")
                        for category in self.categories:
                            try:
                                option_element = WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.ID, category["option_id"]))
                                )
                                option_element.click()
                                print(f"✓ Выбрана категория: {category['name']}")
                                time.sleep(0.5)
                            except Exception as e:
                                print(f"✗ Не удалось выбрать категорию {category['name']}: {str(e)}")
                        
                        try:
                            body = driver.find_element(By.TAG_NAME, "body")
                            body.click()
                            time.sleep(1)
                            print("✓ Закрыт выпадающий список категорий")
                        except Exception as e:
                            print(f"✗ Не удалось закрыть выпадающий список: {str(e)}")
                        
                        try:
                            apply_button = None
                            selectors = [
                                ".ui-button.mt-36.w-100._responsive._primary._md",
                                "//button[contains(., 'Применить фильтр')]",
                                "//button[contains(@class, 'ui-button') and .//div[contains(text(), 'Применить фильтр')]]"
                            ]
                            
                            for selector in selectors:
                                try:
                                    if selector.startswith("//"):
                                        button = WebDriverWait(driver, 3).until(
                                            EC.element_to_be_clickable((By.XPATH, selector))
                                        )
                                    else:
                                        button = WebDriverWait(driver, 3).until(
                                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                        )
                                    
                                    if button:
                                        apply_button = button
                                        print(f"✓ Найдена кнопка 'Применить фильтр' с селектором: {selector}")
                                        break
                                except:
                                    continue
                            
                            if apply_button:
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_button)
                                time.sleep(1)
                                
                                apply_button.click()
                                print("✓ Кнопка 'Применить фильтр' нажата")
                                time.sleep(3)
                            else:
                                print("✗ Кнопка 'Применить фильтр' не найдена")
                        except Exception as e:
                            print(f"✗ Ошибка при нажатии на кнопку 'Применить фильтр': {str(e)}")
                        
                        time.sleep(3)
                    except Exception as e:
                        print(f"✗ Ошибка при выборе категорий: {str(e)}")
                
                print("\nБраузер открыт. Проверьте работу с категориями и структуру страницы.")
                print("Нажмите Enter, чтобы закрыть браузер...")
                input()
                
            finally:
                driver.quit()
                print("Браузер закрыт.")
                
        except Exception as e:
            print(f"Ошибка при работе с браузером: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def check_processed_tasks(self):
        try:
            current_tasks = self.processed_tasks.copy()
            self.processed_tasks = self.load_processed_tasks()
            
            if current_tasks != self.processed_tasks:
                print("\nОбнаружены изменения в processed_tasks.json")
                print(f"Текущее количество записей: {len(self.processed_tasks)}")
                
        except Exception as e:
            print(f"Ошибка при проверке processed_tasks.json: {str(e)}")

class ParserManager:
    def __init__(self, config_path=None, cookies_path=None):
        if config_path is None or cookies_path is None:
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = config_path or os.path.join(script_dir, "config.json")
            cookies_path = cookies_path or os.path.join(script_dir, "www.fl.ru_cookies.txt")
            
        self.parser = WorkzilaParser(config_path=config_path, cookies_path=cookies_path)
        self.is_running = False
        self.total_stats = {
            'total_parsed': 0,
            'total_new': 0,
            'total_duplicates': 0,
            'total_skipped': 0,
            'total_has_executor': 0,
            'total_detailed_info': 0
        }
        self.start_time = None
        self.last_check_time = None
        self.check_interval = 120
    
    def format_duration(self, seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{int(hours)}ч {int(minutes)}м {int(seconds)}с"
    
    def show_stats(self):
        current_time = time.time()
        duration = current_time - self.start_time if self.start_time else 0
        
        print(f"\n{'='*50}")
        print(f"СТАТИСТИКА ПОСЛЕДНЕЙ ПРОВЕРКИ:")
        print(f"{'='*50}")
        print(f"Время работы парсера: {self.format_duration(duration)}")
        print(f"\nНайдено заказов на FL.ru: {self.total_stats['total_parsed']}")
        print(f"  • Сохранено новых заказов: {self.total_stats['total_new']}")
        print(f"  • Получено детальной информации: {self.total_stats.get('total_detailed_info', 0)}")
        print(f"  • Пропущено существующих: {self.total_stats['total_duplicates']}")
        print(f"  • Пропущено с исполнителем: {self.total_stats.get('total_has_executor', 0)}")
        print(f"  • Пропущено по фильтрам: {self.total_stats['total_skipped']}")
        print(f"\nВсего заказов в базе: {len(self.parser.processed_tasks)}")
        print(f"{'='*50}")
    
    def update_total_stats(self, stats: dict, tasks: List[Dict]):
        self.total_stats['total_parsed'] += stats['found']
        self.total_stats['total_new'] += stats['new']
        self.total_stats['total_duplicates'] += stats['duplicates']
        self.total_stats['total_skipped'] += stats['skipped']
        self.total_stats['total_has_executor'] = self.total_stats.get('total_has_executor', 0) + stats.get('has_executor', 0)
        self.total_stats['total_detailed_info'] = self.total_stats.get('total_detailed_info', 0) + stats.get('detailed_info_obtained', 0)
    
    async def run_parser(self):
        self.is_running = True
        self.start_time = time.time()
        print("\nПарсер запущен в непрерывном режиме. Для остановки нажмите Ctrl+C")
        print("Браузер работает в фоновом режиме.")
        print(f"Интервал проверки новых заданий: {self.check_interval} секунд (2 минуты)")
        
        while self.is_running:
            try:
                self.parser.check_processed_tasks()
                
                tasks, stats = await self.parser.parse_tasks()
                self.update_total_stats(stats, tasks)
                
                self.show_stats()
                
                print(f"\nСледующая проверка через {self.check_interval} секунд...")
                print("Чтобы остановить программу, нажмите Ctrl+C")
                for _ in range(self.check_interval):
                    if not self.is_running:
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                print(f"Ошибка при парсинге: {str(e)}")
                import traceback
                print(traceback.format_exc())
                if self.is_running:
                    await asyncio.sleep(5)

async def main():
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    cookies_path = os.path.join(script_dir, "www.fl.ru_cookies.txt")
    
    manager = ParserManager(config_path, cookies_path)
    
    try:
        print("\n=== ПАРСЕР FL.RU С АВТОМАТИЧЕСКИМ ВЫБОРОМ КАТЕГОРИЙ ===")
        print("\nПарсер будет работать в фоновом режиме.")
        print("После завершения работы, нажмите Ctrl+C для выхода из программы.")
        
        await asyncio.sleep(3)
        
        await manager.run_parser()
    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки...")
        manager.is_running = False
    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        await manager.parser.close_session()
        print("Работа завершена")

async def main_test():
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    cookies_path = os.path.join(script_dir, "www.fl.ru_cookies.txt")
    
    parser = WorkzilaParser(config_path=config_path, cookies_path=cookies_path)
    
    try:
        await parser.init_session()
        
        test_url = "https://www.fl.ru/projects/5419983/napisat-otzyivyi-dlya-salonov-krasotyi.html"
        
        print(f"\nТестирование парсинга детальной информации для URL: {test_url}")
        
        detailed_info = await parser.parse_detailed_task(test_url)
        
        print("\nПолучена следующая детальная информация:")
        print(f"Полное описание: {detailed_info.get('full_description', '')[:100]}...")
        print(f"Количество откликов: {detailed_info.get('responses_count', 0)}")
        print(f"Информация об откликах: {detailed_info.get('responses_info', '')}")
        print(f"Дата публикации: {detailed_info.get('publication_date', '')}")
        print(f"Бюджет: {detailed_info.get('budget_info', '')}")
        
        print("\nПолная полученная информация:")
        import json
        print(json.dumps(detailed_info, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"Ошибка при тестировании: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        await parser.close_session()
        print("Тестирование завершено")

async def test_categories():
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    cookies_path = os.path.join(script_dir, "www.fl.ru_cookies.txt")
    
    parser = WorkzilaParser(config_path=config_path, cookies_path=cookies_path)
    
    try:
        await parser.debug_in_browser()
    except Exception as e:
        print(f"Ошибка при тестировании категорий: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    import sys
    
    try:
        if len(sys.argv) > 1:
            if sys.argv[1] == "--test":
                asyncio.run(main_test())
            elif sys.argv[1] == "--categories":
                asyncio.run(test_categories())
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")
    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")
        import traceback
        print(traceback.format_exc()) 