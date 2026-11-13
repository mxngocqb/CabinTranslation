package vn.cabin.translate

import android.Manifest
import android.animation.ObjectAnimator
import android.animation.ValueAnimator
import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Base64
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import com.k2fsa.sherpa.onnx.SileroVadModelConfig
import com.k2fsa.sherpa.onnx.Vad
import com.k2fsa.sherpa.onnx.VadModelConfig
import java.io.File
import kotlin.concurrent.thread
import kotlin.math.abs

/**
 * Landscape, symmetric face-to-face layout (light theme: dark UIs mirror the room on glossy meeting-tablet glass):
 *
 *   [logo  CabinTranslation]        [ English | 한국어 | 中文 ]        [Online] [Sẵn sàng]
 *   ┌ Vietnamese card ┐ ┌──── conversation ────┐ ┌ partner card ┐
 *   │ 🇻🇳 Tiếng Việt    │ │ chat bubbles          │ │ 🇬🇧 English  ⟲ │
 *   │ last translation │ │ (VI right, partner    │ │ last transl.  │
 *   │ ▁▂▃ meter        │ │  left)                │ │ ▁▂▃ meter     │
 *   │ ( 🎤 Nói )        │ │                       │ │ ( 🎤 Speak )   │
 *   └──────────────────┘ └───────────────────────┘ └───────────────┘
 *                         timing / hint line
 */
class MainActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private lateinit var engine: Engine
    private var vad: Vad? = null

    // ---- palette (light)
    private val cBg = Color.parseColor("#EEF2F8")
    private val cCard = Color.WHITE
    private val cLine = Color.parseColor("#E2E8F0")
    private val cInk = Color.parseColor("#0F172A")
    private val cInk2 = Color.parseColor("#64748B")
    private val cInk3 = Color.parseColor("#A0AEC0")
    private val cVi = Color.parseColor("#2563EB")
    private val cViLight = Color.parseColor("#3B82F6")
    private val cViSoft = Color.parseColor("#E0EBFF")
    private val cViInk = Color.parseColor("#1E3A8A")
    private val cXx = Color.parseColor("#059669")
    private val cXxLight = Color.parseColor("#10B981")
    private val cXxSoft = Color.parseColor("#DDF5EA")
    private val cXxInk = Color.parseColor("#065F46")
    private val cRec = Color.parseColor("#EF4444")
    private val cRecDark = Color.parseColor("#DC2626")
    private val cOff1 = Color.parseColor("#CBD5E1")
    private val cOff2 = Color.parseColor("#B6C2D2")

    // ---- views
    private lateinit var statusPill: TextView
    private lateinit var netPill: TextView
    private lateinit var partnerCard: LinearLayout
    private lateinit var partnerHead: TextView
    private lateinit var partnerLast: TextView
    private lateinit var partnerLbl: TextView
    private lateinit var viLast: TextView
    private lateinit var micVi: TextView
    private lateinit var micXx: TextView
    private lateinit var meterVi: View
    private lateinit var meterViTrack: FrameLayout
    private lateinit var meterXx: View
    private lateinit var meterXxTrack: FrameLayout
    private lateinit var footer: TextView
    private lateinit var turns: LinearLayout
    private lateinit var scroll: ScrollView
    private lateinit var emptyBox: LinearLayout
    private lateinit var emptyText: TextView
    private lateinit var spinner: ProgressBar
    private val segs = mutableMapOf<String, TextView>()

    // ---- state
    private var partner = "en"
    @Volatile private var listening = false
    @Volatile private var forceEnd = false
    @Volatile private var busy = false
    @Volatile private var booting = false
    @Volatile private var engineReady = false   // never probe the engine over HTTP from the UI thread
    private var askedFilesAccess = false
    private var player: MediaPlayer? = null
    private var pulse: ObjectAnimator? = null
    private var recBtn: TextView? = null

    private data class Turn(val src: String, val tgt: String, val said: String, val hyp: String, val ms: Int)
    private val turnData = ArrayList<Turn>()
    private var stStatus = "Đang khởi động"
    private var stFooter = ""
    private var stViLast: String? = null
    private var stXxLast: String? = null
    private var stTalkEnabled = false

    private val flag = mapOf("vi" to "🇻🇳", "en" to "🇬🇧", "ko" to "🇰🇷", "zh" to "🇨🇳")
    private val lname = mapOf("vi" to "Tiếng Việt", "en" to "English", "ko" to "한국어", "zh" to "中文")
    private val speakLbl = mapOf("vi" to "Nói tiếng Việt", "en" to "Speak English", "ko" to "한국어로 말하기", "zh" to "说中文")
    private val listenLbl = mapOf("vi" to "Đang nghe… chạm để dừng", "en" to "Listening… tap to stop", "ko" to "듣는 중… 눌러서 멈춤", "zh" to "正在听… 点按停止")
    private val waitLbl = mapOf("vi" to "Lời dịch sẽ hiện ở đây", "en" to "The translation will appear here", "ko" to "번역이 여기에 표시됩니다", "zh" to "译文会显示在这里")
    private val forYou = mapOf("vi" to "BẢN DỊCH CHO BẠN", "en" to "TRANSLATION FOR YOU", "ko" to "번역", "zh" to "给您的译文")

    // ---------------------------------------------------------------- helpers
    private fun dp(v: Number) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), resources.displayMetrics).toInt()
    private fun round(color: Int, r: Number, stroke: Int? = null) = GradientDrawable().apply {
        setColor(color); cornerRadius = dp(r).toFloat(); stroke?.let { setStroke(dp(1), it) }
    }
    private fun grad(c1: Int, c2: Int, r: Number) =
        GradientDrawable(GradientDrawable.Orientation.TL_BR, intArrayOf(c1, c2)).apply { cornerRadius = dp(r).toFloat() }
    private fun text(s: String = "", size: Float = 15f, color: Int = cInk, bold: Boolean = false) = TextView(this).apply {
        text = s; textSize = size; setTextColor(color)
        typeface = Typeface.create(if (bold) "sans-serif-medium" else "sans-serif", Typeface.NORMAL)
    }
    private fun lp(w: Int = LinearLayout.LayoutParams.MATCH_PARENT, h: Int = LinearLayout.LayoutParams.WRAP_CONTENT, weight: Float = 0f) =
        LinearLayout.LayoutParams(w, h, weight)
    private val WRAP = LinearLayout.LayoutParams.WRAP_CONTENT
    private val MATCH = LinearLayout.LayoutParams.MATCH_PARENT

    // ---------------------------------------------------------------- layout
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = cBg; window.navigationBarColor = cBg
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        engine = Engine(this)
        buildUi()
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1)
    }

    override fun onConfigurationChanged(newConfig: android.content.res.Configuration) {
        super.onConfigurationChanged(newConfig)
        if (!listening) buildUi()
    }

    private fun buildUi() {
        segs.clear()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setBackgroundColor(cBg); setPadding(dp(22), dp(14), dp(22), dp(10))
        }

        // ---- header: logo + name | language selector | status
        val header = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val logo = text("⇄", 22f, Color.WHITE, true).apply { gravity = Gravity.CENTER; background = grad(cViLight, cXxLight, 14) }
        header.addView(logo, lp(dp(44), dp(44)).apply { marginEnd = dp(12) })
        val titleBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        titleBox.addView(text("CabinTranslation", 20f, cInk, true))
        titleBox.addView(text("Phiên dịch 2 chiều · chạy hoàn toàn trên thiết bị", 12.5f, cInk2))
        header.addView(titleBox, lp(0, WRAP, 1f))

        val seg = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL; setPadding(dp(4), dp(4), dp(4), dp(4)); background = round(cCard, 999, cLine)
        }
        for (l in listOf("en", "ko", "zh")) {
            val s = text("${flag[l]}  ${lname[l]}", 15f, cInk, true).apply {
                gravity = Gravity.CENTER; setPadding(dp(18), dp(8), dp(18), dp(8)); setOnClickListener { selectPartner(l) }
            }
            segs[l] = s
            seg.addView(s, lp(WRAP, WRAP))
        }
        header.addView(seg, lp(WRAP, WRAP).apply { marginEnd = dp(16) })
        netPill = pill(netLabel())
        statusPill = pill(stStatus)
        header.addView(netPill, lp(WRAP, WRAP).apply { marginEnd = dp(8) })
        header.addView(statusPill, lp(WRAP, WRAP))
        root.addView(header, lp().apply { bottomMargin = dp(14) })

        // ---- body: VI card | conversation | partner card
        val body = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }

        val viCard = sideCard()
        viCard.addView(cardHeader("${flag["vi"]}  ${lname["vi"]}", cViSoft, cViInk, null))
        viCard.addView(text(forYou["vi"]!!, 11.5f, cInk2, true).apply { letterSpacing = .08f; setPadding(dp(2), dp(16), 0, dp(2)) })
        viLast = lastText()
        viCard.addView(viLast, lp(MATCH, 0, 1f))
        meterViTrack = FrameLayout(this).apply { background = round(cLine, 3) }
        meterVi = View(this).apply { background = round(cViLight, 3) }
        meterViTrack.addView(meterVi, FrameLayout.LayoutParams(0, -1))
        viCard.addView(meterViTrack, lp(MATCH, dp(6)).apply { bottomMargin = dp(12) })
        micVi = micButton(cViLight, cVi).apply { setOnClickListener { onTalk("vi", partner, this) } }
        viCard.addView(micVi, lp(MATCH, dp(84)))

        partnerCard = sideCard()
        val flip = text("⟲", 20f, cInk2).apply {
            gravity = Gravity.CENTER; background = round(Color.parseColor("#F1F5F9"), 999, cLine)
            contentDescription = "Lật ngược cho người ngồi đối diện"
            setOnClickListener { partnerCard.animate().rotation(if (partnerCard.rotation == 0f) 180f else 0f).setDuration(350).start() }
        }
        val ph = cardHeader("", cXxSoft, cXxInk, flip)
        partnerHead = ph.getChildAt(0) as TextView
        partnerCard.addView(ph)
        partnerLbl = text("", 11.5f, cInk2, true).apply { letterSpacing = .08f; setPadding(dp(2), dp(16), 0, dp(2)) }
        partnerCard.addView(partnerLbl)
        partnerLast = lastText()
        partnerCard.addView(partnerLast, lp(MATCH, 0, 1f))
        meterXxTrack = FrameLayout(this).apply { background = round(cLine, 3) }
        meterXx = View(this).apply { background = round(cXxLight, 3) }
        meterXxTrack.addView(meterXx, FrameLayout.LayoutParams(0, -1))
        partnerCard.addView(meterXxTrack, lp(MATCH, dp(6)).apply { bottomMargin = dp(12) })
        micXx = micButton(cXxLight, cXx).apply { setOnClickListener { onTalk(partner, "vi", this) } }
        partnerCard.addView(micXx, lp(MATCH, dp(84)))

        // conversation card
        val convo = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(14), dp(16), dp(14))
            background = round(cCard, 24); elevation = dp(2).toFloat()
        }
        val convoHead = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        convoHead.addView(text("💬  Hội thoại", 15f, cInk, true), lp(0, WRAP, 1f))
        convoHead.addView(text("Xoá", 13.5f, cInk2, true).apply {
            setPadding(dp(12), dp(5), dp(12), dp(5)); background = round(Color.parseColor("#F1F5F9"), 999, cLine)
            setOnClickListener { clearConversation() }
        })
        convo.addView(convoHead, lp(MATCH, dp(36)))
        val convoBox = FrameLayout(this)
        turns = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, dp(4), 0, dp(4)) }
        scroll = ScrollView(this).apply { addView(turns); isVerticalScrollBarEnabled = false }
        emptyBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        spinner = ProgressBar(this).apply { isIndeterminate = true }
        emptyText = text("", 15f, cInk2).apply { gravity = Gravity.CENTER; setPadding(dp(16), dp(12), dp(16), 0) }
        emptyBox.addView(spinner, lp(dp(44), dp(44)))
        emptyBox.addView(emptyText, lp(WRAP, WRAP))
        convoBox.addView(scroll, FrameLayout.LayoutParams(-1, -1))
        convoBox.addView(emptyBox, FrameLayout.LayoutParams(-1, -1))
        convo.addView(convoBox, lp(MATCH, 0, 1f))

        body.addView(viCard, lp(0, MATCH, 1f))
        body.addView(convo, lp(0, MATCH, 1.3f).apply { marginStart = dp(16); marginEnd = dp(16) })
        body.addView(partnerCard, lp(0, MATCH, 1f))
        root.addView(body, lp(MATCH, 0, 1f))

        footer = text(stFooter, 12.5f, cInk2).apply { gravity = Gravity.CENTER; setPadding(0, dp(8), 0, 0); maxLines = 1 }
        root.addView(footer, lp())
        setContentView(root)

        selectPartner(partner)
        stViLast?.let { viLast.text = it; viLast.setTextColor(cInk) } ?: run { viLast.text = waitLbl["vi"]; viLast.setTextColor(cInk3) }
        turnData.forEach { renderTurn(it) }
        refreshEmpty()
        setTalkEnabled(stTalkEnabled)
    }

    private fun pill(s: String) = text(s, 13.5f, cInk, true).apply { setPadding(dp(14), dp(7), dp(14), dp(7)); background = round(cCard, 999, cLine) }

    private fun sideCard() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; setPadding(dp(18), dp(16), dp(18), dp(18))
        background = round(cCard, 24); elevation = dp(2).toFloat()
    }

    private fun cardHeader(label: String, soft: Int, ink: Int, extra: View?) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
        addView(text(label, 16f, ink, true).apply { setPadding(dp(14), dp(8), dp(14), dp(8)); background = round(soft, 999) }, lp(WRAP, WRAP))
        addView(View(this@MainActivity), lp(0, 1, 1f))
        addView(extra ?: View(this@MainActivity), lp(dp(40), dp(40)))   // same header height on both cards
    }

    private fun lastText() = text("", 30f, cInk, true).apply {
        gravity = Gravity.CENTER_VERTICAL; setPadding(dp(2), dp(4), dp(2), dp(8)); setLineSpacing(0f, 1.08f)
        setAutoSizeTextTypeUniformWithConfiguration(16, 34, 1, TypedValue.COMPLEX_UNIT_SP)
    }

    private fun micButton(c1: Int, c2: Int) = text("", 20f, Color.WHITE, true).apply {
        gravity = Gravity.CENTER; background = grad(c1, c2, 999); tag = intArrayOf(c1, c2); elevation = dp(3).toFloat()
    }

    private fun selectPartner(l: String) {
        if (listening || busy) return
        partner = l
        segs.forEach { (k, s) ->
            if (k == l) { s.background = round(cXx, 999); s.setTextColor(Color.WHITE) }
            else { s.background = null; s.setTextColor(cInk2) }
        }
        partnerHead.text = "${flag[l]}  ${lname[l]}"
        partnerLbl.text = forYou[l]
        if (!listening) {
            micXx.text = "🎤   ${speakLbl[l]}"
            micVi.text = "🎤   ${speakLbl["vi"]}  →  ${flag[l]}"
        }
        if (stXxLast == null) { partnerLast.text = waitLbl[l]; partnerLast.setTextColor(cInk3) }
        else { partnerLast.text = stXxLast; partnerLast.setTextColor(cInk) }
    }

    private fun refreshEmpty() {
        val loading = !engineReady
        emptyBox.visibility = if (turnData.isEmpty() || loading && turnData.isEmpty()) View.VISIBLE else View.GONE
        spinner.visibility = if (loading) View.VISIBLE else View.GONE
        emptyText.text = if (loading) stFooter.ifEmpty { "Đang nạp model lên thiết bị…" }
                         else "🎙️\nChạm nút micro của người đang nói.\nNói xong, ứng dụng tự dịch và đọc to."
    }

    private fun clearConversation() {
        if (listening || busy) return
        turnData.clear(); turns.removeAllViews(); stViLast = null; stXxLast = null
        viLast.text = waitLbl["vi"]; viLast.setTextColor(cInk3)
        partnerLast.text = waitLbl[partner]; partnerLast.setTextColor(cInk3)
        refreshEmpty()
    }

    private fun setStatus(s: String) = ui.post { stStatus = s; statusPill.text = s; netPill.text = netLabel() }
    private fun setHint(s: String) = ui.post { stFooter = s; footer.text = s; if (!engineReady) refreshEmpty() }

    private fun setTalkEnabled(on: Boolean) = ui.post {
        stTalkEnabled = on
        listOf(micVi, micXx).forEach { b ->
            if (b === recBtn && listening) return@forEach
            b.isEnabled = on
            val cs = b.tag as IntArray
            b.background = if (on) grad(cs[0], cs[1], 999) else grad(cOff1, cOff2, 999)
        }
    }

    private fun netLabel(): String {
        val cm = getSystemService(ConnectivityManager::class.java)
        val online = cm?.getNetworkCapabilities(cm.activeNetwork)?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
        return if (online) "🌐  Online" else "✈️  Offline"
    }

    private fun setRecording(btn: TextView, on: Boolean, src: String) = ui.post {
        val cs = btn.tag as IntArray
        pulse?.cancel(); btn.alpha = 1f
        if (on) {
            recBtn = btn
            btn.background = grad(cRec, cRecDark, 999)
            btn.text = "●   ${listenLbl[src]}"
            pulse = ObjectAnimator.ofFloat(btn, "alpha", 1f, .72f).apply {
                duration = 650; repeatMode = ValueAnimator.REVERSE; repeatCount = ValueAnimator.INFINITE; start()
            }
        } else {
            recBtn = null
            btn.background = grad(cs[0], cs[1], 999)
            btn.text = if (btn === micVi) "🎤   ${speakLbl["vi"]}  →  ${flag[partner]}" else "🎤   ${speakLbl[partner]}"
            listOf(meterVi, meterXx).forEach { m -> (m.layoutParams as FrameLayout.LayoutParams).width = 0; m.requestLayout() }
        }
    }

    // ---------------------------------------------------------------- engine + VAD
    override fun onResume() {
        super.onResume()
        netPill.text = netLabel()
        if (!booting && !engineReady) bootEngine()
    }

    private fun bootEngine() {
        if (booting) return
        if (!android.os.Environment.isExternalStorageManager()) {
            setStatus("⚠️  Cần quyền tệp"); setHint("Cần quyền \"Truy cập mọi tệp\" để đọc model trong ${engine.modelsDir.absolutePath}")
            if (!askedFilesAccess) {
                askedFilesAccess = true
                startActivity(android.content.Intent(android.provider.Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                    android.net.Uri.parse("package:$packageName")))
            }
            return
        }
        booting = true
        thread { try { bootEngineInner() } finally { booting = false } }
    }

    private fun bootEngineInner() {
        if (!engine.modelsPresent()) {
            setStatus("⚠️  Thiếu model"); setHint("Chép model vào ${engine.modelsDir.absolutePath} (xem edge/android-app/README.md)")
            return
        }
        setStatus("⏳  Đang nạp model")
        val t0 = System.currentTimeMillis()
        val ok = engine.start { msg -> setHint(msg) }
        if (!ok) { setStatus("❌  Lỗi engine"); setHint("Log: ${engine.logFile.absolutePath}"); return }
        // Silero VAD exactly as in the sherpa-onnx vad-asr sample, with a longer silence for conversational speech
        if (vad == null) vad = Vad(assets, VadModelConfig(
            sileroVadModelConfig = SileroVadModelConfig(model = "silero_vad.onnx", threshold = 0.5f,
                minSilenceDuration = 0.6f, minSpeechDuration = 0.25f, windowSize = 512, maxSpeechDuration = 20f),
            sampleRate = 16000, numThreads = 1, provider = "cpu"))
        val rss = (engine.health()?.optLong("rss_kb") ?: 0) / 1024
        engineReady = true
        setStatus("✅  Sẵn sàng")
        setHint("Gemma 4 E2B trên GPU · nạp ${(System.currentTimeMillis() - t0) / 1000}s · RAM ${rss} MB")
        setTalkEnabled(true)
        ui.post { refreshEmpty(); handleDemoIntent(intent) }
    }

    override fun onNewIntent(i: android.content.Intent) { super.onNewIntent(i); setIntent(i); handleDemoIntent(i) }

    /** Remote testing without a speaker in the room:
     *  adb shell am start -f 0x20000000 -n vn.cabin.translate/.MainActivity --es wav /sdcard/Download/x.wav --es src vi --es tgt en
     *  The 16 kHz PCM16 WAV is processed exactly like a microphone utterance. */
    private fun handleDemoIntent(i: android.content.Intent?) {
        val path = i?.getStringExtra("wav") ?: return
        android.util.Log.i("CabinUI", "demo intent wav=$path ready=$engineReady busy=$busy")
        if (!engineReady || busy) return
        val src = i.getStringExtra("src") ?: "vi"
        val tgt = i.getStringExtra("tgt") ?: partner
        if (src != "vi") selectPartner(src) else if (tgt != "vi") selectPartner(tgt)
        i.removeExtra("wav")
        thread {
            try {
                val b = File(path).readBytes()
                val n = (b.size - 44) / 2
                val x = FloatArray(n) { k -> ((b[44 + 2 * k].toInt() and 255) or (b[45 + 2 * k].toInt() shl 8)).toShort() / 32768f }
                translate(x, src, tgt)
            } catch (e: Exception) { android.util.Log.e("CabinUI", "demo failed", e); setHint("Demo lỗi: ${e.message}") }
        }
    }

    override fun onDestroy() { listening = false; engine.stop(); vad?.release(); player?.release(); super.onDestroy() }

    // ---------------------------------------------------------------- capture (AudioRecord 16 kHz + VAD)
    private fun onTalk(src: String, tgt: String, btn: TextView) {
        if (busy) return
        if (listening) { forceEnd = true; return }          // second tap: finish now
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1); return
        }
        player?.stop()
        listening = true; forceEnd = false
        setRecording(btn, true, src)
        val other = if (btn === micVi) micXx else micVi
        ui.post { other.isEnabled = false; other.background = grad(cOff1, cOff2, 999) }
        setHint("Nói xong, ứng dụng sẽ tự dịch")
        thread { captureOneUtterance(src, tgt, btn) }
    }

    private fun captureOneUtterance(src: String, tgt: String, btn: TextView) {
        val sr = 16000
        val minBuf = AudioRecord.getMinBufferSize(sr, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, sr, AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, sr))   // VOICE_RECOGNITION: no AGC/NS, like the sample apps
        val v = vad!!
        v.reset()
        val buf = ShortArray(512)
        val pre = ArrayDeque<FloatArray>()                         // 0.3 s pre-roll in front of the VAD onset
        val captured = ArrayList<FloatArray>()
        var speechStarted = false
        var segment: FloatArray? = null
        val t0 = System.currentTimeMillis()
        val (meter, track) = if (btn === micVi) meterVi to meterViTrack else meterXx to meterXxTrack
        rec.startRecording()
        try {
            while (listening) {
                val n = rec.read(buf, 0, buf.size)
                if (n <= 0) continue
                val x = FloatArray(n) { buf[it] / 32768f }
                var pk = 0f; for (s in x) pk = maxOf(pk, abs(s))
                ui.post {
                    val lpm = meter.layoutParams as FrameLayout.LayoutParams
                    lpm.width = (track.width * (pk * 1.6f).coerceAtMost(1f)).toInt(); meter.requestLayout()
                }
                v.acceptWaveform(x)
                if (!speechStarted) {
                    pre.addLast(x); while (pre.size > 10) pre.removeFirst()
                    if (v.isSpeechDetected()) { speechStarted = true; captured.addAll(pre) }
                } else captured.add(x)
                if (!v.empty()) { segment = v.front().samples; v.pop(); break }   // VAD closed the utterance
                if (forceEnd) { v.flush(); if (!v.empty()) { segment = v.front().samples; v.pop() }; break }
                if (!speechStarted && System.currentTimeMillis() - t0 > 10_000) break   // nothing said
            }
        } finally { rec.stop(); rec.release() }
        listening = false
        setRecording(btn, false, src)
        // prefer the raw capture (pre-roll + everything until the VAD end) so word onsets are never clipped
        val audio = if (captured.isNotEmpty()) captured.flatMap { it.asIterable() }.toFloatArray() else segment
        if (audio == null || audio.size < sr / 3) { setHint("Không nghe thấy tiếng nói — chạm và nói lại"); setTalkEnabled(true); return }
        translate(audio, src, tgt)
    }

    // ---------------------------------------------------------------- translate + speak
    private fun translate(audio: FloatArray, src: String, tgt: String) {
        busy = true; setTalkEnabled(false)
        setStatus("⏳  Đang dịch")
        setHint("Đang dịch trên thiết bị…")
        try {
            val r = engine.translate(floatsToWav(audio), src, tgt)
            val said = r.optString("mt_in").ifEmpty { r.optString("asr") }
            val hyp = r.optString("hyp")
            val total = r.optDouble("total_ms").toInt()
            val timing = "ASR %d ms · dịch %d ms · TTS %d ms · tổng %d ms".format(
                r.optDouble("asr_ms").toInt(), r.optDouble("mt_ms").toInt(), r.optDouble("tts_ms").toInt(), total)
            ui.post {
                addTurn(src, tgt, said, hyp, total)
                val shown = hyp.ifEmpty { "…" }
                if (tgt == "vi") { stViLast = shown; viLast.text = shown; viLast.setTextColor(cInk) }
                else { stXxLast = shown; partnerLast.text = shown; partnerLast.setTextColor(cInk) }
            }
            r.optString("audio_b64").takeIf { it.isNotEmpty() }?.let { play(it) }
            setStatus("✅  Sẵn sàng"); setHint(timing)
        } catch (e: Exception) {
            setStatus("❌  Lỗi"); setHint("Lỗi dịch: ${e.message}")
        } finally { busy = false; setTalkEnabled(true) }
    }

    private fun play(b64: String) {
        val f = File(cacheDir, "tts.wav").apply { writeBytes(Base64.decode(b64, Base64.DEFAULT)) }
        ui.post {
            player?.release()
            player = MediaPlayer().apply { setDataSource(f.absolutePath); prepare(); start() }
        }
    }

    private fun addTurn(src: String, tgt: String, said: String, hyp: String, ms: Int) {
        val t = Turn(src, tgt, said, hyp, ms); turnData.add(t); renderTurn(t)
    }

    private fun renderTurn(t: Turn) {
        val (src, tgt, said, hyp, ms) = t
        emptyBox.visibility = View.GONE
        val mine = src == "vi"
        val bubble = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setPadding(dp(14), dp(10), dp(14), dp(10))
            background = GradientDrawable().apply {
                setColor(if (mine) cViSoft else cXxSoft)
                val r = dp(18).toFloat(); val s = dp(5).toFloat()
                cornerRadii = if (mine) floatArrayOf(r, r, s, s, r, r, r, r) else floatArrayOf(s, s, r, r, r, r, r, r)
            }
        }
        bubble.addView(text("${flag[src]}  $said", 13.5f, cInk2))
        bubble.addView(text("${flag[tgt]}  $hyp", 17f, if (mine) cViInk else cXxInk, true).apply { setPadding(0, dp(4), 0, dp(2)) })
        bubble.addView(text("$ms ms", 11f, cInk3).apply { gravity = Gravity.END })
        val row = LinearLayout(this).apply { gravity = if (mine) Gravity.END else Gravity.START }
        val w = resources.displayMetrics.widthPixels * 0.30
        row.addView(bubble, LinearLayout.LayoutParams(w.toInt(), WRAP))
        turns.addView(row, lp().apply { topMargin = dp(5); bottomMargin = dp(5) })
        scroll.post { scroll.fullScroll(View.FOCUS_DOWN) }
    }
}
