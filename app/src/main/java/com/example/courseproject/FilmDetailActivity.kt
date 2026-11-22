package com.example.courseproject

import android.content.Intent
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import androidx.appcompat.app.AppCompatActivity
import coil.load

class FilmDetailActivity : AppCompatActivity() {
    companion object { const val EXTRA_FILM = "film" }
    private var film: Film? = null
    private lateinit var titleText: android.widget.TextView
    private lateinit var details: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        film = intent.readFilm() ?: run { finish(); return }
        showFilm(film!!)
        val selected = film!!
        FilmRepository.loadFilm(this, selected.id, selected) { refreshed ->
            if (!isFinishing && !isDestroyed) {
                film = refreshed
                showFilm(refreshed)
            }
        }
    }

    private fun showFilm(value: Film) {
        val scroll = ScrollView(this).apply { clipToPadding = false }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(BochkinoColors.background)
            setPadding(0, 0, 0, dp(26))
        }
        val hero = FrameLayout(this).apply { clipToOutline = true }
        val image = ImageView(this).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP
            if (value.posterUrl.startsWith("http")) load(value.posterUrl)
            else value.posterResource(this@FilmDetailActivity).takeIf { it != 0 }?.let(::setImageResource)
        }
        hero.addView(image, FrameLayout.LayoutParams(-1, -1))
        hero.addView(View(this).apply { setBackgroundColor(0x90000000.toInt()) }, FrameLayout.LayoutParams(-1, -1))
        val topShade = View(this).apply {
            background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(0xA8000000.toInt(), 0x00000000))
        }
        hero.addView(topShade, FrameLayout.LayoutParams(-1, dp(100), Gravity.TOP))
        titleText = label(value.title, 30f, BochkinoColors.white, bold = true)
        val heroWords = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.BOTTOM
            setPadding(dp(22), dp(12), dp(22), dp(22))
            addView(label("BOCHKINO ORIGINAL", 10f, BochkinoColors.white, bold = true).apply { letterSpacing = .13f })
            addView(titleText, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(5) })
        }
        hero.addView(heroWords, FrameLayout.LayoutParams(-1, -1))
        val back = android.widget.TextView(this).apply {
            text = "‹"
            textSize = 34f
            gravity = Gravity.CENTER
            setTextColor(BochkinoColors.white)
            background = GradientDrawable().apply {
                setColor(0x66000000)
                shape = GradientDrawable.OVAL
            }
            contentDescription = "Назад"
            setOnClickListener { finish() }
        }
        hero.addView(back, FrameLayout.LayoutParams(dp(44), dp(44), Gravity.TOP or Gravity.START).apply {
            setMargins(dp(16), dp(14), 0, 0)
        })
        content.addView(hero, LinearLayout.LayoutParams(-1, dp(335)))

        details = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(19), dp(22), 0)
        }
        content.addView(details)
        scroll.addView(content)
        installScreen(scroll)
        fillDetails(value)
    }

    private fun fillDetails(value: Film) {
        if (!::details.isInitialized) return
        details.removeAllViews()
        details.addView(label("${value.year}   ·   ${value.genre}   ·   ${value.duration}", 13f, BochkinoColors.muted))
        details.addView(label("★  ${"%.1f".format(java.util.Locale.US, value.rating)}  ·  Bochkino", 14f, BochkinoColors.green, bold = true).apply {
            setPadding(0, dp(9), 0, dp(17))
        })
        details.addView(primaryButton("▶    Смотреть") {
            startActivity(Intent(this, PlayerActivity::class.java).putExtra(EXTRA_FILM, value))
        }, LinearLayout.LayoutParams(-1, dp(52)))
        details.addView(label("О фильме", 19f, BochkinoColors.white, bold = true).apply {
            setPadding(0, dp(23), 0, dp(7))
        })
        details.addView(label(value.description, 15f, 0xFFE1E1E1.toInt()).apply {
            setLineSpacing(dp(3).toFloat(), 1f)
        })
        details.addView(label("Видео и права", 17f, BochkinoColors.white, bold = true).apply {
            setPadding(0, dp(20), 0, dp(5))
        })
        details.addView(label("${value.creator} · ${value.license}", 12f, BochkinoColors.muted))
        details.addView(label("Открыть источник ↗", 12f, BochkinoColors.white).apply {
            setPadding(0, dp(7), 0, 0)
            setOnClickListener {
                runCatching { startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(value.sourceUrl))) }
            }
        })
    }
}

internal fun Intent.readFilm(): Film? = if (Build.VERSION.SDK_INT >= 33) {
    getSerializableExtra(FilmDetailActivity.EXTRA_FILM, Film::class.java)
} else {
    @Suppress("DEPRECATION")
    getSerializableExtra(FilmDetailActivity.EXTRA_FILM) as? Film
}
