package com.example.courseproject

import android.content.Intent
import android.os.Bundle
import android.util.Patterns
import android.view.Gravity
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {
    private val authExecutor = Executors.newSingleThreadExecutor()
    private lateinit var emailInput: EditText
    private lateinit var passwordInput: EditText
    private lateinit var signInButton: com.google.android.material.button.MaterialButton

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SessionManager.clearLegacyStorage(this)
        if (SessionManager.isSignedIn(this)) {
            openCatalogue()
            return
        }

        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(26), dp(30), dp(26), dp(24))
            setBackgroundColor(BochkinoColors.background)
        }
        val scroll = ScrollView(this).apply { isFillViewport = true }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
        }
        content.addView(label("BOCHKINO", 34f, BochkinoColors.red, bold = true).apply {
            letterSpacing = .12f
        })
        content.addView(label("Смотри хорошее кино", 26f, BochkinoColors.white, bold = true).apply {
            setPadding(0, dp(12), 0, dp(5))
        })
        content.addView(label("Войди, чтобы продолжить", 15f, BochkinoColors.muted))

        emailInput = inputField("Электронная почта", android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS).apply {
            setSingleLine()
            isSaveEnabled = false
            contentDescription = "Электронная почта"
        }
        content.addView(emailInput, LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(34) })

        passwordInput = inputField("Пароль", android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD).apply {
            setSingleLine()
            isSaveEnabled = false
            contentDescription = "Пароль"
        }
        content.addView(passwordInput, LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(12) })

        signInButton = primaryButton("Войти") { signIn() }
        content.addView(signInButton, LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(24) })
        content.addView(secondaryAction("Ещё нет аккаунта?  Зарегистрироваться") {
            startActivity(Intent(this, RegistrationActivity::class.java))
        }, LinearLayout.LayoutParams(-1, dp(54)).apply { topMargin = dp(8) })
        content.addView(label("Короткие истории о природе — уже внутри.", 13f, BochkinoColors.muted).apply {
            gravity = Gravity.CENTER
            setPadding(0, dp(38), 0, 0)
        })
        scroll.addView(content)
        page.addView(scroll, LinearLayout.LayoutParams(-1, -1))
        installScreen(page)
    }

    private fun signIn() {
        val email = emailInput.text.toString().trim().lowercase()
        val password = passwordInput.text.toString()
        if (email.isBlank() || password.isBlank()) {
            showMessage("Заполни электронную почту и пароль.")
            return
        }
        if (!Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
            showMessage("Проверь формат электронной почты.")
            return
        }

        signInButton.isEnabled = false
        signInButton.text = "Проверяем…"
        authExecutor.execute {
            val result = runCatching { Accounts.login(email, password) }
            runOnUiThread {
                signInButton.isEnabled = true
                signInButton.text = "Войти"
                if (result.isFailure) showMessage(result.exceptionOrNull()?.message ?: "Сервер недоступен")
                else {
                    SessionManager.signIn(this, result.getOrThrow())
                    passwordInput.text.clear()
                    openCatalogue()
                }
            }
        }
    }

    private fun openCatalogue() {
        startActivity(Intent(this, CatalogueActivity::class.java))
        finish()
    }

    private fun showMessage(message: String) {
        MaterialAlertDialogBuilder(this).setMessage(message).setPositiveButton("Понятно", null).show()
    }

    override fun onDestroy() {
        authExecutor.shutdown()
        super.onDestroy()
    }
}

internal object SessionManager {
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
