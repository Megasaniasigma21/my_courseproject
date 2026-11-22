/**
 * ==============================================================================
 * BOCHFLIX — FRONTEND LOADER MODULE (frontend_loader.js)
 * ==============================================================================
 * 
 * Назначение:
 * 1. Асинхронно запрашивает данные с FastAPI бэкенда (баннеры, плитки каталога, фильмы).
 * 2. Рендерит адаптивный промо-слайдер баннеров (<section class="main__slider">).
 * 3. Рендерит плитки категорий каталога (<section class="main__catalog">)
 *    строго между баннерами и блоком "Новое и популярное".
 *    ИСКЛЮЧЕНИЕ: Категории "Новое" и "Популярное" в плитки НЕ выводятся.
 * 4. Заполняет блок "Новое и популярное" (<section class="main__new-popular">) фильмами.
 * 5. Динамически создает блоки <article class="main__other-article main__standart-card">
 *    внутри <section class="main__other"> для каждой пользовательской категории
 *    с их фильмами (Many-to-Many).
 * 6. Реализует плавную подгрузку порциями по 10 категорий (Lazy Loading / Infinite Scroll)
 *    через IntersectionObserver.
 */

// ==============================================================================
// 1. КОНФИГУРАЦИОННЫЕ КОНСТАНТЫ И СЕЛЕКТОРЫ КЛАССОВ
// ==============================================================================

const SELECTORS = {
    // Слайдер баннеров
    SLIDER_CONTAINER: '.main__slider',
    SLIDER_TRACK: '.main__slider-track',
    SLIDER_ITEM: '.main__slider-item',

    // Плитки каталога (между баннерами и Новым/Популярным)
    CATALOG_TRACK: '.main__catalog-track',

    // Блок "Новое и популярное"
    POPULAR_TRACK: '.main__new-popular .main__standart-card--track',

    // Секция пользовательских категорий
    OTHER_SECTION: '.main__other',

    // Базовые классы элементов
    CLASS_SLIDER_ITEM: 'main__slider-item',
    CLASS_CARD_ITEM: 'main__standart-card--item',
};

const API_CONFIG = {
    BASE_URL: 'http://127.0.0.1:8000',
    BANNERS_ENDPOINT: '/api/banners',
    CATALOG_CATEGORIES_ENDPOINT: '/api/catalog/categories',
    CATEGORIES_PAGINATED_ENDPOINT: '/api/categories',
    MOVIES_ENDPOINT: '/api/movies',
    POPULAR_ENDPOINT: '/api/movies?is_popular=true',
    REQUEST_TIMEOUT: 7000,
    CATEGORIES_BATCH_SIZE: 10,
    DEFAULT_CATEGORY_ICON: '../IMAGES/icons/test-icon.svg',
    DEFAULT_POSTER: '../IMAGES/error_items/error_items-img/bochflix-test-img-2.jpg',
    DEFAULT_BANNER: '../IMAGES/error_items/error_items-img/bochflix-test-img.png',
};

// ==============================================================================
// 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ==============================================================================

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Проверяет, является ли категория системной («Новое», «Популярное», «Новое и популярное»).
 */
function isPopularCategory(nameOrSlug) {
    if (!nameOrSlug) return false;
    const s = String(nameOrSlug).toLowerCase().trim();
    const banned = [
        'новое',
        'популярное',
        'новое и популярное',
        'новое & популярное',
        'new',
        'popular',
        'new-popular',
        'novoe',
        'populyarnoe'
    ];
    return banned.includes(s);
}

function getApiBaseUrl() {
    if (window.BOCHFLIX_API_URL) {
        return window.BOCHFLIX_API_URL.replace(/\/+$/, '');
    }
    if (window.location.protocol.startsWith('http')) {
        if (['8080', '80', '443', ''].includes(window.location.port)) {
            return '';
        }
        const hostname = window.location.hostname || '127.0.0.1';
        return `http://${hostname}:8000`;
    }
    return API_CONFIG.BASE_URL;
}

function resolveUrl(url) {
    if (!url) return '';
    if (/^(https?:)?\/\//i.test(url) || url.startsWith('data:') || url.startsWith('..')) {
        return url;
    }
    const cleanPath = url.startsWith('/') ? url : `/${url}`;
    const base = getApiBaseUrl();
    if (!base) {
        return cleanPath;
    }
    return `${base}${cleanPath}`;
}

async function apiFetch(endpoint) {
    const url = `${getApiBaseUrl()}${endpoint}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), API_CONFIG.REQUEST_TIMEOUT);

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            signal: controller.signal,
        });
        clearTimeout(timer);

        if (!response.ok) {
            // Запасной fallback на /api/v1/..., если /api/... недоступен
            if (response.status === 404 && endpoint.startsWith('/api/') && !endpoint.startsWith('/api/v1/')) {
                const fallbackEndpoint = endpoint.replace('/api/', '/api/v1/');
                return await apiFetch(fallbackEndpoint);
            }
            throw new Error(`HTTP Error ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (err) {
        clearTimeout(timer);
        console.warn(`[Bochflix Loader] Запрос к ${url} завершился с ошибкой:`, err.message);
        throw err;
    }
}

/**
 * Подключает плавный drag-скроллинг мышью и клавишами для динамически созданных треков.
 */
function enableTrackDrag(track) {
    if (!track || track.dataset.dragEnabled) return;
    track.dataset.dragEnabled = "true";
    track.setAttribute('tabindex', '0');

    let isDown = false;
    let startX = 0;
    let scrollLeft = 0;

    const setCardsDragging = (isDragging) => {
        const cards = track.querySelectorAll('.main__standart-card--item');
        cards.forEach((card) => {
            card.classList.toggle('is-dragging', isDragging);
        });
    };

    track.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        isDown = true;
        track.classList.add('active');
        startX = e.pageX - track.offsetLeft;
        scrollLeft = track.scrollLeft;
    });

    track.addEventListener('mousemove', (e) => {
        if (!isDown) return;
        e.preventDefault();
        setCardsDragging(true);
        const x = e.pageX - track.offsetLeft;
        const walk = (x - startX) * 1.5;
        track.scrollLeft = scrollLeft - walk;
    });

    const stopDragging = () => {
        if (!isDown) return;
        isDown = false;
        track.classList.remove('active');
        setCardsDragging(false);
    };

    track.addEventListener('mouseup', stopDragging);
    track.addEventListener('mouseleave', stopDragging);

    track.addEventListener('keydown', (e) => {
        const step = 220;
        if (e.key === 'ArrowRight') {
            e.preventDefault();
            track.scrollBy({ left: step, behavior: 'smooth' });
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            track.scrollBy({ left: -step, behavior: 'smooth' });
        }
    });
}

function injectLoaderStyles() {
    if (document.getElementById('bochflix-loader-styles')) return;

    const style = document.createElement('style');
    style.id = 'bochflix-loader-styles';
    style.textContent = `
        /* Карточки слайдера */
        .bochflix-slider-card {
            position: relative;
            display: block !important;
            overflow: hidden;
            text-decoration: none;
            border-radius: 15px;
            user-select: none;
            -webkit-user-drag: none;
            background: #000 !important;
        }

        .bochflix-slider-card picture,
        .bochflix-slider-card picture img,
        .bochflix-slider-img {
            display: block !important;
            width: 100% !important;
            height: 100% !important;
            object-fit: cover !important;
            border-radius: inherit;
            pointer-events: none;
            user-select: none;
            -webkit-user-drag: none;
        }

        /* Карточки фильмов в горизонтальных треках */
        .bochflix-card-item {
            position: relative;
            display: block !important;
            overflow: hidden;
            text-decoration: none;
            border-radius: 15px;
            user-select: none;
            -webkit-user-drag: none;
            transform: none !important;
            transition: none !important;
        }

        .bochflix-card-item:hover {
            transform: none !important;
            box-shadow: none !important;
        }

        .bochflix-card-poster {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: inherit;
            display: block;
            pointer-events: none;
            user-select: none;
            -webkit-user-drag: none;
            transform: none !important;
            transition: none !important;
        }

        .bochflix-card-item:hover .bochflix-card-poster {
            transform: none !important;
        }

        /* Sentinel для Lazy Loading */
        .main__other-sentinel {
            width: 100%;
            height: 40px;
            margin: 20px 0;
            display: flex;
            align-items: center;
            justify-content: center;
            color: rgba(255, 255, 255, 0.35);
            font-size: 0.9rem;
            pointer-events: none;
        }

        /* Плавное появление динамических секций категорий */
        .main__other-article {
            animation: fadeInArticle 0.3s ease-out forwards;
        }

        @keyframes fadeInArticle {
            from { opacity: 0; transform: translateY(10px); }
            to   { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(style);
}

// ==============================================================================
// 3. ПРОМО-СЛАЙДЕР БАННЕРОВ (<section class="main__slider">)
// ==============================================================================

function createSliderElement(banner) {
    const desktopUrl = resolveUrl(banner.banner_desktop_url);
    const mobileUrl = resolveUrl(banner.banner_mobile_url);
    const pageUrl = banner.movie_page_url || `/movie/${banner.pnr}`;

    const link = document.createElement('a');
    link.href = pageUrl;
    link.className = `${SELECTORS.CLASS_SLIDER_ITEM} bochflix-slider-card`;
    link.setAttribute('data-pnr', banner.pnr);
    link.setAttribute('title', banner.title);

    link.addEventListener('click', (e) => {
        const slider = link.closest(SELECTORS.SLIDER_CONTAINER);
        if (slider && slider.classList.contains('is-dragging')) {
            e.preventDefault();
            e.stopPropagation();
        }
    });

    link.innerHTML = `
        <picture>
            <source media="(max-width: 767px)" srcset="${escapeHtml(mobileUrl)}">
            <img class="bochflix-slider-img" 
                 src="${escapeHtml(desktopUrl)}" 
                 alt="${escapeHtml(banner.title)}" 
                 loading="eager"
                 onerror="this.onerror=null; this.src='${API_CONFIG.DEFAULT_BANNER}';">
        </picture>
    `;

    return link;
}

async function loadAndRenderBanners() {
    const sliderTrack = document.querySelector(SELECTORS.SLIDER_TRACK);
    if (!sliderTrack) return;

    try {
        const banners = await apiFetch(API_CONFIG.BANNERS_ENDPOINT);
        if (!Array.isArray(banners) || banners.length === 0) return;

        const newElements = banners.map(createSliderElement);
        sliderTrack.replaceChildren(...newElements);
        window.dispatchEvent(new Event('resize'));
        console.log(`[Bochflix Loader] Отрисовано баннеров в слайдере: ${newElements.length}`);
    } catch (err) {
        console.error('[Bochflix Loader] Ошибка при загрузке баннеров:', err);
    }
}

// ==============================================================================
// 4. ПЛИТКИ КАТАЛОГА КАТЕГОРИЙ (<section class="main__catalog">)
// ==============================================================================

/**
 * Создает DOM-элемент плитки категории:
 * <a href="#category-${cat.id}" class="main__catalog-item" data-id="${cat.id}">
 *   <img src="${cat.icon_url || '../IMAGES/icons/test-icon.svg'}" alt="${cat.title}" class="main__catalog-item--icon">
 *   <div class="catalog-item--text">${cat.title}</div>
 * </a>
 */
function createCatalogTileElement(cat) {
    const iconUrl = cat.icon_url ? resolveUrl(cat.icon_url) : API_CONFIG.DEFAULT_CATEGORY_ICON;
    const catTitle = cat.title || cat.name || 'Категория';

    const link = document.createElement('a');
    link.href = `#category-${cat.id}`;
    link.className = 'main__catalog-item';
    link.setAttribute('data-id', cat.id);
    link.setAttribute('title', catTitle);

    // Плавный скролл к секции выбранной категории
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetBlock = document.querySelector(`[data-category-id="${cat.id}"]`);
        if (targetBlock) {
            targetBlock.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });

    link.innerHTML = `
        <img src="${escapeHtml(iconUrl)}" 
             alt="${escapeHtml(catTitle)}" 
             class="main__catalog-item--icon"
             onerror="this.onerror=null; this.src='${API_CONFIG.DEFAULT_CATEGORY_ICON}';">
        <div class="catalog-item--text">${escapeHtml(catTitle)}</div>
    `;

    return link;
}

/**
 * Загружает категории и надежно рендерит их в 2 горизонтальных ряда (.main__catalog-row),
 * гарантируя соблюдение оригинальной верстки и стилей.
 * ИСКЛЮЧЕНИЕ: Категории 'Новое' и 'Популярное' исключаются!
 */
async function loadAndRenderCatalogTiles() {
    const catalogTrack = document.querySelector(SELECTORS.CATALOG_TRACK);
    if (!catalogTrack) return;

    try {
        const categories = await apiFetch(API_CONFIG.CATALOG_CATEGORIES_ENDPOINT);
        if (!Array.isArray(categories) || categories.length === 0) {
            console.info('[Bochflix Loader] Категории для каталога не найдены.');
            return;
        }

        // ВАЖНОЕ ИСКЛЮЧЕНИЕ: исключаем 'Новое', 'Популярное', 'Новое и популярное'
        const filtered = categories.filter(c => {
            const name = c.title || c.name || '';
            const slug = c.slug || '';
            return !isPopularCategory(name) && !isPopularCategory(slug);
        });

        if (filtered.length === 0) return;

        // Создаем элементы плиток
        const tileElements = filtered.map(createCatalogTileElement);

        // Раскладываем в 2 ряда (.main__catalog-row) согласно стилям style.css
        const row1 = document.createElement('div');
        row1.className = 'main__catalog-row';
        const row2 = document.createElement('div');
        row2.className = 'main__catalog-row';

        const half = Math.ceil(tileElements.length / 2);
        tileElements.forEach((el, index) => {
            if (index < half) {
                row1.appendChild(el);
            } else {
                row2.appendChild(el);
            }
        });

        catalogTrack.replaceChildren(row1, row2);
        console.log(`[Bochflix Loader] Успешно отрисовано ${tileElements.length} плиток каталога в 2 ряда.`);
    } catch (err) {
        console.error('[Bochflix Loader] Ошибка при загрузке плиток каталога:', err);
    }
}

// ==============================================================================
// 5. КАРТОЧКИ ФИЛЬМОВ ДЛЯ ГОРИЗОНТАЛЬНЫХ ТРЕКОВ
// ==============================================================================

function createMovieCardElement(movie, parentTrack) {
    const posterUrl = resolveUrl(movie.poster_url);
    const pageUrl = movie.movie_page_url || `/movie/${movie.pnr}`;

    const link = document.createElement('a');
    link.href = pageUrl;
    link.className = `${SELECTORS.CLASS_CARD_ITEM} bochflix-card-item`;
    link.setAttribute('data-pnr', movie.pnr);
    link.setAttribute('title', movie.title);

    link.addEventListener('click', (e) => {
        if (link.classList.contains('is-dragging') || (parentTrack && parentTrack.classList.contains('active'))) {
            e.preventDefault();
            e.stopPropagation();
        }
    });

    link.innerHTML = `
        <img class="bochflix-card-poster" 
             src="${escapeHtml(posterUrl)}" 
             alt="${escapeHtml(movie.title)}" 
             loading="lazy"
             onerror="this.onerror=null; this.src='${API_CONFIG.DEFAULT_POSTER}';">
    `;

    return link;
}

// ==============================================================================
// 6. СЕКЦИЯ "НОВОЕ И ПОПУЛЯРНОЕ" (<section class="main__new-popular">)
// ==============================================================================

async function loadAndRenderPopularMovies() {
    const popularTrack = document.querySelector(SELECTORS.POPULAR_TRACK);
    if (!popularTrack) return;

    try {
        let movies = [];
        try {
            movies = await apiFetch(API_CONFIG.POPULAR_ENDPOINT);
        } catch (e) {
            movies = [];
        }

        // Если с флагом is_popular фильмов пока нет, берем свежие из общего каталога
        if (!Array.isArray(movies) || movies.length === 0) {
            movies = await apiFetch(`${API_CONFIG.MOVIES_ENDPOINT}?limit=12`);
        }

        if (Array.isArray(movies) && movies.length > 0) {
            const cardElements = movies.map(movie => createMovieCardElement(movie, popularTrack));
            popularTrack.replaceChildren(...cardElements);
            enableTrackDrag(popularTrack);
            console.log(`[Bochflix Loader] Отрисовано фильмов в 'Новое и популярное': ${cardElements.length}`);
        }
    } catch (err) {
        console.error('[Bochflix Loader] Ошибка при загрузке секции Новое и популярное:', err);
    }
}

// ==============================================================================
// 7. ДИНАМИЧЕСКИЕ БЛОКИ КАТЕГОРИЙ (<section class="main__other">) + LAZY LOADING
// ==============================================================================

/**
 * Создает блок категории, в точности повторяющий оригинальную разметку тестовых категорий:
 * <article class="main__other-article main__standart-card category-block" data-category-id="${cat.id}">
 *   <div class="main__standart-card--title">${cat.title}</div>
 *   <div class="main__standart-card--track" tabindex="0">
 *     <!-- Карточки фильмов данной категории -->
 *   </div>
 * </article>
 */
function createCategoryArticleElement(cat) {
    const catTitle = cat.title || cat.name || 'Категория';

    const article = document.createElement('article');
    article.className = 'main__other-article main__standart-card category-block';
    article.setAttribute('data-category-id', cat.id);
    article.id = `category-${cat.id}`;

    const titleDiv = document.createElement('div');
    titleDiv.className = 'main__standart-card--title';
    titleDiv.textContent = catTitle;

    const trackDiv = document.createElement('div');
    trackDiv.className = 'main__standart-card--track';
    trackDiv.setAttribute('tabindex', '0');

    const movies = Array.isArray(cat.movies) ? cat.movies : [];
    if (movies.length > 0) {
        movies.forEach((movie) => {
            const card = createMovieCardElement(movie, trackDiv);
            trackDiv.appendChild(card);
        });
    } else {
        const emptyMsg = document.createElement('div');
        emptyMsg.className = 'main__standart-card--empty';
        emptyMsg.style.cssText = 'color: rgba(255,255,255,0.35); padding: 25px 20px; font-size: 0.95rem; font-style: italic;';
        emptyMsg.textContent = 'В этой категории пока нет добавленных фильмов';
        trackDiv.appendChild(emptyMsg);
    }

    // Подключаем drag-скроллинг мышью и клавиатурой
    enableTrackDrag(trackDiv);

    article.appendChild(titleDiv);
    article.appendChild(trackDiv);
    return article;
}

/**
 * Менеджер Infinite Scroll для динамических секций категорий в main__other.
 */
class InfiniteCategoriesLoader {
    constructor() {
        this.container = document.querySelector(SELECTORS.OTHER_SECTION);
        this.offset = 0;
        this.limit = API_CONFIG.CATEGORIES_BATCH_SIZE;
        this.isLoading = false;
        this.hasMore = true;
        this.sentinel = null;
        this.observer = null;
    }

    init() {
        if (!this.container) return;

        // Создаем невидимый элемент-триггер внизу контейнера
        this.sentinel = document.createElement('div');
        this.sentinel.className = 'main__other-sentinel';
        this.sentinel.textContent = '';
        this.container.appendChild(this.sentinel);

        // Настраиваем IntersectionObserver с упреждающим отступом 250px
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting && !this.isLoading && this.hasMore) {
                    this.loadNextBatch();
                }
            });
        }, {
            root: null,
            rootMargin: '250px 0px',
            threshold: 0.01,
        });

        this.observer.observe(this.sentinel);

        // Загружаем первую порцию (offset=0, limit=10)
        this.loadNextBatch();
    }

    async loadNextBatch() {
        if (this.isLoading || !this.hasMore) return;
        this.isLoading = true;

        try {
            const endpoint = `${API_CONFIG.CATEGORIES_PAGINATED_ENDPOINT}?offset=${this.offset}&limit=${this.limit}&exclude_popular=true`;
            const categories = await apiFetch(endpoint);

            if (!Array.isArray(categories) || categories.length === 0) {
                this.finishLoading();
                return;
            }

            // Фильтруем категории 'Новое' и 'Популярное'
            const validCategories = categories.filter(c => {
                const name = c.title || c.name || '';
                const slug = c.slug || '';
                return !isPopularCategory(name) && !isPopularCategory(slug);
            });

            validCategories.forEach((cat) => {
                const articleEl = createCategoryArticleElement(cat);
                this.container.insertBefore(articleEl, this.sentinel);
            });

            this.offset += categories.length;
            console.log(`[Bochflix Loader] Добавлено ${validCategories.length} категорий в main__other (offset: ${this.offset})`);

            // Если пришло меньше лимита, все категории в БД загружены
            if (categories.length < this.limit) {
                this.finishLoading();
            }
        } catch (err) {
            console.error('[Bochflix Loader] Ошибка Infinite Scroll категорий:', err);
            this.finishLoading();
        } finally {
            this.isLoading = false;
        }
    }

    finishLoading() {
        this.hasMore = false;
        if (this.observer) this.observer.disconnect();
        if (this.sentinel && this.sentinel.parentNode) this.sentinel.remove();
    }
}

// ==============================================================================
// 8. ИНИЦИАЛИЗАЦИЯ И ЭКСПОРТ
// ==============================================================================

async function initBochflixLoader() {
    injectLoaderStyles();

    // Запускаем загрузку баннеров, плиток каталога и популярного
    await Promise.allSettled([
        loadAndRenderBanners(),
        loadAndRenderCatalogTiles(),
        loadAndRenderPopularMovies(),
    ]);

    // Инициализируем Infinite Scroll для динамических секций категорий в main__other
    const infiniteLoader = new InfiniteCategoriesLoader();
    infiniteLoader.init();
    window.BochflixInfiniteCategories = infiniteLoader;
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBochflixLoader);
} else {
    initBochflixLoader();
}

// Экспорт в глобальный объект window
window.BochflixLoader = {
    init: initBochflixLoader,
    loadBanners: loadAndRenderBanners,
    loadCatalogTiles: loadAndRenderCatalogTiles,
    loadPopularMovies: loadAndRenderPopularMovies,
    CONFIG: API_CONFIG,
    SELECTORS: SELECTORS,
};
