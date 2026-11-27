package com.example.courseproject

import android.content.Context
import com.google.gson.annotations.SerializedName
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Query
import retrofit2.http.Path
import java.io.Serializable

data class Film(
    val id: Int,
    val title: String,
    val description: String,
    val year: Int,
    val genre: String,
    val duration: String,
    val rating: Double,
    val posterUrl: String,
    val videoUrl: String,
    val creator: String,
    val license: String,
    val sourceUrl: String
) : Serializable {
    fun posterResource(context: Context): Int = if (posterUrl.startsWith("http")) 0 else
        context.resources.getIdentifier(posterUrl, "drawable", context.packageName)

    fun videoResource(context: Context): Int = if (videoUrl.startsWith("http")) 0 else
        context.resources.getIdentifier(videoUrl, "raw", context.packageName)
}

internal data class Episode(val film: Film, val season: Int?, val number: Int?) {
    val label: String get() = if (season != null && number != null) "Сезон $season, серия $number" else film.title
}

internal data class Series(val title: String, val episodes: List<Episode>)

private val episodeTitle = Regex("""^(.+?)\s*[-–—]\s*сезон\s+(\d+)\s*,\s*серия\s+(\d+)\s*$""", RegexOption.IGNORE_CASE)
private val episodeFile = Regex("""/([^/?#]+)_s(\d+)e(\d+)\.[^/?#]+(?:[?#].*)?$""", RegexOption.IGNORE_CASE)

internal fun groupSeries(films: List<Film>): List<Series> {
    val groups = linkedMapOf<String, MutableList<Episode>>()
    val titles = mutableMapOf<String, String>()
    for (film in films) {
        val titleMatch = episodeTitle.matchEntire(film.title)
        val fileMatch = episodeFile.find(film.videoUrl)
        val title = titleMatch?.groupValues?.get(1)?.trim() ?: film.title
        val key = when {
            fileMatch != null -> "file:" + fileMatch.groupValues[1].lowercase()
            titleMatch != null -> "title:" + title.lowercase()
            else -> "record:" + film.id
        }
        val numbers = titleMatch ?: fileMatch
        titles.putIfAbsent(key, title)
        groups.getOrPut(key) { mutableListOf() }.add(Episode(
            film, numbers?.groupValues?.get(2)?.toIntOrNull(), numbers?.groupValues?.get(3)?.toIntOrNull()
        ))
    }
    return groups.map { (key, episodes) ->
        Series(titles.getValue(key), episodes.sortedWith(compareBy({ it.season }, { it.number }, { it.film.id })))
    }
}

internal data class FilmDto(
    val id: Int,
    @SerializedName("title") val title: String,
    val description: String,
    val year: Int,
    val genre: String,
    val duration: String,
    val rating: Double,
    val posterUrl: String,
    val videoUrl: String,
    val creator: String,
    val license: String,
    val sourceUrl: String
) {
    fun toFilm() = Film(id, title, description, year, genre, duration, rating, posterUrl, videoUrl, creator, license, sourceUrl)
}

internal enum class CatalogueSection(val apiValue: String, val title: String, val menuId: Int) {
    FILMS("films", "Фильмы", 1),
    SERIES("series", "Сериалы", 2)
}

internal interface BochkinoApi {
    @GET("films") fun getFilms(@Query("section") section: String): Call<List<FilmDto>>
    @GET("films/{id}") fun getFilm(@Path("id") id: Int): Call<FilmDto>
}

internal object FilmRepository {
    @Volatile private var configuredUrl: String? = null
    @Volatile private var api: BochkinoApi? = null
    @Volatile var currentFilms: List<Film> = emptyList()
        private set

    fun localFilms(context: Context): List<Film> = currentFilms

    fun loadFilms(context: Context, section: CatalogueSection = CatalogueSection.FILMS, callback: (List<Film>, String?) -> Unit): Call<List<FilmDto>>? {
        val service = service()
        if (service == null) {
            callback(emptyList(), "Адрес сервера не настроен.")
            return null
        }
        val fallback = if (section == CatalogueSection.FILMS) currentFilms else emptyList()
        return service.getFilms(section.apiValue).also { call ->
            call.enqueue(object : Callback<List<FilmDto>> {
                override fun onResponse(call: Call<List<FilmDto>>, response: Response<List<FilmDto>>) {
                    if (call.isCanceled) return
                    if (response.isSuccessful && response.body() != null) {
                        val films = response.body()!!.map(FilmDto::toFilm)
                        if (section == CatalogueSection.FILMS) currentFilms = films
                        callback(films, null)
                    } else callback(fallback, "Не удалось загрузить каталог.")
                }
                override fun onFailure(call: Call<List<FilmDto>>, error: Throwable) {
                    if (!call.isCanceled) callback(fallback, "Сервер недоступен. Проверьте подключение.")
                }
            })
        }
    }

    fun loadFilm(context: Context, id: Int, fallback: Film, callback: (Film) -> Unit): Call<FilmDto>? {
        val service = service() ?: return null
        return service.getFilm(id).also { call ->
            call.enqueue(object : Callback<FilmDto> {
                override fun onResponse(call: Call<FilmDto>, response: Response<FilmDto>) {
                    callback(if (response.isSuccessful) response.body()?.toFilm() ?: fallback else fallback)
                }
                override fun onFailure(call: Call<FilmDto>, error: Throwable) = callback(fallback)
            })
        }
    }

    private fun service(): BochkinoApi? {
        val rawUrl = BuildConfig.BOCHKINO_API_BASE_URL.trim()
        if (rawUrl.isBlank()) return null
        val url = if (rawUrl.endsWith('/')) rawUrl else "$rawUrl/"
        if (configuredUrl == url) return api
        synchronized(this) {
            if (configuredUrl != url) {
                api = runCatching {
                    Retrofit.Builder().baseUrl(url)
                        .addConverterFactory(GsonConverterFactory.create())
                        .build().create(BochkinoApi::class.java)
                }.getOrNull()
                configuredUrl = url
            }
        }
        return api
    }
}
