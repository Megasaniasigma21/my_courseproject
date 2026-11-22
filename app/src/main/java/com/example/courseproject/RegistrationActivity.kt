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

class RegistrationActivity : AppCompatActivity() {
    private val registerExecutor = Executors.newSingleThreadExecutor()
    private lateinit var nameInput: EditText
    private lateinit var emailInput: EditText
    private lateinit var passwordInput: EditText
    private lateinit var registerButton: com.google.android.material.button.MaterialButton

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val scroll = ScrollView(this).apply { isFillViewport = true }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(26), dp(30), dp(26), dp(30))
            setBackgroundColor(BochkinoColors.background)
        }
        content.addView(secondaryAction("‹  НАЗАД КО ВХОДУ") { finish() }.apply {
            gravity = Gravity.START
            setTextColor(BochkinoColors.muted)
        }, LinearLayout.LayoutParams(-1, dp(48)))
        content.addView(label("BOCHKINO", 34f, BochkinoColors.red, bold = true).apply { letterSpacing = .12f })
        content.addView(label("Создать аккаунт", 26f, BochkinoColors.white, bold = true).apply {
            setPadding(0, dp(14), 0, dp(5))
        })
        content.addView(label("Твой билет в мир коротких историй", 14f, BochkinoColors.muted))

        nameInput = inputField("Имя", android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PERSON_NAME).apply {
            setSingleLine()
            isSaveEnabled = false
            contentDescription = "Имя"
        }
        content.addView(nameInput, LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(30) })
        emailInput = inputField("Электронная почта", android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS).apply {
            setSingleLine()
            isSaveEnabled = false
            contentDescription = "Электронная почта"
        }
        content.addView(emailInput, LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(12) })
        passwordInput = inputField("Пароль (не менее 6 символов)", android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD).apply {
            setSingleLine()
            isSaveEnabled = false
            contentDescription = "Пароль"
        }
        content.addView(passwordInput, LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(12) })

        registerButton = primaryButton("Зарегистрироваться") { register() }
        content.addView(registerButton, LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(22) })
        content.addView(label("Аккаунт хранится на сервере.", 12f, BochkinoColors.muted).apply {
            gravity = Gravity.CENTER
            setPadding(0, dp(16), 0, 0)
        })
        scroll.addView(content)
        installScreen(scroll)
    }

    private fun register() {
        val name = nameInput.text.toString().trim()
        val email = emailInput.text.toString().trim().lowercase()
        val password = passwordInput.text.toString()
        when {
            name.isBlank() || email.isBlank() || password.isBlank() -> return showMessage("Заполни все поля.")
            !Patterns.EMAIL_ADDRESS.matcher(email).matches() -> return showMessage("Проверь формат электронной почты.")
            password.length < 6 -> return showMessage("Пароль должен содержать не менее 6 символов.")
        }

        registerButton.isEnabled = false
        registerButton.text = "Создаём аккаунт…"
        registerExecutor.execute {
            val result = runCatching { Accounts.register(name, email, password) }
            runOnUiThread {
                registerButton.isEnabled = true
                registerButton.text = "Зарегистрироваться"
                if (result.isSuccess) {
                    MaterialAlertDialogBuilder(this)
                        .setMessage("Аккаунт создан. Теперь войди в Bochkino.")
                        .setPositiveButton("Ко входу") { _, _ ->
                            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
                            finish()
                        }
                        .show()
                } else showMessage(result.exceptionOrNull()?.message ?: "Сервер недоступен")
            }
        }
    }

    private fun showMessage(message: String) {
        MaterialAlertDialogBuilder(this).setMessage(message).setPositiveButton("Понятно", null).show()
    }

    override fun onDestroy() {
        registerExecutor.shutdown()
        super.onDestroy()
    }
}
