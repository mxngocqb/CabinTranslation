package vn.cabin.translate

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * Runs the on-device engine (cabin_edge: sherpa-onnx ASR + Gemma 4 E2B on GPU via LiteRT-LM + TTS)
 * as a child process from the app's native-lib dir and talks to it over loopback HTTP.
 * Models live in the app's external files dir: /sdcard/Android/data/vn.cabin.translate/files/models
 */
class Engine(private val ctx: Context) {
    private var proc: Process? = null
    val port = 18181
    /** Shared-storage location written by edge/android-app/install.sh (needs "All files access"). */
    val modelsDir: File = File(android.os.Environment.getExternalStorageDirectory(), "CabinTranslation/models")
    val logFile: File = File(ctx.filesDir, "engine.log")

    fun modelsPresent(): Boolean = File(modelsDir, "gemma-4-E2B-it-gpu.litertlm").exists()

    /** Writes config.json/prompts.json for this install and starts the engine. Blocks until healthy. */
    fun start(langs: String = "vi,en,ko,zh", onProgress: (String) -> Unit): Boolean {
        if (healthy()) return true
        val files = ctx.filesDir
        File(files, "cache").mkdirs()
        File(files, "live").mkdirs()
        ctx.assets.open("prompts.json").use { i -> File(files, "prompts.json").outputStream().use { i.copyTo(it) } }
        val cfg = ctx.assets.open("config.template.json").bufferedReader().readText()
            .replace("/data/local/tmp/cabin/models", modelsDir.absolutePath)
            .replace("/data/local/tmp/cabin/prompts.json", File(files, "prompts.json").absolutePath)
            .replace("/data/local/tmp/cabin/cache", File(files, "cache").absolutePath)
            .replace("/data/local/tmp/cabin/web", File(files, "web").absolutePath)
        val cfgJson = JSONObject(cfg).put("live_dir", File(files, "live").absolutePath)
        val cfgFile = File(files, "config.json").apply { writeText(cfgJson.toString(1)) }

        val libDir = ctx.applicationInfo.nativeLibraryDir
        val pb = ProcessBuilder(
            "$libDir/libcabin_edge.so", "--config", cfgFile.absolutePath,
            "--serve", port.toString(), "--langs", langs, "--host", "127.0.0.1"
        )
        pb.environment()["LD_LIBRARY_PATH"] = libDir
        pb.redirectErrorStream(true)
        pb.redirectOutput(logFile)
        proc = pb.start()
        val t0 = System.currentTimeMillis()
        while (System.currentTimeMillis() - t0 < 180_000) {
            if (proc?.isAlive != true) { onProgress("Engine stopped: " + logFile.readText().takeLast(300)); return false }
            if (healthy()) return true
            onProgress("Đang nạp model lên thiết bị… ${(System.currentTimeMillis() - t0) / 1000}s")
            Thread.sleep(700)
        }
        return false
    }

    fun stop() { proc?.destroy(); proc = null }

    fun healthy(): Boolean = try {
        val c = URL("http://127.0.0.1:$port/api/health").openConnection() as HttpURLConnection
        c.connectTimeout = 400; c.readTimeout = 800
        val ok = c.responseCode == 200
        c.disconnect(); ok
    } catch (e: Exception) { false }

    fun health(): JSONObject? = try {
        val c = URL("http://127.0.0.1:$port/api/health").openConnection() as HttpURLConnection
        JSONObject(c.inputStream.bufferedReader().readText()).also { c.disconnect() }
    } catch (e: Exception) { null }

    /** 16 kHz mono PCM16 WAV in -> JSON {asr, mt_in, hyp, *_ms, audio_b64 (translated speech WAV)}. */
    fun translate(wav: ByteArray, src: String, tgt: String): JSONObject {
        val c = URL("http://127.0.0.1:$port/api/translate?src=$src&tgt=$tgt").openConnection() as HttpURLConnection
        c.requestMethod = "POST"; c.doOutput = true
        c.connectTimeout = 2000; c.readTimeout = 60_000
        c.setRequestProperty("Content-Type", "audio/wav")
        c.outputStream.use { it.write(wav) }
        val body = c.inputStream.bufferedReader().readText()
        c.disconnect()
        return JSONObject(body)
    }

    companion object { const val TAG = "CabinEngine" }
}

/** PCM float [-1,1] @16 kHz -> WAV bytes (PCM16). */
fun floatsToWav(x: FloatArray, sr: Int = 16000): ByteArray {
    val n = x.size
    val out = java.io.ByteArrayOutputStream(44 + n * 2)
    fun le32(v: Int) { out.write(v and 255); out.write((v shr 8) and 255); out.write((v shr 16) and 255); out.write((v shr 24) and 255) }
    fun le16(v: Int) { out.write(v and 255); out.write((v shr 8) and 255) }
    out.write("RIFF".toByteArray()); le32(36 + n * 2); out.write("WAVE".toByteArray())
    out.write("fmt ".toByteArray()); le32(16); le16(1); le16(1); le32(sr); le32(sr * 2); le16(2); le16(16)
    out.write("data".toByteArray()); le32(n * 2)
    for (v in x) le16((v.coerceIn(-1f, 1f) * 32767f).toInt())
    return out.toByteArray()
}
