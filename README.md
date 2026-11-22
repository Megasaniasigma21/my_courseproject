# Bochkino

Курсовой проект онлайн-кинотеатра. Android-приложение на Kotlin получает каталог и данные профиля через REST API. Сервер на FastAPI использует SQLite, видео воспроизводится через AndroidX Media3.

## Запуск сервера в Windows

Из корня проекта выполни в PowerShell:

```powershell
cd gemini-project-2
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_server.py
```

После запуска открой http://127.0.0.1:8000/docs. При первом запуске сервер создаёт локальную базу. Для просмотра фильмов потребуется добавить собственные медиафайлы в `gemini-project-2/media/` и соответствующие записи в каталог.

## Запуск Android-приложения

Открой корень проекта в Android Studio. В `gradle.properties` укажи `bochkinoApiBaseUrl=http://10.0.2.2:8000/api/` для стандартного эмулятора Android Studio. Для телефона в той же сети подставь локальный IPv4 компьютера вместо `10.0.2.2`. Синхронизируй Gradle и запусти модуль `app`.

## Структура

| Путь | Назначение |
| --- | --- |
| `app/` | Android-клиент, экраны, сетевой код и ресурсы |
| `gemini-project-2/backend/` | REST API, модели и создание схемы SQLite |
| `gemini-project-2/tests/` | Тесты сервера |
| `nginx/` | nginx для Windows и конфигурация прокси. Перед запуском проверь адрес API и пути к файлам в `servers/bochflix.conf` |
| `Project-map/` | Интерактивная карта проекта |

Рабочая база, резервные копии, ключ профилей и медиатека хранятся локально и исключены через `.gitignore`.
