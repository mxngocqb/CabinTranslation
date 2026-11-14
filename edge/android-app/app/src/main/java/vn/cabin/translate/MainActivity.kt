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
 * Landscape, symmetric face-to-face layout (light theme: dark UIs mirror the room on glossy meeting-tablet glass).
 * Everything belonging to the Vietnamese speaker is on the left, everything of the partner on the right:
 *
 *   [logo  CabinTranslation]        [ English | 한국어 | 中文 ]        [Offline] [Sẵn sàng]
 *   ┌ Vietnamese card ─┐ ┌──── conversation ────┐ ┌ partner card ── 🔊 ⟲ ┐
 *   │ 🇻🇳 Tiếng Việt  🔊 │ │ VI bubbles (left)     │ │ 🇬🇧 English          │
 *   │ translation for  │ │     partner (right)   │ │ translation for you  │
 *   │ you (large)      │ │ tap a bubble = replay │ │ (large)              │
 *   │ "Bạn vừa nói: …" │ │                       │ │ "You said: …"        │
 *   │ ( 🎤 Nói )        │ │                       │ │ ( 🎤 Speak )          │
 *   └──────────────────┘ └───────────────────────┘ └──────────────────────┘
 *                         timing / hint line
 * Each speaker's own texts (button, hints, errors) are in that speaker's language.
 */
class MainActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private lateinit var engine: Engine
    private var vad: Vad? = null

    // ---- palette (light)
    private val cBg = Color.parseColor("#EEF2F8")
    private val cCard = Color.WHITE
    private val cLine = Color.parseColor("#E2E8F0")
    private val cChip = Color.parseColor("#F1F5F9")
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
    private val cErr = Color.parseColor("#B91C1C")
    private val cOff1 = Color.parseColor("#CBD5E1")
    private val cOff2 = Color.parseColor("#B6C2D2")

    // ---- views
    private lateinit var statusPill: TextView
    private lateinit var netPill: TextView
    private lateinit var partnerCard: LinearLayout
    private lateinit var partnerHead: TextView
    private lateinit var partnerLast: TextView
    private lateinit var partnerLbl: TextView
    private lateinit var partnerSaid: TextView
    private lateinit var viLast: TextView
    private lateinit var viSaid: TextView
    private lateinit var replayVi: TextView
    private lateinit var replayXx: TextView
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
    private var pendingRow: View? = null

    // ---- state ("vi" = the Vietnamese speaker's side, "xx" = the partner's side)
    private var partner = "en"
    @Volatile private var listening = false
    @Volatile private var forceEnd = false
    @Volatile private var busy = false
    @Volatile private var booting = false
    @Volatile private var engineReady = false   // never probe the engine over HTTP from the UI thread
    @Volatile private var activeSide: String? = null
    private var askedFilesAccess = false
    private var player: MediaPlayer? = null
    private var pulse: ObjectAnimator? = null

    private data class Turn(val src: String, val tgt: String, val said: String, val hyp: String, val ms: Int, val wav: File?)
    private val turnData = ArrayList<Turn>()
    private var turnSeq = 0
    private var stStatus = "Đang khởi động"
    private var stFooter = ""
    private val stLast = mutableMapOf<String, String>()         // side -> last translation shown to that side
    private val stSaid = mutableMapOf<String, Pair<String, Boolean>>()   // side -> (own text or error, isError)
    private val lastWav = mutableMapOf<String, File>()          // side -> audio of the last translation for that side
    private var stTalkEnabled = false

    private val flag = mapOf("vi" to "🇻🇳", "en" to "🇬🇧", "ko" to "🇰🇷", "zh" to "🇨🇳")
    private val lname = mapOf("vi" to "Tiếng Việt", "en" to "English", "ko" to "한국어", "zh" to "中文")
    private val speakLbl = mapOf("vi" to "Nói tiếng Việt", "en" to "Speak English", "ko" to "한국어로 말하기", "zh" to "说中文")
    private val listenLbl = mapOf("vi" to "Đang nghe… chạm để dừng", "en" to "Listening… tap to stop", "ko" to "듣는 중… 눌러서 멈춤", "zh" to "正在听… 点按停止")
    private val busyLbl = mapOf("vi" to "Đang dịch…", "en" to "Translating…", "ko" to "번역 중…", "zh" to "翻译中…")
    private val waitOther = mapOf("vi" to "Vui lòng chờ…", "en" to "Please wait…", "ko" to "잠시만요…", "zh" to "请稍等…")
    private val forYou = mapOf("vi" to "BẢN DỊCH CHO BẠN", "en" to "TRANSLATION FOR YOU", "ko" to "번역", "zh" to "给您的译文")
    private val saidLbl = mapOf("vi" to "Bạn vừa nói", "en" to "You said", "ko" to "방금 말한 내용", "zh" to "您刚才说")
    private val placeholder = mapOf(
        "vi" to "Chạm nút xanh bên dưới để nói.\nLời của khách sẽ được dịch sang tiếng Việt và hiện ở đây.",
        "en" to "Tap the button below to speak.\nWhat the other person says appears here in English.",
        "ko" to "아래 버튼을 눌러 말하세요.\n상대방의 말이 한국어로 여기에 표시됩니다.",
        "zh" to "点击下方按钮说话。\n对方的话会翻译成中文显示在这里。")
    private val noSpeech = mapOf("vi" to "Không nghe thấy tiếng — chạm nút và nói lại", "en" to "No speech heard — tap and try again",
        "ko" to "음성이 들리지 않아요 — 다시 눌러 말해 주세요", "zh" to "没有听到声音 — 请再点一次说话")
    private val noRecog = mapOf("vi" to "Không nhận ra lời nói — hãy nói lại rõ hơn", "en" to "Couldn't recognize that — please repeat",
        "ko" to "인식하지 못했어요 — 다시 말해 주세요", "zh" to "没有识别出来 — 请再说一遍")
    private val failLbl = mapOf("vi" to "Lỗi khi dịch — hãy thử lại", "en" to "Translation failed — please try again",
        "ko" to "번역 오류 — 다시 시도해 주세요", "zh" to "翻译出错 — 请重试")
    private val replayLbl = mapOf("vi" to "Nghe lại", "en" to "Replay", "ko" to "다시 듣기", "zh" to "重播")

    private fun langOf(side: String) = if (side == "vi") "vi" else partner

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
        if (!listening && !busy) buildUi()
    }

    private fun buildUi() {
        segs.clear(); pendingRow = null
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
        replayVi = chipButton("🔊", "vi").apply { setOnClickListener { replay("vi") } }
        viCard.addView(cardHeader("${flag["vi"]}  ${lname["vi"]}", cViSoft, cViInk, listOf(replayVi)))
        viCard.addView(text(forYou["vi"]!!, 11.5f, cInk2, true).apply { letterSpacing = .08f; setPadding(dp(2), dp(16), 0, dp(2)) })
        viLast = lastText()
        viCard.addView(viLast, lp(MATCH, 0, 1f))
        viSaid = saidText()
        viCard.addView(viSaid, lp().apply { bottomMargin = dp(8) })
        meterViTrack = FrameLayout(this).apply { background = round(cLine, 3) }
        meterVi = View(this).apply { background = round(cViLight, 3) }
        meterViTrack.addView(meterVi, FrameLayout.LayoutParams(0, -1))
        viCard.addView(meterViTrack, lp(MATCH, dp(6)).apply { bottomMargin = dp(12) })
        micVi = micButton(cViLight, cVi).apply { setOnClickListener { onTalk("vi") } }
        viCard.addView(micVi, lp(MATCH, dp(84)))

        partnerCard = sideCard()
        replayXx = chipButton("🔊", "xx").apply { setOnClickListener { replay("xx") } }
        val flip = text("⟲  Lật", 14f, cInk2, true).apply {
            gravity = Gravity.CENTER; setPadding(dp(14), 0, dp(14), 0); background = round(cChip, 999, cLine)
            contentDescription = "Lật ngược thẻ này cho người ngồi đối diện"
            setOnClickListener { partnerCard.animate().rotation(if (partnerCard.rotation == 0f) 180f else 0f).setDuration(350).start() }
        }
        val ph = cardHeader("", cXxSoft, cXxInk, listOf(replayXx, flip))
        partnerHead = ph.getChildAt(0) as TextView
        partnerCard.addView(ph)
        partnerLbl = text("", 11.5f, cInk2, true).apply { letterSpacing = .08f; setPadding(dp(2), dp(16), 0, dp(2)) }
        partnerCard.addView(partnerLbl)
        partnerLast = lastText()
        partnerCard.addView(partnerLast, lp(MATCH, 0, 1f))
        partnerSaid = saidText()
        partnerCard.addView(partnerSaid, lp().apply { bottomMargin = dp(8) })
        meterXxTrack = FrameLayout(this).apply { background = round(cLine, 3) }
        meterXx = View(this).apply { background = round(cXxLight, 3) }
        meterXxTrack.addView(meterXx, FrameLayout.LayoutParams(0, -1))
        partnerCard.addView(meterXxTrack, lp(MATCH, dp(6)).apply { bottomMargin = dp(12) })
        micXx = micButton(cXxLight, cXx).apply { setOnClickListener { onTalk("xx") } }
        partnerCard.addView(micXx, lp(MATCH, dp(84)))

        // conversation card
        val convo = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(14), dp(16), dp(14))
            background = round(cCard, 24); elevation = dp(2).toFloat()
        }
        val convoHead = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        convoHead.addView(text("💬  Hội thoại", 15f, cInk, true), lp(WRAP, WRAP))
        convoHead.addView(text("  · chạm vào câu để nghe lại", 12.5f, cInk3), lp(0, WRAP, 1f))
        convoHead.addView(text("Xoá", 13.5f, cInk2, true).apply {
            setPadding(dp(12), dp(5), dp(12), dp(5)); background = round(cChip, 999, cLine)
            setOnClickListener { clearConversation() }
        })
        convo.addView(convoHead, lp(MATCH, dp(36)))
        val convoBox = FrameLayout(this)
        turns = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, dp(4), 0, dp(4)) }
        scroll = ScrollView(this).apply { addView(turns); isVerticalScrollBarEnabled = false }
        emptyBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        spinner = ProgressBar(this).apply { isIndeterminate = true }
        emptyText = text("", 15f, cInk2).apply { gravity = Gravity.CENTER; setPadding(dp(16), dp(12), dp(16), 0); setLineSpacing(0f, 1.2f) }
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

        selectPartner(partner, force = true)
        turnData.forEach { renderTurn(it) }
        refreshEmpty()
        renderMics()
    }

    private fun pill(s: String) = text(s, 13.5f, cInk, true).apply { setPadding(dp(14), dp(7), dp(14), dp(7)); background = round(cCard, 999, cLine) }

    private fun chipButton(s: String, side: String) = text(s, 17f, cInk2, true).apply {
        gravity = Gravity.CENTER; setPadding(dp(12), 0, dp(12), 0); background = round(cChip, 999, cLine)
        contentDescription = "replay $side"; alpha = .35f; isEnabled = false
    }

    private fun sideCard() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; setPadding(dp(18), dp(16), dp(18), dp(18))
        background = round(cCard, 24); elevation = dp(2).toFloat()
    }

    private fun cardHeader(label: String, soft: Int, ink: Int, extras: List<View>) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
        addView(text(label, 16f, ink, true).apply { setPadding(dp(14), dp(8), dp(14), dp(8)); background = round(soft, 999) }, lp(WRAP, WRAP))
        addView(View(this@MainActivity), lp(0, 1, 1f))
        extras.forEachIndexed { i, v -> addView(v, lp(WRAP, dp(40)).apply { if (i > 0) marginStart = dp(8) }) }
    }

    private fun lastText() = text("", 30f, cInk, true).apply {
        gravity = Gravity.CENTER_VERTICAL; setPadding(dp(2), dp(4), dp(2), dp(8)); setLineSpacing(0f, 1.08f)
    }

    private fun saidText() = text("", 14f, cInk2).apply {
        setPadding(dp(12), dp(8), dp(12), dp(8)); background = round(cChip, 12); maxLines = 3; ellipsize = android.text.TextUtils.TruncateAt.END; visibility = View.GONE
    }

    private fun micButton(c1: Int, c2: Int) = text("", 20f, Color.WHITE, true).apply {
        gravity = Gravity.CENTER; background = grad(c1, c2, 999); tag = intArrayOf(c1, c2); elevation = dp(3).toFloat()
    }

    /** Large "translation for you" text, or a small grey how-to while there is none yet. */
    private fun showLast(side: String) {
        val tv = if (side == "vi") viLast else partnerLast
        val s = stLast[side]
        if (s == null) {
            tv.setAutoSizeTextTypeWithDefaults(TextView.AUTO_SIZE_TEXT_TYPE_NONE)
            tv.textSize = 18f; tv.setTextColor(cInk3); tv.text = placeholder[langOf(side)]
        } else {
            tv.setTextColor(cInk); tv.text = s
            tv.setAutoSizeTextTypeUniformWithConfiguration(16, 34, 1, TypedValue.COMPLEX_UNIT_SP)
        }
        (if (side == "vi") replayVi else replayXx).let { b -> val on = lastWav[side] != null; b.isEnabled = on; b.alpha = if (on) 1f else .35f }
    }

    /** "You said: …" under each speaker's own card, or an error in that speaker's language. */
    private fun showSaid(side: String) {
        val tv = if (side == "vi") viSaid else partnerSaid
        val p = stSaid[side]
        if (p == null) { tv.visibility = View.GONE; return }
        tv.visibility = View.VISIBLE
        if (p.second) { tv.text = "⚠️  ${p.first}"; tv.setTextColor(cErr); tv.background = round(Color.parseColor("#FEE2E2"), 12) }
        else { tv.text = "🗣  ${saidLbl[langOf(side)]}: ${p.first}"; tv.setTextColor(cInk2); tv.background = round(cChip, 12) }
    }

    private fun selectPartner(l: String, force: Boolean = false) {
        if (!force && (listening || busy)) return
        if (l != partner) { stLast.remove("xx"); stSaid.remove("xx"); lastWav.remove("xx") }
        partner = l
        segs.forEach { (k, s) ->
            if (k == l) { s.background = round(cXx, 999); s.setTextColor(Color.WHITE) }
            else { s.background = null; s.setTextColor(cInk2) }
        }
        partnerHead.text = "${flag[l]}  ${lname[l]}"
        partnerLbl.text = forYou[l]
        showLast("vi"); showLast("xx"); showSaid("vi"); showSaid("xx")
        refreshEmpty(); renderMics()
    }

    private fun refreshEmpty() {
        val loading = !engineReady
        emptyBox.visibility = if (turnData.isEmpty() && pendingRow == null) View.VISIBLE else View.GONE
        spinner.visibility = if (loading) View.VISIBLE else View.GONE
        emptyText.text = if (loading) stFooter.ifEmpty { "Đang nạp model lên thiết bị…" }
                         else "🎙️\nNgười đang nói chạm nút micro của mình.\nNói một hai câu ngắn — ngừng nói là tự dịch và đọc to.\n\n" +
                              "${flag[partner]}  ${placeholder[partner]!!.substringBefore('\n')}"
    }

    private fun clearConversation() {
        if (listening || busy) return
        player?.stop()
        turnData.forEach { it.wav?.delete() }
        turnData.clear(); turns.removeAllViews(); stLast.clear(); stSaid.clear(); lastWav.clear()
        showLast("vi"); showLast("xx"); showSaid("vi"); showSaid("xx")
        refreshEmpty()
    }

    private fun setStatus(s: String) = ui.post { stStatus = s; statusPill.text = s; netPill.text = netLabel() }
    private fun setHint(s: String) = ui.post { stFooter = s; footer.text = s; if (!engineReady) refreshEmpty() }
    private fun setTalkEnabled(on: Boolean) { stTalkEnabled = on; renderMics() }

    /** One place that decides how both microphone buttons look: idle / listening / translating / waiting. */
    private fun renderMics() = ui.post {
        pulse?.cancel(); pulse = null
        for ((b, side) in listOf(micVi to "vi", micXx to "xx")) {
            val lang = langOf(side)
            val cs = b.tag as IntArray
            b.alpha = 1f
            val mine = activeSide == side
            when {
                listening && mine -> {
                    b.isEnabled = true; b.background = grad(cRec, cRecDark, 999); b.text = "●   ${listenLbl[lang]}"
                    pulse = ObjectAnimator.ofFloat(b, "alpha", 1f, .72f).apply {
                        duration = 650; repeatMode = ValueAnimator.REVERSE; repeatCount = ValueAnimator.INFINITE; start()
                    }
                }
                busy && mine -> { b.isEnabled = false; b.background = grad(cs[0], cs[1], 999); b.alpha = .8f; b.text = "⏳   ${busyLbl[lang]}" }
                listening || busy -> { b.isEnabled = false; b.background = grad(cOff1, cOff2, 999); b.text = waitOther[lang] }
                else -> {
                    b.isEnabled = stTalkEnabled
                    b.background = if (stTalkEnabled) grad(cs[0], cs[1], 999) else grad(cOff1, cOff2, 999)
                    b.text = if (side == "vi") "🎤   ${speakLbl["vi"]}  →  ${flag[partner]}" else "🎤   ${speakLbl[partner]}"
                }
            }
        }
        if (!listening) listOf(meterVi, meterXx).forEach { m -> (m.layoutParams as FrameLayout.LayoutParams).width = 0; m.requestLayout() }
    }

    private fun netLabel(): String {
        val cm = getSystemService(ConnectivityManager::class.java)
        val online = cm?.getNetworkCapabilities(cm.activeNetwork)?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
        return if (online) "🌐  Online" else "✈️  Offline"
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
        if (!engineReady || busy || listening) return
        val src = i.getStringExtra("src") ?: "vi"
        val tgt = i.getStringExtra("tgt") ?: partner
        if (src != "vi") selectPartner(src) else if (tgt != "vi") selectPartner(tgt)
        i.removeExtra("wav")
        activeSide = if (src == "vi") "vi" else "xx"
        thread {
            try {
                val b = File(path).readBytes()
                val n = (b.size - 44) / 2
                val x = FloatArray(n) { k -> ((b[44 + 2 * k].toInt() and 255) or (b[45 + 2 * k].toInt() shl 8)).toShort() / 32768f }
                translate(x, src, tgt)
            } catch (e: Exception) { android.util.Log.e("CabinUI", "demo failed", e); setHint("Demo lỗi: ${e.message}"); activeSide = null; renderMics() }
        }
    }

    override fun onDestroy() { listening = false; engine.stop(); vad?.release(); player?.release(); super.onDestroy() }

    // ---------------------------------------------------------------- capture (AudioRecord 16 kHz + VAD)
    private fun onTalk(side: String) {
        if (busy) return
        if (listening) { if (activeSide == side) forceEnd = true; return }   // second tap: finish now
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1); return
        }
        val src = langOf(side); val tgt = if (side == "vi") partner else "vi"
        try { player?.stop() } catch (_: Exception) {}          // never record our own loudspeaker
        listening = true; forceEnd = false; activeSide = side
        stSaid.remove(side); showSaid(side)
        renderMics()
        setHint("🎙  Đang nghe ${flag[src]} ${lname[src]} — ngừng nói là tự dịch, hoặc chạm nút đỏ để dừng")
        thread { captureOneUtterance(src, tgt, side) }
    }

    private fun captureOneUtterance(src: String, tgt: String, side: String) {
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
        val (meter, track) = if (side == "vi") meterVi to meterViTrack else meterXx to meterXxTrack
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
        // prefer the raw capture (pre-roll + everything until the VAD end) so word onsets are never clipped
        val audio = if (captured.isNotEmpty()) captured.flatMap { it.asIterable() }.toFloatArray() else segment
        if (audio == null || audio.size < sr / 3) {
            ui.post { stSaid[side] = noSpeech[src]!! to true; showSaid(side) }
            setHint(noSpeech["vi"]!!); activeSide = null; renderMics(); return
        }
        translate(audio, src, tgt)
    }

    // ---------------------------------------------------------------- translate + speak
    private fun translate(audio: FloatArray, src: String, tgt: String) {
        val side = if (src == "vi") "vi" else "xx"
        val other = if (side == "vi") "xx" else "vi"
        busy = true; activeSide = side; renderMics()
        setStatus("⏳  Đang dịch")
        setHint("Đang dịch trên thiết bị…")
        ui.post { addPending(src) }
        try {
            val r = engine.translate(floatsToWav(audio), src, tgt)
            val said = r.optString("mt_in").ifEmpty { r.optString("asr") }.trim()
            val hyp = r.optString("hyp").trim()
            val total = r.optDouble("total_ms").toInt()
            val timing = "ASR %d ms · dịch %d ms · TTS %d ms · tổng %d ms".format(
                r.optDouble("asr_ms").toInt(), r.optDouble("mt_ms").toInt(), r.optDouble("tts_ms").toInt(), total)
            if (said.isEmpty() || hyp.isEmpty()) {
                ui.post { removePending(); stSaid[side] = noRecog[src]!! to true; showSaid(side) }
                setStatus("✅  Sẵn sàng"); setHint(noRecog["vi"]!!)
                return
            }
            val wav = r.optString("audio_b64").takeIf { it.isNotEmpty() }?.let {
                File(cacheDir, "turn_${++turnSeq}.wav").apply { writeBytes(Base64.decode(it, Base64.DEFAULT)) }
            }
            ui.post {
                removePending()
                addTurn(src, tgt, said, hyp, total, wav)
                stLast[other] = hyp; wav?.let { lastWav[other] = it }
                stSaid[side] = said to false
                showLast(other); showSaid(side)
            }
            wav?.let { play(it) }
            setStatus("✅  Sẵn sàng"); setHint(timing)
        } catch (e: Exception) {
            ui.post { removePending(); stSaid[side] = failLbl[src]!! to true; showSaid(side) }
            setStatus("❌  Lỗi"); setHint("Lỗi dịch: ${e.message}")
        } finally { busy = false; activeSide = null; renderMics() }
    }

    private fun play(f: File) = ui.post {
        try {
            player?.release()
            player = MediaPlayer().apply { setDataSource(f.absolutePath); prepare(); start() }
        } catch (e: Exception) { android.util.Log.e("CabinUI", "play failed", e) }
    }

    private fun replay(side: String) { if (!listening) lastWav[side]?.let { play(it) } }

    private fun addTurn(src: String, tgt: String, said: String, hyp: String, ms: Int, wav: File?) {
        val t = Turn(src, tgt, said, hyp, ms, wav); turnData.add(t); renderTurn(t)
    }

    private fun bubbleRow(fromVi: Boolean, bubble: View): LinearLayout {
        // Vietnamese bubbles on the left (next to the Vietnamese card), the partner's on the right
        val row = LinearLayout(this).apply { gravity = if (fromVi) Gravity.START else Gravity.END }
        val w = resources.displayMetrics.widthPixels * 0.30
        row.addView(bubble, LinearLayout.LayoutParams(w.toInt(), WRAP))
        return row
    }

    private fun bubbleBg(fromVi: Boolean) = GradientDrawable().apply {
        setColor(if (fromVi) cViSoft else cXxSoft)
        val r = dp(18).toFloat(); val s = dp(5).toFloat()
        cornerRadii = if (fromVi) floatArrayOf(s, s, r, r, r, r, r, r) else floatArrayOf(r, r, s, s, r, r, r, r)
    }

    private fun addPending(src: String) {
        removePending()
        val fromVi = src == "vi"
        val bubble = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(12)); background = bubbleBg(fromVi)
            addView(ProgressBar(this@MainActivity).apply { isIndeterminate = true }, lp(dp(22), dp(22)).apply { marginEnd = dp(10) })
            addView(text("${flag[src]}  ${busyLbl[src]}", 15f, cInk2))
        }
        val row = bubbleRow(fromVi, bubble)
        turns.addView(row, lp().apply { topMargin = dp(5); bottomMargin = dp(5) })
        pendingRow = row
        refreshEmpty()
        scroll.post { scroll.fullScroll(View.FOCUS_DOWN) }
    }

    private fun removePending() { pendingRow?.let { turns.removeView(it) }; pendingRow = null }

    private fun renderTurn(t: Turn) {
        val (src, tgt, said, hyp, ms, wav) = t
        emptyBox.visibility = View.GONE
        val fromVi = src == "vi"
        val bubble = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setPadding(dp(14), dp(10), dp(14), dp(10)); background = bubbleBg(fromVi)
            if (wav != null) setOnClickListener { if (!listening) play(wav) }
        }
        bubble.addView(text("${flag[src]}  $said", 13.5f, cInk2))
        bubble.addView(text("${flag[tgt]}  $hyp", 17f, if (fromVi) cViInk else cXxInk, true).apply { setPadding(0, dp(4), 0, dp(2)) })
        val foot = "%s%.1f s".format(if (wav != null) "🔊 ${replayLbl[tgt]}  ·  " else "", ms / 1000.0)
        bubble.addView(text(foot, 11.5f, cInk3).apply { gravity = Gravity.END })
        turns.addView(bubbleRow(fromVi, bubble), lp().apply { topMargin = dp(5); bottomMargin = dp(5) })
        scroll.post { scroll.fullScroll(View.FOCUS_DOWN) }
    }
}
