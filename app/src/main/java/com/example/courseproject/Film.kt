package com.example.courseproject

import android.content.Context
import com.google.gson.annotations.SerializedName
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
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

internal interface BochkinoApi {
    @GET("films") fun getFilms(): Call<List<FilmDto>>
    @GET("films/{id}") fun getFilm(@Path("id") id: Int): Call<FilmDto>
}

internal object FilmRepository {
    @Volatile private var configuredUrl: String? = null
    @Volatile private var api: BochkinoApi? = null
    @Volatile var currentFilms: List<Film> = emptyList()
        private set

    fun localFilms(context: Context): List<Film> = currentFilms

    fun loadFilms(context: Context, callback: (List<Film>, String?) -> Unit): Call<List<FilmDto>>? {
        val service = service()
        if (service == null) {
            callback(emptyList(), "Адрес сервера не настроен.")
            return null
        }
        return service.getFilms().also { call ->
            call.enqueue(object : Callback<List<FilmDto>> {
                override fun onResponse(call: Call<List<FilmDto>>, response: Response<List<FilmDto>>) {
                    if (response.isSuccessful && response.body() != null) {
                        currentFilms = response.body()!!.map(FilmDto::toFilm)
                        callback(currentFilms, null)
                    } else callback(currentFilms, "Не удалось загрузить каталог.")
                }
                override fun onFailure(call: Call<List<FilmDto>>, error: Throwable) {
                    if (!call.isCanceled) callback(currentFilms, "Сервер недоступен. Проверьте подключение.")
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
