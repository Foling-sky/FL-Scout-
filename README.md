# Инструкция по запуску парсера FL.ru

## Требования

- Python 3.8 или выше
- Chrome/Chromium браузер

## Структура проекта
```
├── main.py                 # Основной файл запуска
├── requirements.txt        # Общие зависимости проекта
├── FL/                     # Директория парсера
│   ├── parser.py           # Код парсера
│   ├── config.json         # Настройки парсера
│   ├── requirements.txt    # Зависимости парсера
│   ├── processed_tasks.json # Данные с заданиями
│   └── www.fl.ru_cookies.txt # Файл с cookies
└── TelegramBot/            # Директория Telegram бота
    ├── bot.py              # Код Telegram бота
    ├── requirements.txt    # Зависимости бота
    ├── .env                # Настройки бота
    └── user_data.db        # База данных пользователей
```

## Шаги для установки и запуска

### 1. Подготовка окружения

1. **Клонирование репозитория**:
   ```bash
   git clone <ссылка_на_репозиторий>
   cd <директория_проекта>
   ```

2. **Создание виртуального окружения**:
   ```bash
   # Для Windows
   python -m venv venv
   venv\Scripts\activate
   
   # Для Linux/MacOS
   python3 -m venv venv
   source venv/bin/activate
   ```

### 2. Подготовка файлов

1. **Файл cookies**:

   - Поместите файл с куками от сайта FL.ru в папку `FL/` с названием `www.fl.ru_cookies.txt`
   - Файл должен быть в формате Netscape Cookie File
   - Как получить файл cookies:
     1. Установите расширение для браузера "EditThisCookie" или "Cookie-Editor"
     2. Войдите в свой аккаунт на сайте FL.ru
     3. Откройте расширение и экспортируйте cookies в формате Netscape
     4. Сохраните файл как `www.fl.ru_cookies.txt` в папке `FL/`

2. **Настройка .env файла**:

   - В корне проекта создайте файл `.env` со следующими данными:
     ```
     # Не обязательно, нужен только если хотите использовать Telegram бота
     TELEGRAM_BOT_TOKEN=ваш_токен_бота

     # Не обязательно, нужен только для AI-обработки задач
     OPENAI_API_KEY=ваш_api_ключ_openai
     ```

   - Как получить токен Telegram бота:
     1. Откройте Telegram и найдите @BotFather
     2. Отправьте команду /newbot
     3. Следуйте инструкциям для создания нового бота
     4. После создания бота вы получите токен, который нужно скопировать в .env файл

   - Как получить API ключ OpenAI:
     1. Зарегистрируйтесь на сайте OpenAI (https://platform.openai.com/)
     2. Перейдите в раздел API keys
     3. Создайте новый ключ API
     4. Скопируйте его в .env файл

3. **Настройка TelegramBot/.env файла** (если планируете использовать Telegram бота):

   - Создайте файл `TelegramBot/.env` со следующим содержимым:
     ```
     TELEGRAM_BOT_TOKEN=ваш_токен_бота
     OPENAI_API_KEY=ваш_api_ключ_openai
     DATA_FILE_PATH=../FL/processed_tasks.json
     ```

### 3. Установка зависимостей

```bash
# Установка основных зависимостей
pip install -r requirements.txt

# Установка зависимостей для парсера
pip install -r FL/requirements.txt

# Установка зависимостей для Telegram бота (если нужно)
pip install -r TelegramBot/requirements.txt
```

### 4. Запуск

Для запуска всего проекта (парсер + Telegram бот):

```bash
python main.py
```

Для запуска только парсера:

```bash
cd FL
python parser.py
```

Для запуска только Telegram бота:

```bash
cd TelegramBot
python bot.py
```

### 5. Настройка поиска

Вы можете настроить параметры поиска задач в файле `FL/config.json`:

- Категории цен
- Ключевые слова для исключения
- Ключевые слова для включения

## Конфигурация конфиденциальных данных

Для работы приложения требуется настройка следующих конфиденциальных данных:

1. **Файл `.env` в директории TelegramBot**:
   - Скопируйте файл `.env.example` в `.env`
   - Заполните следующие параметры:
     - `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота (получите у [@BotFather](https://t.me/BotFather))
     - `OPENAI_API_KEY` - ключ API OpenAI (получите на [сайте OpenAI](https://platform.openai.com))

2. **Файл куки для FL.ru**:
   - Скопируйте файл `FL/www.fl.ru_cookies.example.txt` в `FL/www.fl.ru_cookies.txt`
   - Заполните его вашими куки для авторизации на сайте FL.ru (инструкции в файле примера)

⚠️ **ВАЖНО**: Никогда не публикуйте файлы с конфиденциальными данными в репозитории!

## Примечания

- Парсер сохраняет результаты в файл `FL/processed_tasks.json`
- Telegram бот использует данные из этого файла
- Для корректной работы парсера необходимо иметь актуальные cookies от сайта FL.ru
- Cookies необходимо обновлять, если вы вышли из аккаунта или они устарели
- Если путь к проекту содержит кириллические символы, могут возникнуть проблемы
