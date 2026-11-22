package com.example.courseproject

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.Call
import org.json.JSONObject

data class User(val id: Long, val name: String, val email: String)
internal data class Credentials(val email: String, val password: String)
internal data class NewAccount(val name: String, val email: String, val password: String)
internal data class LoginResult(val token: String, val user: User)
internal interface AccountApi {
    @POST("auth/login") fun login(@Body data: Credentials): Call<LoginResult>
    @POST("auth/register") fun register(@Body data: NewAccount): Call<Map<String, String>>
    @POST("auth/logout") fun logout(@Header("Authorization") token: String): Call<Void>
}
internal object Accounts {
    private val api: AccountApi by lazy {
        Retrofit.Builder().baseUrl(BuildConfig.BOCHKINO_API_BASE_URL.trim().trimEnd('/') + "/")
            .addConverterFactory(GsonConverterFactory.create()).build().create(AccountApi::class.java)
    }
    fun login(email: String, password: String): LoginResult {
        val response = api.login(Credentials(email, password)).execute()
        if (!response.isSuccessful) throw IllegalStateException(message(response.errorBody()?.string()))
        return response.body() ?: error("Сервер вернул пустой ответ")
    }
    fun register(name: String, email: String, password: String) {
        val response = api.register(NewAccount(name, email, password)).execute()
        if (!response.isSuccessful) throw IllegalStateException(message(response.errorBody()?.string()))
    }
    fun logout(token: String) { runCatching { api.logout("Bearer $token").execute() } }
    private fun message(body: String?): String = runCatching {
        JSONObject(body.orEmpty()).optString("detail").takeIf { it.isNotBlank() } ?: "Ошибка запроса"
    }.getOrDefault("Ошибка запроса к серверу")
}
