package com.astrofrekans.astrofrekans

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import java.util.UUID

/** Generic lock-screen surface. No consultation or user details are rendered. */
class IncomingCallActivity : Activity() {
    companion object {
        private var active: IncomingCallActivity? = null
        fun dismiss(id: String) {
            active?.takeIf { it.callId == id }?.finish()
        }
    }

    private var callId: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val id = intent.getStringExtra("callId")
        val nonce = intent.getStringExtra("nonce")
        val valid = try {
            id != null && UUID.fromString(id).toString().equals(id, ignoreCase = true)
        } catch (_: IllegalArgumentException) { false }
        if (!valid || nonce == null) {
            finish()
            return
        }
        val callIdValue = id!!
        if (!NativeCallDelivery.validNonce(this, callIdValue, nonce) ||
            NativeCallDelivery.expiresAt(this, callIdValue) <= System.currentTimeMillis() / 1000) {
            finish()
            return
        }
        callId = callIdValue
        active = this
        if (Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
            )
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val remainingMs = ((NativeCallDelivery.expiresAt(this, callIdValue) -
            System.currentTimeMillis() / 1000) * 1000).coerceAtLeast(1)
        Handler(Looper.getMainLooper()).postDelayed({
            if (!isFinishing && callId == callIdValue) finish()
        }, remainingMs)

        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.rgb(10, 16, 29))
            setPadding(32, 32, 32, 32)
        }
        content.addView(TextView(this).apply {
            text = "Astrofrekans"
            textSize = 28f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT))
        content.addView(TextView(this).apply {
            text = "Gelen görüşme"
            textSize = 20f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT))
        content.addView(Button(this).apply {
            text = "Kabul et"
            setOnClickListener { handoff("answer") }
        })
        content.addView(Button(this).apply {
            text = "Reddet"
            setOnClickListener { handoff("decline") }
        })
        setContentView(content)
    }

    private fun handoff(action: String) {
        val id = callId ?: return
        val nonce = intent.getStringExtra("nonce") ?: return
        startActivity(Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("callId", id)
            putExtra("action", action)
            putExtra("nonce", nonce)
        })
        finish()
    }

    override fun onDestroy() {
        if (active === this) active = null
        super.onDestroy()
    }
}
