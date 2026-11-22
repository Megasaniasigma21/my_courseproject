from pathlib import Path
import re
root = Path(r'D:/My_corseproject')
stage = Path('integration-staging/android-update')
source = root / 'app/src/main/java/com/example/courseproject'

def save(name, text):
    (stage/name).write_text(text, encoding='utf-8')

save('UserDatabase.kt', '''package com.example.courseproject

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
''')
main = (source/'MainActivity.kt').read_text(encoding='utf-8')
main = main.replace('val user = runCatching { UserDatabase(this).use { it.verifyPassword(email, password) } }.getOrNull()', 'val result = runCatching { Accounts.login(email, password) }')
main = main.replace('if (user == null) showMessage("Аккаунт не найден или пароль неверный.")', 'if (result.isFailure) showMessage(result.exceptionOrNull()?.message ?: "Сервер недоступен")')
main = main.replace('SessionManager.signIn(this, user.email, user.name)', 'SessionManager.signIn(this, result.getOrThrow())\n                    passwordInput.text.clear()')
main = main.replace('super.onCreate(savedInstanceState)', '''super.onCreate(savedInstanceState)
        SessionManager.clearLegacyStorage(this)''', 1)
main = main[:main.index('internal object SessionManager')] + '''internal object SessionManager {
    @Volatile private var session: LoginResult? = null
    fun isSignedIn(context: android.content.Context) = session != null
    fun email(context: android.content.Context) = session?.user?.email.orEmpty()
    fun name(context: android.content.Context) = session?.user?.name.orEmpty()
    fun signIn(context: android.content.Context, result: LoginResult) { session = result }
    fun signOut(context: android.content.Context) {
        val token = session?.token
        session = null
        if (token != null) Thread { Accounts.logout(token) }.start()
    }
    fun clearLegacyStorage(context: android.content.Context) {
        context.deleteDatabase("users.db")
        context.getSharedPreferences("bochkino_session", 0).edit().clear().apply()
        context.getSharedPreferences("bochkino_avatars", 0).edit().clear().apply()
        val avatars = java.io.File(context.filesDir, "avatars")
        avatars.listFiles()?.filter { it.isFile }?.forEach { it.delete() }
    }
}
'''
save('MainActivity.kt', main)
reg = (source/'RegistrationActivity.kt').read_text(encoding='utf-8').replace('Аккаунт хранится только на этом устройстве.', 'Аккаунт хранится на сервере.').replace('val result = runCatching { UserDatabase(this).use { it.addUser(name, email, password) } }.getOrDefault(-1L)', 'val result = runCatching { Accounts.register(name, email, password) }').replace('if (result > 0)', 'if (result.isSuccess)').replace('} else showMessage("Этот адрес уже зарегистрирован. Попробуй войти.")', '} else showMessage(result.exceptionOrNull()?.message ?: "Сервер недоступен")')
save('RegistrationActivity.kt', reg)
save('AccountActivity.kt', '''package com.example.courseproject

import android.content.Intent
import android.os.Bundle
import android.widget.LinearLayout
import androidx.appcompat.app.AppCompatActivity

class AccountActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!SessionManager.isSignedIn(this)) {
            startActivity(Intent(this, MainActivity::class.java))
            finish()
            return
        }
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(40), dp(24), dp(24))
            setBackgroundColor(BochkinoColors.background)
        }
        page.addView(secondaryAction("‹ Назад") { finish() })
        page.addView(label("Аккаунт", 26f, BochkinoColors.white, bold = true))
        page.addView(label(SessionManager.name(this), 22f, BochkinoColors.white))
        page.addView(label(SessionManager.email(this), 16f, BochkinoColors.muted))
        page.addView(primaryButton("Выйти из аккаунта") {
            SessionManager.signOut(this)
            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
            finish()
        })
        installScreen(page)
    }
}
''')
props = (root/'gradle.properties').read_text(encoding='utf-8').replace('bochkinoApiBaseUrl=http://192.168.68.105:8000/api/', 'bochkinoApiBaseUrl=http://10.0.2.2:8000/api/')
save('gradle.properties', props)
film = (source/'Film.kt').read_text(encoding='utf-8').replace('import com.google.gson.Gson\n','').replace('import com.google.gson.reflect.TypeToken\n','').replace('    private val gson = Gson()\n','')
save('Film.kt', film)
manifest = (root/'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8').replace('android:allowBackup="true"', 'android:allowBackup="false"')
save('AndroidManifest.xml', manifest)
print('Prepared Android files:', ', '.join(p.name for p in stage.iterdir()))
