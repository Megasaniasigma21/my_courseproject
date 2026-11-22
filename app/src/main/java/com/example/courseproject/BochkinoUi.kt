package com.example.courseproject

import  android.content.Context
import android.content.res.ColorStateList
import android.graphics.Rect
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.material.button.MaterialButton

internal object BochkinoColors {
    const val background = 0xFF101010.toInt()
    const val surface = 0xFF202020.toInt()
    const val surfaceRaised = 0xFF2A2A2A.toInt()
    const val red = 0xFFE50914.toInt()
    const val white = 0xFFFFFFFF.toInt()
    const val muted = 0xFFB3B3B3.toInt()
    const val green = 0xFF46D369.toInt()
}

internal fun Context.dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

internal fun AppCompatActivity.installScreen(root: View) {
    val left = root.paddingLeft
    val top = root.paddingTop
    val right = root.paddingRight
    val bottom = root.paddingBottom
    window.statusBarColor = BochkinoColors.background
    window.navigationBarColor = BochkinoColors.background
    window.decorView.systemUiVisibility = 0
    setContentView(root)
    var imeWasVisible = false
    ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
        val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
        val imeVisible = insets.isVisible(WindowInsetsCompat.Type.ime())
        val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
        val bottomInset = maxOf(bars.bottom, if (imeVisible) ime.bottom else 0)
        view.setPadding(left + bars.left, top + bars.top, right + bars.right, bottom + bottomInset)

        if (imeVisible && !imeWasVisible) {
            view.post {
                val focused = view.findFocus()
                if (focused is EditText) {
                    focused.requestRectangleOnScreen(
                        Rect(0, 0, focused.width, focused.height),
                        true
                    )
                }
            }
        }
        imeWasVisible = imeVisible
        insets
    }
}

internal fun Context.label(
    value: CharSequence,
    size: Float = 16f,
    color: Int = BochkinoColors.white,
    bold: Boolean = false
) = TextView(this).apply {
    text = value
    textSize = size
    setTextColor(color)
    if (bold) typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    includeFontPadding = true
}

internal fun Context.primaryButton(value: String, action: () -> Unit) = MaterialButton(this).apply {
    text = value
    textSize = 16f
    isAllCaps = false
    cornerRadius = dp(7)
    backgroundTintList = ColorStateList.valueOf(BochkinoColors.red)
    setTextColor(BochkinoColors.white)
    setOnClickListener { action() }
}

internal fun Context.secondaryAction(value: String, action: () -> Unit) = TextView(this).apply {
    text = value
    textSize = 14f
    gravity = android.view.Gravity.CENTER
    setTextColor(BochkinoColors.white)
    setOnClickListener { action() }
}

internal fun Context.inputField(hintText: String, inputType: Int) = EditText(this).apply {
    hint = hintText
    this.inputType = inputType
    textSize = 15f
    setTextColor(BochkinoColors.white)
    setHintTextColor(0xFF8C8C8C.toInt())
    setPadding(dp(16), 0, dp(16), 0)
    background = GradientDrawable().apply {
        setColor(BochkinoColors.surface)
        cornerRadius = dp(6).toFloat()
    }
}
