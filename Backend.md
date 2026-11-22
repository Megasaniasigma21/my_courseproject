# Backend   
# ИНСТРУКЦИЯ ДЛЯ НЕЙРОСЕТИ / РАЗРАБОТЧИКА: ЗАПУСК БЭКЕНДА BOCHFLIX И ИНТЕГРАЦИЯ С ANDROID  
  
> **КОНТЕКСТ ДЛЯ AI-АССИСТЕНТА:**  
> Вы работаете с бэкендом онлайн-кинотеатра **Bochflix**. Ваша цель — развернуть и запустить данный REST API бэкенд на Python/FastAPI и подключить к нему клиентское мобильное приложение на **Android** (Kotlin / Jetpack Compose / ExoPlayer / Retrofit).  
  
---  
  
## 1. Архитектура и стек технологий  
  
- **Язык бэкенда:** Python 3.10+ (протестировано до Python 3.14).  
- **Веб-фреймворк:** FastAPI (ASGI), сервер Uvicorn.  
- **База данных:** SQLite (`data/cinema.db`), ORM SQLAlchemy 2.0.  
  - **Архитектура строго из 2 таблиц (без M2M-таблиц):**  
    1. `movies` (фильмы) — хранит привязку к категориям строкой через запятую (`category_ids="1,4,6"`), отдельные флаги `is_new_and_popular` и `is_hero_banner`, метаданные качества и хронометража.  
    2. `categories` (категории) — хранит `id`, `name`, `slug`, `icon_path` (с дефолтным fallback на иконку).  
- **Статика и стриминг видео:**  
  - Видеофайлы (`.mp4`) раздаются FastAPI и Nginx с поддержкой HTTP 206 Partial Content (Byte-Range Requests), что необходимо для перемотки в **Android ExoPlayer**.  
  - Путь к видео: `/movie/video/{PNR}.mp4` или `/media/video/{PNR}.mp4`.  
  - Постеры и баннеры: `/media/posters/{file}` и `/media/banners/{file}`.  
  
---  
  
## 2. Структура проекта  
  
```text  
gemini-project-2/  
├── backend/  
│   ├── config.py             # Настройки (HOST, PORT, CORS, пути к файлам)  
│   ├── database.py           # Движок SQLite, сессии, автомиграции  
│   ├── main.py               # Точка входа FastAPI, маршруты, раздача статики  
│   ├── models.py             # SQLAlchemy модели: Movie и Category  
│   ├── schemas.py            # Pydantic DTO схемы (валидация/сериализация)  
│   ├── routes/  
│   │   └── movies.py         # REST эндпоинты (фильмы, категории, баннеры)  
│   └── utils/  
│       ├── pnr.py            # Генерация и валидация 6-значных PNR кодов  
│       ├── video_meta.py     # Pure-Python парсер MP4-атомов (длительность/качество)  
│       └── category_parser.py# Парсинг и валидация списков category_ids  
├── data/  
│   └── cinema.db             # Файл SQLite базы данных  
├── media/                    # Папка с медиафайлами  
│   ├── video/                # Видеофайлы (<PNR>.mp4)  
│   ├── posters/              # Вертикальные постеры (~2:3)  
│   └── banners/              # Горизонтальные баннеры (16:9 и 1.2:1)  
├── manage_db.py              # CLI-утилита интерактивного добавления контента  
├── migrate_schema.py         # Скрипт безопасной миграции базы данных  
├── run_server.py             # Скрипт быстрого запуска FastAPI сервера  
├── server.sh                 # Скрипт управления (start, stop, restart, status)  
├── start_servers.sh          # Запуск Nginx + FastAPI  
├── stop_servers.sh           # Остановка процессов  
├── restart_servers.sh        # Перезапуск процессов  
├── requirements.txt          # Зависимости Python  
└── tests/                    # Набор тестов pytest (17 тестов)  
```  
  
---  
  
## 3. Пошаговая инструкция по установке и запуску бэкенда  
  
### Шаг 3.1. Создание виртуального окружения Python  
В корне проекта выполните:  
```bash  
# Создание виртуального окружения  
python3 -m venv .venv  
  
# Активация окружения:  
# На macOS / Linux:  
source .venv/bin/activate  
# На Windows:  
.venv\Scripts\activate  
```  
  
### Шаг 3.2. Установка зависимостей  
```bash  
pip install --upgrade pip  
pip install -r requirements.txt  
```  
  
### Шаг 3.3. Проверка и миграция базы данных  
База данных уже преднастроена в `data/cinema.db`. Чтобы убедиться в корректности схемы колонок:  
```bash  
python migrate_schema.py  
```  
Скрипт автоматически создаст бэкап, проверит колонки `banner`, `mobile_poster`, `is_new_and_popular`, нормализует длительность (`2 ч 29 мин`) и качество (`1080p Full HD`, `720p HD`, `480p`).  
  
### Шаг 3.4. Прогон тестов (весь стек из 17 тестов)  
```bash  
pytest tests -v  
```  
Все тесты должны завершиться со статусом `PASSED`.  
  
### Шаг 3.5. Запуск сервера для Android  
  
#### Вариант А: Быстрый автономный запуск (Рекомендуется для разработки Android)  
Для тестирования Android-приложения Nginx не обязателен, так как FastAPI сам раздает видео с заголовками Range и статику:  
```bash  
python run_server.py  
```  
Либо напрямую через Uvicorn:  
```bash  
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload  
```  
- **Хост `0.0.0.0`** открывает доступ как с `localhost`, так и с внешних устройств локальной сети (телефоны, планшеты, эмуляторы).  
- **Swagger документация API:** `http://localhost:8000/docs`  
- **Проверка здоровья (Healthcheck):** `curl http://localhost:8000/health` (ответ: `{"status":"ok"}`)  
  
#### Вариант Б: Запуск в фоновом режиме демона с Nginx  
```bash  
./server.sh start -d  
# Проверка статуса:  
./server.sh status  
# Остановка:  
./server.sh stop  
```  
  
---  
  
## 4. КРИТИЧЕСКИ ВАЖНО ДЛЯ ANDROID РАЗРАБОТЧИКА  
  
### 4.1. IP-адреса для подключения из Android  
  
| Где запущен Android-клиент | Базовый URL для Android (`BASE_URL`) | Пояснение |  
| :--- | :--- | :--- |  
| **Android Studio Emulator** | `http://10.0.2.2:8000/` | В эмуляторе Android `127.0.0.1` указывает на сам эмулятор. Для доступа к хост-компьютеру используется специальный псевдоним `10.0.2.2`. |  
| **Физический Android-смартфон** (по Wi-Fi) | `http://<IP_КОМПЬЮТЕРА_В_WIFI>:8000/` | Пример: `http://192.168.1.45:8000/`. Компьютер и телефон должны быть в одной Wi-Fi сети. |  
| **Genymotion Emulator** | `http://10.0.3.2:8000/` | Псевдоним хоста в Genymotion. |  
  
### 4.2. Разрешение незашифрованного HTTP трафика (Cleartext Traffic)  
Начиная с Android 9 (API 28), система блокирует HTTP запросы без SSL по умолчанию.   
В проекте Android в файле `app/src/main/AndroidManifest.xml` добавьте атрибут `android:usesCleartextTraffic="true"`:  
  
```xml  
<application  
    android:allowBackup="true"  
    android:icon="@mipmap/ic_launcher"  
    android:label="@string/app_name"  
    android:roundIcon="@mipmap/ic_launcher_round"  
    android:supportsRtl="true"  
    android:theme="@style/Theme.Bochflix"  
    android:usesCleartextTraffic="true"> <!-- ОБЯЗАТЕЛЬНО ДЛЯ HTTP -->  
      
    <activity android:name=".MainActivity" ... />  
</application>  
```  
  
---  
  
## 5. Спецификация REST API для Android  
  
Все эндпоинты возвращают JSON. Относительные пути медиафайлов (`/media/...` или `/movie/video/...`) на клиенте должны дополняться `BASE_URL`.  
  
### 5.1. Главный промо-слайдер (Баннеры)  
- **Запрос:** `GET /api/banners?limit=10`  
- **Назначение:** Верхняя карусель/слайдер на главном экране (фильмы с `is_hero_banner = true`).  
- **Пример ответа (массив объектов):**  
```json  
[  
  {  
    "id": 6,  
    "pnr": "QRY168",  
    "title": "Джокер",  
    "banner": "/media/banners/QRY168_desktop.webp",  
    "mobile_poster": "/media/banners/QRY168_mobile.webp",  
    "banner_desktop_url": "/media/banners/QRY168_desktop.webp",  
    "banner_mobile_url": "/media/banners/QRY168_mobile.webp",  
    "movie_page_url": "/movie/video/QRY168.mp4",  
    "is_hero_banner": true,  
    "description": "История становления культового злодея",  
    "quality": "480p",  
    "duration": "1 ч 56 мин"  
  }  
]  
```  
  
### 5.2. Плитки каталога категорий (Верхние чипсы / табы)  
- **Запрос:** `GET /api/catalog/categories`  
- **Назначение:** Горизонтальный список категорий (фильтрует категории без фильмов; исключает категорию «Новое и популярное»).  
- **Пример ответа:**  
```json  
[  
  {  
    "id": 1,  
    "title": "Фильмы",  
    "name": "Фильмы",  
    "slug": "movies",  
    "icon_path": null,  
    "icon_url": "../IMAGES/icons/test-icon.svg"  
  },  
  {  
    "id": 4,  
    "title": "Боевики",  
    "name": "Боевики",  
    "slug": "action",  
    "icon_path": null,  
    "icon_url": "../IMAGES/icons/test-icon.svg"  
  }  
]  
```  
  
### 5.3. Секция «Новое и популярное»  
- **Запрос:** `GET /api/movies?is_popular=true&limit=20`  
- **Назначение:** Горизонтальная лента фильмов со статусом «Новое и популярное».  
- **Пример ответа:**  
```json  
[  
  {  
    "id": 4,  
    "pnr": "KVLXGR",  
    "title": "Наполеон",  
    "poster_url": "/media/posters/KVLXGR_poster.webp",  
    "quality": "480p",  
    "duration": "2 ч 29 мин",  
    "movie_page_url": "/movie/video/KVLXGR.mp4",  
    "banner": "/media/banners/KVLXGR_desktop.webp",  
    "mobile_poster": "/media/banners/KVLXGR_mobile.webp",  
    "category_ids": [1, 3, 4, 6],  
    "is_hero_banner": true,  
    "is_new_and_popular": true  
  }  
]  
```  
  
### 5.4. Ленты категорий с фильмами (Infinite Scroll / Пагинация)  
- **Запрос:** `GET /api/categories?offset=0&limit=10`  
- **Назначение:** Формирует вертикальный список категорий, в каждой из которых вложен массив фильмов `movies`.  
- **Пример ответа:**  
```json  
[  
  {  
    "id": 4,  
    "title": "Боевики",  
    "slug": "action",  
    "icon_url": "../IMAGES/icons/test-icon.svg",  
    "movies": [  
      {  
        "id": 4,  
        "pnr": "KVLXGR",  
        "title": "Наполеон",  
        "poster_url": "/media/posters/KVLXGR_poster.webp",  
        "quality": "480p",  
        "duration": "2 ч 29 мин",  
        "movie_page_url": "/movie/video/KVLXGR.mp4"  
      }  
    ]  
  }  
]  
```  
  
### 5.5. Детальная карточка фильма  
- **Запрос:** `GET /api/movies/{PNR}` (например: `GET /api/movies/KVLXGR`)  
- **Назначение:** Экран подробной информации о фильме перед запуском плеера.  
- **Пример ответа:**  
```json  
{  
  "id": 4,  
  "pnr": "KVLXGR",  
  "title": "Наполеон",  
  "description": "Историческая драма о восхождении полководца.",  
  "duration": "2 ч 29 мин",  
  "quality": "480p",  
  "poster_url": "/media/posters/KVLXGR_poster.webp",  
  "banner": "/media/banners/KVLXGR_desktop.webp",  
  "mobile_poster": "/media/banners/KVLXGR_mobile.webp",  
  "movie_page_url": "/movie/video/KVLXGR.mp4",  
  "trailer": null,  
  "logo_url": null,  
  "is_hero_banner": true,  
  "is_new_and_popular": true,  
  "category_ids": [1, 3, 4, 6],  
  "category_names": ["Фильмы", "Мультфильмы", "Боевики", "Драмы"]  
}  
```  
  
---  
  
## 6. Пример реализации на Android (Kotlin / Retrofit / ExoPlayer)  
  
### 6.1. DTO Модели (Kotlin)  
```kotlin  
package com.example.bochflix.data.model  
  
import com.google.gson.annotations.SerializedName  
  
data class MovieDto(  
    @SerializedName("id") val id: Int,  
    @SerializedName("pnr") val pnr: String,  
    @SerializedName("title") val title: String,  
    @SerializedName("description") val description: String?,  
    @SerializedName("duration") val duration: String,  
    @SerializedName("quality") val quality: String,  
    @SerializedName("poster_url") val posterUrl: String,  
    @SerializedName("banner") val banner: String?,  
    @SerializedName("mobile_poster") val mobilePoster: String?,  
    @SerializedName("movie_page_url") val moviePageUrl: String,  
    @SerializedName("trailer") val trailer: String?,  
    @SerializedName("is_hero_banner") val isHeroBanner: Boolean = false,  
    @SerializedName("is_new_and_popular") val isNewAndPopular: Boolean = false,  
    @SerializedName("category_ids") val categoryIds: List<Int> = emptyList()  
) {  
    fun getFullVideoUrl(baseUrl: String): String =   
        baseUrl.trimEnd('/') + "/" + moviePageUrl.trimStart('/')  
  
    fun getFullPosterUrl(baseUrl: String): String =   
        baseUrl.trimEnd('/') + "/" + posterUrl.trimStart('/')  
}  
  
data class CategoryDto(  
    @SerializedName("id") val id: Int,  
    @SerializedName("title") val title: String,  
    @SerializedName("slug") val slug: String?,  
    @SerializedName("icon_url") val iconUrl: String?  
)  
  
data class CategoryWithMoviesDto(  
    @SerializedName("id") val id: Int,  
    @SerializedName("title") val title: String,  
    @SerializedName("slug") val slug: String,  
    @SerializedName("icon_url") val iconUrl: String?,  
    @SerializedName("movies") val movies: List<MovieDto> = emptyList()  
)  
```  
  
### 6.2. Retrofit API Сервис  
```kotlin  
package com.example.bochflix.data.api  
  
import com.example.bochflix.data.model.CategoryDto  
import com.example.bochflix.data.model.CategoryWithMoviesDto  
import com.example.bochflix.data.model.MovieDto  
import retrofit2.http.GET  
import retrofit2.http.Path  
import retrofit2.http.Query  
  
interface BochflixApiService {  
    @GET("api/banners")  
    suspend fun getBanners(@Query("limit") limit: Int = 10): List<MovieDto>  
  
    @GET("api/catalog/categories")  
    suspend fun getCatalogCategories(): List<CategoryDto>  
  
    @GET("api/movies")  
    suspend fun getNewAndPopular(  
        @Query("is_popular") isPopular: Boolean = true,  
        @Query("limit") limit: Int = 20  
    ): List<MovieDto>  
  
    @GET("api/categories")  
    suspend fun getCategoriesWithMovies(  
        @Query("offset") offset: Int = 0,  
        @Query("limit") limit: Int = 10  
    ): List<CategoryWithMoviesDto>  
  
    @GET("api/movies/{pnr}")  
    suspend fun getMovieByPnr(@Path("pnr") pnr: String): MovieDto  
}  
```  
  
### 6.3. Воспроизведение видео в ExoPlayer (Media3)  
FastAPI поддерживает byte-range, поэтому перемотка работает из коробки:  
```kotlin  
val baseUrl = "http://10.0.2.2:8000" // или IP компьютера в локальной сети  
val videoFullUrl = movie.getFullVideoUrl(baseUrl)  
  
val player = ExoPlayer.Builder(context).build().apply {  
    val mediaItem = MediaItem.fromUri(Uri.parse(videoFullUrl))  
    setMediaItem(mediaItem)  
    prepare()  
    playWhenReady = true  
}  
```  
  
---  
  
## 7. Управление медиатекой и добавление новых фильмов  
  
Для добавления фильмов в БД используйте интерактивный CLI-мастер:  
```bash  
python manage_db.py  
```  
Шаги мастера:  
1. Автоматически генерирует уникальный 6-значный `PNR` (например, `KVLXGR`).  
2. Запрашивает путь к исходному `.mp4` файлу на диске.  
3. Автоматически считывает метаданные контейнера MP4 (хронометраж и разрешение) без внешних библиотек.  
4. Перемещает видеофайл в `media/video/<PNR>.mp4`.  
5. Позволяет выбрать категории (ввод ID через запятую: `1, 4`) или создать новую.  
6. Выставляет флаги показа в слайдере (`is_hero_banner`) и «Новое и популярное» (`is_new_and_popular`).  
  
---  
  
## 8. Чек-лист решения типичных проблем (Troubleshooting)  
  
1. **Ошибка `java.net.ConnectException: Failed to connect to /127.0.0.1:8000` в Android:**  
   - *Решение:* Замените `127.0.0.1` на `10.0.2.2` (для эмулятора Android Studio) или на локальный IP компьютера (для реального телефона).  
  
2. **Ошибка `CLEARTEXT communication to ... not permitted by network security policy`:**  
   - *Решение:* Добавьте `android:usesCleartextTraffic="true"` в `<application>` в `AndroidManifest.xml`.  
  
3. **Порт 8000 уже занят другим процессом:**  
   - *Решение:* Запустите `./stop_servers.sh` или выполните: `fuser -k 8000/tcp` (Linux) / `lsof -ti :8000 | xargs kill -9` (macOS).  
  
4. **Видеофайл долго стартует в плеере:**  
   - *Решение:* Заголовочный atom `moov` находится в конце файла. Запустите `ffmpeg -i input.mp4 -movflags +faststart output.mp4` для переноса заголовков в начало файла.  
  
5. **Изображения не загружаются в Glide/Coil:**  
   - *Решение:* Проверьте, что в URL постера добавляется базовый префикс `http://10.0.2.2:8000` перед `/media/posters/...`.  
