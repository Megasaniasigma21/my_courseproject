package com.example.courseproject

import android.content.pm.ActivityInfo
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.google.android.material.button.MaterialButton

class PlayerActivity : AppCompatActivity() {
    private var player: ExoPlayer? = null
    private lateinit var playerView: PlayerView
    private lateinit var retryButton: MaterialButton
    private lateinit var film: Film

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        film = intent.readFilm() ?: run { finish(); return }
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }

        val frame = FrameLayout(this).apply { setBackgroundColor(android.graphics.Color.BLACK) }
        playerView = PlayerView(this).apply {
            useController = true
            controllerAutoShow = true
            keepScreenOn = true
            contentDescription = "Видеоплеер: ${film.title}"
        }
        frame.addView(playerView, FrameLayout.LayoutParams(-1, -1))
        val back = MaterialButton(this).apply {
            text = "‹  Назад"
            isAllCaps = false
            setTextColor(BochkinoColors.white)
            backgroundTintList = android.content.res.ColorStateList.valueOf(0xAA171717.toInt())
            cornerRadius = dp(7)
            setOnClickListener { finish() }
        }
        frame.addView(back, FrameLayout.LayoutParams(dp(108), dp(45), Gravity.TOP or Gravity.START).apply {
            setMargins(dp(18), dp(18), 0, 0)
        })
        retryButton = MaterialButton(this).apply {
            text = "Не удалось загрузить. Повторить"
            isAllCaps = false
            visibility = View.GONE
            setOnClickListener { startPlayback() }
        }
        frame.addView(retryButton, FrameLayout.LayoutParams(-2, dp(52), Gravity.CENTER))
        setContentView(frame)
        startPlayback()
    }

    private fun startPlayback() {
        retryButton.visibility = View.GONE
        player?.release()
        val media = ExoPlayer.Builder(this).build().also { instance ->
            player = instance
            playerView.player = instance
            instance.addListener(object : Player.Listener {
                override fun onPlayerError(error: PlaybackException) {
                    retryButton.visibility = View.VISIBLE
                }
            })
        }
        val uri = if (film.videoUrl.startsWith("http")) Uri.parse(film.videoUrl) else {
            val resource = film.videoResource(this)
            Uri.parse("android.resource://$packageName/$resource")
        }
        media.setMediaItem(MediaItem.fromUri(uri))
        media.prepare()
        media.playWhenReady = true
    }

    override fun onStop() {
        player?.pause()
        super.onStop()
    }

    override fun onDestroy() {
        playerView.player = null
        player?.release()
        player = null
        super.onDestroy()
    }
}
