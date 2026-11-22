package com.example.courseproject

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
