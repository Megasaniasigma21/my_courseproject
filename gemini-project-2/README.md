# Bochflix — Backend API, Клиентский загрузчик и CLI управления БД

Проект серверной части и динамической интеграции для сайта кинохостинга **Bochflix**.

---

## 1. Архитектура и структура проекта

```
gemini-project-2/
├── backend/                        # Исходный код FastAPI сервера
│   ├── routes/
│   │   ├── __init__.py
│   │   └── movies.py               # Эндпоинты GET /api/v1/movies, GET /api/v1/banners, CRUD
│   ├── utils/
│   │   ├── __init__.py
│   │   └── pnr.py                  # Генератор и валидатор PNR (6 символов: 0-9 + согласные)
│   ├── __init__.py
│   ├── config.py                   # Настройки (Pydantic BaseSettings, пути, CORS, порт)
│   ├── database.py                 # Подключение SQLAlchemy, сессии и init_db
│   ├── main.py                     # Главный файл FastAPI (CORS, роуты, статика в dev)
│   ├── models.py                   # SQLAlchemy модель сущности Movie
│   └── schemas.py                  # Pydantic схемы (MovieCatalogItem, MovieBannerItem, MovieDetail)
├── data/
│   └── cinema.db                   # База данных SQLite
├── media/                          # Локальная папка для медиафайлов (для тестов / dev)
├── manage_db.py                    # Автономная CLI-утилита для интерактивного наполнения БД
├── frontend_loader.js              # Модуль запросов и рендеринга на стороне клиента (Vanilla JS)
├── front-end/                      # Оригинальная верстка сайта (код не изменялся)
│   ├── HTML/
│   │   └── index.html              # Разметка страниц
│   ├── JS/
│   │   ├── frontend_loader.js      # Копия загрузчика для удобного подключения
│   │   └── script.js               # Оригинальный скрипт (слайдер, скролл, MutationObserver)
│   ├── STYLES/                     # Стили проекта (style.css, reset.css, optimize.css)
│   └── IMAGES/                     # Логотипы, иконки и тестовые изображения
├── tests/                          # Автоматические тесты (pytest)
│   └── test_backend.py
├── requirements.txt                # Зависимости Python
└── .env.example                    # Пример переменных окружения
```

---

## 2. Спецификация базы данных и сущности `Movie`

Используется **SQLite + SQLAlchemy 2.0**. Таблица `movies` включает следующие поля:

| Поле | Тип | Описание | Ограничение |
|---|---|---|---|
| `id` | INTEGER | Первичный ключ | PRIMARY KEY, AUTOINCREMENT |
| `pnr` | VARCHAR(6) | Уникальный код фильма | UNIQUE, NOT NULL, 6 символов (`0-9` + `BCDFGHJKLMNPQRSTVWXYZ`) |
| `title` | VARCHAR(255) | Название фильма | NOT NULL |
| `description` | TEXT | Описание сюжета | NOT NULL |
| `duration` | VARCHAR(50) | Длительность (например, `169 мин`) | NOT NULL |
| `quality` | VARCHAR(20) | Качество (`4K`, `1080p`) | NOT NULL |
| `poster_url` | VARCHAR(500) | Путь/URL постера (раздается Nginx) | NOT NULL |
| `banner_desktop_url` | VARCHAR(500) | Баннер для ПК 16:9 | NOT NULL |
| `banner_mobile_url` | VARCHAR(500) | Баннер для мобилок 1.2:1 (~6:5) | NOT NULL |
| `movie_page_url` | VARCHAR(500) | Ссылка на страницу фильма (`/movie/{pnr}`) | NOT NULL |
| `rating` | FLOAT | Рейтинг (зарезервировано) | NULL по умолчанию |
| `logo_url` | VARCHAR(500) | Логотип фильма (зарезервировано) | NULL по умолчанию |
| `trailer_url` | VARCHAR(500) | URL трейлера (зарезервировано) | NULL по умолчанию |

> **Правило PNR**: PNR генерируется криптографически стойким генератором `secrets` строго из 10 цифр (`0-9`) и 21 заглавной английской согласной буквы (`BCDFGHJKLMNPQRSTVWXYZ`). Английские гласные (`A`, `E`, `I`, `O`, `U`) исключены.

---

## 3. Быстрый запуск бэкенда

### 3.1. Установка виртуального окружения и зависимостей
```bash
# Создание виртуального окружения (если еще не создано)
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### 3.2. Запуск FastAPI сервера
```bash
# Вариант 1: Через модуль backend
python -m backend.main

# Вариант 2: Напрямую через Uvicorn
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

После старта доступны:
- Интерактивная документация Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Альтернативная документация ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- Каталог фильмов: [http://127.0.0.1:8000/api/v1/movies](http://127.0.0.1:8000/api/v1/movies)
- Баннеры слайдера: [http://127.0.0.1:8000/api/v1/banners](http://127.0.0.1:8000/api/v1/banners)

---

## 4. Инструкция по работе с CLI-скриптом (`manage_db.py`)

Скрипт `manage_db.py` позволяет наполнять и администрировать базу данных без прямого написания SQL-запросов.

### 4.1. Главное интерактивное меню
```bash
python manage_db.py
```
Откроется меню:
```
====================================================================
          BOCHFLIX — УТИЛИТА НАПОЛНЕНИЯ И УПРАВЛЕНИЯ БД
====================================================================
Выберите действие:
  1) Добавить новый фильм (интерактивный ввод с PNR и предпросмотром)
  2) Показать список всех фильмов в БД
  3) Просмотреть карточку фильма по PNR
  4) Удалить фильм по PNR
  5) Инициализировать таблицы БД
  0) Выход
```

### 4.2. Добавление фильма (Мастер ввода с предпросмотром)
Команда:
```bash
python manage_db.py add
```
Шаги мастера:
1. **Генерация PNR**: Скрипт генерирует уникальный 6-значный PNR (например, `NMHYTB`). Нажмите `Enter`, чтобы принять его, либо введите свой.
2. **Ввод метаданных**: Запрашиваются название, описание, длительность и качество (выбором из списка: `1) 4K`, `2) 1080p`, `3) 720p`).
3. **Пути к медиа**: Указываются пути к постеру, баннерам для десктопа (16:9) и мобильных (1.2:1).
4. **Предпоказ (Preview)**: В консоль выводится аккуратная карточка со всеми параметрами.
5. **Подтверждение**: Запрос `Сохранить фильм в БД? (y/n)`. При согласии запись коммитится в SQLite.

### 4.3. Быстрые команды CLI
```bash
# Список всех фильмов в базе
python manage_db.py list

# Детальная карточка фильма по PNR
python manage_db.py show NMHYTB

# Удаление фильма по PNR с подтверждением
python manage_db.py delete NMHYTB

# Проверка/инициализация таблиц БД
python manage_db.py init
```

---

## 5. Подключение клиентского загрузчика (`frontend_loader.js`)

Скрипт `frontend_loader.js` разработан в строгом соответствии с правилом **не изменять существующий код верстки**.

### 5.1. Как подключить к `index.html`
В файле `front-end/HTML/index.html` в самом низу страницы перед закрывающим тегом `</body>` добавьте подключение скрипта:

```html
    <!-- Оригинальный скрипт -->
    <script src="../JS/script.js"></script>

    <!-- Новый скрипт динамической загрузки данных из FastAPI -->
    <script src="../JS/frontend_loader.js"></script>
</body>
</html>
```

### 5.2. Как работает загрузчик
1. **Событие `DOMContentLoaded`**: Скрипт ожидает готовности DOM и выполняет параллельные запросы к `/api/v1/banners` и `/api/v1/movies`.
2. **Адаптивный слайдер**:
   - Формирует разметку со стандартизированным HTML5-тегом `<picture>`:
     ```html
     <picture>
         <source media="(max-width: 768px)" srcset="/images/banners/banner_mobile.webp">
         <img src="/images/banners/banner_desktop.webp" alt="Название">
     </picture>
     ```
   - Браузер **автоматически запрашивает мобильный баннер** при ширине экрана до 768px и **десктопный 16:9** при ширине выше 768px.
   - За счет существующего в `script.js` механизма `MutationObserver`, дорожка слайдера автоматически пересобирается (`rebuild()`), создаются бесшовные клоны для зацикливания, настраиваются кнопки-стрелки и сенсорный/мышиный drag.
3. **Карточки каталога**:
   - Наполняют горизонтальный трек «Новое и популярное» (`.main__new-popular .main__standart-card--track`) и дополнительные треки категорий.
   - Отображают постер, бейдж качества (`4K`, `1080p`), длительность, заголовок и рейтинг.
   - Ссылка ведет на `/movie/{pnr}`.
   - Во время горизонтального перетаскивания мышью случайные клики блокируются.
4. **Безопасная изоляция**: Скрипт самостоятельно внедряет необходимые визуальные оверлеи и бейджи через тег `<style>` в `head`, не трогая оригинальные CSS-файлы проекта.

### 5.3. Переопределение URL API при необходимости
Если фронтенд открывается на другом порту или домене, в HTML перед загрузчиком можно задать глобальную переменную:
```html
<script>
    window.BOCHFLIX_API_URL = "http://127.0.0.1:8000";
</script>
<script src="../JS/frontend_loader.js"></script>
```

---

## 6. Конфигурация Nginx в продакшене

В продакшене отдачей статики (постеров, баннеров) и HLS-видеопотока занимается Nginx, а запросы `/api/` проксируются в FastAPI (Uvicorn):

```nginx
server {
    listen 80;
    server_name kino.example.com;

    # Фронтенд (HTML, CSS, JS)
    location / {
        root /var/www/bochflix/front-end/HTML;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Статика фронтенда (стили, скрипты, шрифты)
    location ~* \.(css|js|woff2|woff|ttf|svg|ico)$ {
        root /var/www/bochflix/front-end;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # Постеры, промо-баннеры и медиа
    location /images/ {
        alias /var/www/bochflix/front-end/IMAGES/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    # HLS видеопотоки (m3u8, ts)
    location /hls/ {
        alias /var/media/hls/;
        types {
            application/vnd.apple.mpegurl m3u8;
            video/mp2t ts;
        }
        add_header Cache-Control "no-cache";
        add_header Access-Control-Allow-Origin *;
    }

    # Проксирование API в FastAPI (Uvicorn)
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 7. Запуск тестов

Для запуска полного набора юнит- и интеграционных тестов:
```bash
PYTHONPATH=. .venv/bin/pytest tests -v
```
Все тесты проверяют валидацию PNR, отсутствие гласных, работу API, пагинацию, удаление и отсутствие моковых данных.
