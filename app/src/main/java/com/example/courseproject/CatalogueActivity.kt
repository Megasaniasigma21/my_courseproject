package com.example.courseproject

import android.content.Intent
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import coil.load
import com.google.android.material.snackbar.Snackbar

class CatalogueActivity : AppCompatActivity() {
    private lateinit var page: LinearLayout
    private lateinit var search: android.widget.EditText
    private lateinit var hero: FrameLayout
    private lateinit var filmsList: LinearLayout
    private lateinit var status: TextView
    private lateinit var retry: com.google.android.material.button.MaterialButton
    private var allFilms: List<Film> = emptyList()
    private var request: retrofit2.Call<List<FilmDto>>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!SessionManager.isSignedIn(this)) {
            startActivity(Intent(this, MainActivity::class.java))
            finish()
            return
        }
        page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(BochkinoColors.background)
        }
        page.addView(buildHeader(), LinearLayout.LayoutParams(-1, dp(62)))
        val scroll = ScrollView(this).apply { clipToPadding = false }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(8), dp(18), dp(24))
        }
        content.addView(label("Добро пожаловать, ${SessionManager.name(this)}", 14f, BochkinoColors.muted).apply {
            setPadding(0, dp(6), 0, dp(10))
        })
        search = inputField("Поиск по каталогу", android.text.InputType.TYPE_CLASS_TEXT).apply {
            setSingleLine()
            imeOptions = android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH
            contentDescription = "Поиск по каталогу"
        }
        content.addView(search, LinearLayout.LayoutParams(-1, dp(50)).apply { bottomMargin = dp(16) })
        status = label("", 13f, BochkinoColors.muted).apply { visibility = View.GONE }
        content.addView(status, LinearLayout.LayoutParams(-1, -2))
        retry = secondaryButton("Повторить загрузку") { refreshCatalog() }.apply { visibility = View.GONE }
        content.addView(retry, LinearLayout.LayoutParams(-1, dp(44)))

        content.addView(label("Рекомендуем", 21f, BochkinoColors.white, bold = true).apply {
            setPadding(0, dp(2), 0, dp(12))
        })
        hero = FrameLayout(this).apply {
            background = roundedBackground(BochkinoColors.surfaceRaised, 12)
            clipToOutline = true
        }
        content.addView(hero, LinearLayout.LayoutParams(-1, dp(256)).apply { bottomMargin = dp(22) })
        content.addView(label("Каталог", 21f, BochkinoColors.white, bold = true).apply {
            setPadding(0, 0, 0, dp(12))
        })
        filmsList = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        content.addView(filmsList)
        scroll.addView(content)
        page.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        installScreen(page)

        search.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = renderCatalog()
            override fun afterTextChanged(s: Editable?) = Unit
        })
        refreshCatalog()
    }

    private fun buildHeader(): View = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(18), 0, dp(18), 0)
        addView(label("BOCHKINO", 22f, BochkinoColors.red, bold = true).apply { letterSpacing = .12f },
            LinearLayout.LayoutParams(0, -2, 1f))
        val profile = TextView(this@CatalogueActivity).apply {
            text = SessionManager.name(this@CatalogueActivity).take(1).uppercase()
            textSize = 15f
            gravity = Gravity.CENTER
            setTextColor(BochkinoColors.white)
            background = roundedBackground(BochkinoColors.red, 24)
            contentDescription = "Аккаунт"
            setOnClickListener {
                startActivity(Intent(this@CatalogueActivity, AccountActivity::class.java))
            }
        }
        addView(profile, LinearLayout.LayoutParams(dp(38), dp(38)))
    }

    private fun refreshCatalog() {
        retry.isEnabled = false
        request?.cancel()
        request = FilmRepository.loadFilms(this) { films, error ->
            if (isFinishing || isDestroyed) return@loadFilms
            allFilms = films
            renderCatalog()
            status.visibility = if (error == null) View.GONE else View.VISIBLE
            status.text = error.orEmpty()
            retry.visibility = if (error == null) View.GONE else View.VISIBLE
            retry.isEnabled = true
        }
    }

    private fun renderCatalog() {
        if (!::hero.isInitialized || !::filmsList.isInitialized) return
        val query = search.text?.toString()?.trim().orEmpty()
        val filtered = allFilms.filter { it.title.contains(query, ignoreCase = true) }
        hero.removeAllViews()
        if (query.isEmpty()) {
            hero.visibility = View.VISIBLE
            filtered.firstOrNull()?.let { film ->
                val poster = ImageView(this).apply {
                    scaleType = ImageView.ScaleType.CENTER_CROP
                    loadPoster(film, this)
                }
                hero.addView(poster, FrameLayout.LayoutParams(-1, -1))
                hero.addView(View(this).apply {
                    setBackgroundColor(0x85000000.toInt())
                }, FrameLayout.LayoutParams(-1, -1))
                val words = LinearLayout(this).apply {
                    orientation = LinearLayout.VERTICAL
                    gravity = Gravity.BOTTOM
                    setPadding(dp(18), dp(15), dp(18), dp(16))
                    addView(label("BOCHKINO ORIGINAL", 10f, BochkinoColors.white, bold = true).apply { letterSpacing = .12f })
                    addView(label(film.title, 24f, BochkinoColors.white, bold = true).apply {
                        setPadding(0, dp(5), 0, dp(3))
                    })
                    addView(label("${film.year}   ·   ${film.genre}", 12f, BochkinoColors.white))
                    addView(primaryButton("▶  Смотреть") { openFilm(film) },
                        LinearLayout.LayoutParams(-1, dp(46)).apply { topMargin = dp(12) })
                }
                hero.addView(words, FrameLayout.LayoutParams(-1, -1))
            }
        } else hero.visibility = View.GONE

        filmsList.removeAllViews()
        if (filtered.isEmpty()) {
            filmsList.addView(label(if (allFilms.isEmpty()) "Каталог пока пуст." else "Ничего не найдено. Попробуй другое название.",
                14f, BochkinoColors.muted).apply { setPadding(dp(4), dp(18), dp(4), dp(24)) })
            return
        }
        filtered.forEachIndexed { index, film ->
            filmsList.addView(filmCard(film), LinearLayout.LayoutParams(-1, dp(156)).apply {
                bottomMargin = if (index == filtered.lastIndex) 0 else dp(12)
            })
        }
    }

    private fun filmCard(film: Film): View {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(9), dp(9), dp(10), dp(9))
            background = roundedBackground(BochkinoColors.surface, 10)
            isClickable = true
            isFocusable = true
            setOnClickListener { openFilm(film) }
        }
        val poster = ImageView(this).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP
            background = roundedBackground(BochkinoColors.surfaceRaised, 7)
            clipToOutline = true
            loadPoster(film, this)
            contentDescription = "Постер: ${film.title}"
        }
        card.addView(poster, LinearLayout.LayoutParams(dp(98), -1))
        val info = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(13), 0, 0, 0)
        }
        info.addView(label(film.title, 16f, BochkinoColors.white, bold = true))
        info.addView(label("${film.year}  ·  ${film.genre}", 11f, BochkinoColors.muted).apply {
            setPadding(0, dp(5), 0, dp(5))
        })
        info.addView(label("★  ${"%.1f".format(java.util.Locale.US, film.rating)}     ${film.duration}", 12f, BochkinoColors.green, bold = true))
        info.addView(label(film.description, 11f, BochkinoColors.muted).apply {
            maxLines = 3
            ellipsize = android.text.TextUtils.TruncateAt.END
            setPadding(0, dp(6), 0, 0)
        })
        card.addView(info, LinearLayout.LayoutParams(0, -1, 1f))
        return card
    }

    private fun loadPoster(film: Film, image: ImageView) {
        if (film.posterUrl.startsWith("http")) image.load(film.posterUrl)
        else film.posterResource(this).takeIf { it != 0 }?.let(image::setImageResource)
    }

    private fun openFilm(film: Film) {
        startActivity(Intent(this, FilmDetailActivity::class.java).putExtra(FilmDetailActivity.EXTRA_FILM, film))
    }

    private fun secondaryButton(text: String, action: () -> Unit) = com.google.android.material.button.MaterialButton(this).apply {
        this.text = text
        isAllCaps = false
        setTextColor(BochkinoColors.white)
        backgroundTintList = android.content.res.ColorStateList.valueOf(BochkinoColors.surfaceRaised)
        cornerRadius = dp(6)
        setOnClickListener { action() }
    }

    private fun roundedBackground(color: Int, radius: Int) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radius).toFloat()
    }

    override fun onDestroy() {
        request?.cancel()
        super.onDestroy()
    }
}
