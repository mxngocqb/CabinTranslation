// cabin_edge — on-device voice-to-voice interpreter + benchmark driver (Android arm64).
//
//   ASR  : sherpa-onnx C API (zipformer / X-ASR), CPU
//   MT   : Gemma 4 E2B via LiteRT-LM C API, GPU (short context)
//   TTS  : ViFastTts (Rust FFI) for Vietnamese, sherpa-onnx Supertonic (en/ko) / Matcha (zh), CPU
//
// Usage (on device):
//   cabin_edge --config config.json --manifest in.jsonl --out out.jsonl [--wav-dir outwav]
// Manifest lines:
//   {"id":"VE-1","task":"e2e","src":"vi","tgt":"en","wav":"/path/in.wav"}      ASR -> MT -> TTS
//   {"id":"VE-1","task":"mt","src":"vi","tgt":"en","text":"..."}               text MT only
//   {"id":"VE-1","task":"asr","src":"vi","wav":"..."}                           ASR only
//   {"id":"VE-1","task":"tts","tgt":"vi","text":"..."}                          TTS only
// Every output line carries per-stage timings (ms); a final {"summary":...} line reports load
// times, peak RSS (VmHWM) and GPU memory if readable.
#include <sys/resource.h>
#include <climits>
#include <cstdlib>
#include <unistd.h>

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <regex>
#include <sstream>
#include <string>
#include <vector>

#include "c-api.h"         // sherpa-onnx
#include "conversation.h"  // litert-lm
#include "engine.h"        // litert-lm
#include "error_reporter.h"  // litert-lm
#include "json.hpp"
#include "vifasttts.h"
#include "httplib.h"

using json = nlohmann::json;
using Clock = std::chrono::steady_clock;

static std::string jdump(const json& j) { return j.dump(-1, ' ', false, json::error_handler_t::replace); }

static double ms_since(Clock::time_point t0) {
  return std::chrono::duration<double, std::milli>(Clock::now() - t0).count();
}

static std::string read_file(const std::string& p) {
  std::ifstream f(p);
  std::stringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

static long status_kb(const char* key) {
  std::ifstream f("/proc/self/status");
  std::string line;
  while (std::getline(f, line)) {
    if (line.rfind(key, 0) == 0) return std::atol(line.c_str() + strlen(key));
  }
  return -1;
}

// Adreno per-process GPU memory (kgsl). Returns -1 if not readable.
static long kgsl_gpu_kb() {
  std::string p = "/sys/class/kgsl/kgsl/proc/" + std::to_string(getpid()) + "/gpumem_mapped";
  std::ifstream f(p);
  long v = -1;
  if (f >> v) return v / 1024;
  p = "/sys/class/kgsl/kgsl/proc/" + std::to_string(getpid()) + "/gpumem_unmapped";
  std::ifstream g(p);
  if (g >> v) return v / 1024;
  return -1;
}

// ---------------------------------------------------------------- UTF-8 helpers
static std::u32string to_u32(const std::string& s) {
  std::u32string out;
  for (size_t i = 0; i < s.size();) {
    unsigned char c = s[i];
    char32_t cp;
    int n;
    if (c < 0x80) { cp = c; n = 1; }
    else if ((c >> 5) == 6) { cp = c & 0x1F; n = 2; }
    else if ((c >> 4) == 14) { cp = c & 0x0F; n = 3; }
    else { cp = c & 0x07; n = 4; }
    for (int k = 1; k < n && i + k < s.size(); ++k) cp = (cp << 6) | (s[i + k] & 0x3F);
    out.push_back(cp);
    i += n;
  }
  return out;
}

static std::string to_u8(const std::u32string& s) {
  std::string out;
  for (char32_t cp : s) {
    if (cp < 0x80) out.push_back(char(cp));
    else if (cp < 0x800) { out.push_back(char(0xC0 | (cp >> 6))); out.push_back(char(0x80 | (cp & 0x3F))); }
    else if (cp < 0x10000) {
      out.push_back(char(0xE0 | (cp >> 12))); out.push_back(char(0x80 | ((cp >> 6) & 0x3F)));
      out.push_back(char(0x80 | (cp & 0x3F)));
    } else {
      out.push_back(char(0xF0 | (cp >> 18))); out.push_back(char(0x80 | ((cp >> 12) & 0x3F)));
      out.push_back(char(0x80 | ((cp >> 6) & 0x3F))); out.push_back(char(0x80 | (cp & 0x3F)));
    }
  }
  return out;
}

// Lower-case for Latin + all Vietnamese letters (enough for ASR output).
static char32_t lower_cp(char32_t c) {
  if (c >= 'A' && c <= 'Z') return c + 32;
  if (c >= 0xC0 && c <= 0xDE && c != 0xD7) return c + 32;
  if ((c >= 0x100 && c <= 0x17F) && (c % 2 == 0)) return c + 1;  // Latin Ext-A pairs (Ă Đ Ĩ Ũ ...)
  if (c == 0x1A0 || c == 0x1AF) return c + 1;                     // Ơ Ư
  if (c >= 0x1EA0 && c <= 0x1EF9 && (c % 2 == 0)) return c + 1;   // Vietnamese tone letters
  return c;
}

static bool is_upper_cp(char32_t c) { return lower_cp(c) != c; }

static std::string lower_u8(const std::string& s) {
  std::u32string u = to_u32(s);
  for (auto& c : u) c = lower_cp(c);
  return to_u8(u);
}

static bool all_caps(const std::string& s) {
  bool any_letter = false;
  for (char32_t c : to_u32(s)) {
    if (is_upper_cp(c)) any_letter = true;
    else if (lower_cp(c) == c && ((c >= 'a' && c <= 'z') || (c >= 0xDF && c <= 0x1EF9 && c != 0xF7)))
      return false;  // found a lower-case letter
  }
  return any_letter;
}

static std::string capitalize_first(const std::string& s) {
  std::u32string u = to_u32(s);
  if (!u.empty()) {
    for (char32_t c = 0x41; c <= 0x1EF9; ++c) {  // reverse lookup of lower_cp
      if (lower_cp(c) == u[0] && c != u[0]) { u[0] = c; break; }
    }
  }
  return to_u8(u);
}

// word sequence after removing punctuation, lower-cased (to verify the punctuation pass)
static std::vector<std::string> words(const std::string& s) {
  std::u32string u = to_u32(lower_u8(s));
  std::vector<std::string> out;
  std::u32string cur;
  auto flush = [&] { if (!cur.empty()) { out.push_back(to_u8(cur)); cur.clear(); } };
  for (char32_t c : u) {
    bool punct = (c < 0x80 && !isalnum(int(c))) || (c >= 0x2000 && c <= 0x206F) || (c >= 0x3000 && c <= 0x303F) ||
                 (c >= 0xFF00 && c <= 0xFF65);
    if (punct) flush(); else cur.push_back(c);
  }
  flush();
  return out;
}

static bool ends_with(const std::string& s, const std::string& t) {
  return s.size() >= t.size() && s.compare(s.size() - t.size(), t.size(), t) == 0;
}

// rule-based fallback (mirrors cabin/normalize.py prep_asr_text)
static std::string prep_asr_text(std::string t, const std::string& lang, const json& cfg) {
  if (t.empty() || (lang != "vi" && lang != "en") || !all_caps(t)) return t;
  t = lower_u8(t);
  char last = t.back();
  if (last != '.' && last != '?' && last != '!') {
    bool q = false;
    if (lang == "vi") {
      for (auto& e : cfg["vi_q_end"]) q |= ends_with(t, e.get<std::string>());
      std::string padded = " " + t + " ";
      for (auto& e : cfg["vi_q_any"]) q |= padded.find(" " + e.get<std::string>() + " ") != std::string::npos;
    } else {
      std::string first = t.substr(0, t.find(' '));
      for (auto& e : cfg["en_q_start"]) q |= first == e.get<std::string>();
    }
    t += q ? "?" : ".";
  }
  return capitalize_first(t);
}

static std::string clean_output(std::string out) {
  out = std::regex_replace(out, std::regex("</?[a-zA-Z][a-zA-Z0-9]*>"), "");
  auto nl = out.find('\n');
  if (nl != std::string::npos && nl > 3) out = out.substr(0, nl);
  out = std::regex_replace(out, std::regex("(anh|chị|ông|bà|bạn|em)\\s*/\\s*(anh|chị|ông|bà|bạn|em)"), "$1");
  while (!out.empty() && (out.back() == ' ' || out.back() == '"')) out.pop_back();
  while (!out.empty() && (out.front() == ' ' || out.front() == '"')) out.erase(0, 1);
  return out;
}

// ---------------------------------------------------------------- MT (LiteRT-LM)
struct MT {
  LiteRtLmEngine* engine = nullptr;
  LiteRtLmEngineSettings* settings = nullptr;
  int max_out = 128;
  double load_ms = 0;
  bool prefix_cache = true;
  // one prefilled conversation per system prompt; cloned per request so the ~170-token system
  // prompt is prefilled once instead of on every sentence
  struct Base { LiteRtLmConversation* conv; LiteRtLmConversationConfig* cc; LiteRtLmSessionConfig* sc;
                LiteRtLmSamplerParams* sp; };
  std::map<std::string, Base> bases;

  std::string speculative = "off";
  int steps_per_sync = 0;
  int num_threads = 0;  // CPU backend only; 0 = LiteRT-LM default
  std::string dispatch_lib_dir;
  // "greedy" (GPU), "topk1" or "default" (model metadata, stochastic). The CPU backend implements
  // neither GREEDY nor TOP_K ("Sampler type: N not implemented yet"); TOP_P with k=1 is the same argmax.
  std::string sampler = "greedy";
  LiteRtLmSamplerParams* make_sampler() {
    LiteRtLmSamplerParams* sp = nullptr;
    if (sampler == "default") return nullptr;  // model metadata's sampler
    if (sampler == "topk1") {
      // the CPU sampler factory only implements TOP_P (which also applies k): k=1 -> argmax
      litert_lm_sampler_params_create(kLiteRtLmSamplerTypeTopP, &sp);
      litert_lm_sampler_params_set_top_k(sp, 1);
      litert_lm_sampler_params_set_top_p(sp, 1.0f);
      litert_lm_sampler_params_set_temperature(sp, 1.0f);
      litert_lm_sampler_params_set_seed(sp, 0);
    } else {
      litert_lm_sampler_params_create(kLiteRtLmSamplerTypeGreedy, &sp);
    }
    return sp;
  }

  bool init(const std::string& model, const std::string& backend, int max_tokens, int max_out_tokens,
            const std::string& cache_dir) {
    auto t0 = Clock::now();
    max_out = max_out_tokens;
    litert_lm_set_min_log_level(kLiteRtLmLogSeverityError);
    if (litert_lm_engine_settings_create(model.c_str(), backend.c_str(), nullptr, nullptr, &settings) !=
        kLiteRtLmStatusOk) {
      std::cerr << "engine_settings_create failed\n";
      return false;
    }
    litert_lm_engine_settings_set_max_num_tokens(settings, max_tokens);
    if (!cache_dir.empty()) litert_lm_engine_settings_set_cache_dir(settings, cache_dir.c_str());
    litert_lm_engine_settings_enable_benchmark(settings);
    if (steps_per_sync > 0) litert_lm_engine_settings_set_gpu_decode_steps_per_sync(settings, steps_per_sync);
    if (num_threads > 0) litert_lm_engine_settings_set_num_threads(settings, num_threads);
    if (!dispatch_lib_dir.empty())  // NPU: dir with libLiteRtDispatch_Qualcomm.so + QNN libs
      litert_lm_engine_settings_set_litert_dispatch_lib_dir(settings, dispatch_lib_dir.c_str());
#ifndef CABIN_NO_SPECULATIVE  // the LiteRT-LM 0.18 NPU runtime (libLiteRtLm.so) has no speculative-decoding API
    if (speculative != "off") {
      LiteRtLmSpeculativeDecodingConfig* sd = nullptr;
      litert_lm_speculative_decoding_config_create(&sd);
      litert_lm_speculative_decoding_config_set_mode(
          sd, speculative == "adaptive" ? kLiteRtLmSpeculativeDecodingModeAdaptive : kLiteRtLmSpeculativeDecodingModeOn);
      litert_lm_engine_settings_set_speculative_decoding_config(settings, sd);
      litert_lm_speculative_decoding_config_delete(sd);
    }
#endif
    if (litert_lm_engine_create(settings, &engine) != kLiteRtLmStatusOk) {
      std::cerr << "engine_create failed\n";
      return false;
    }
    load_ms = ms_since(t0);
    return true;
  }

  Base make_base(const std::string& system) {
    Base b{};
    b.sp = make_sampler();
    litert_lm_session_config_create(&b.sc);
    litert_lm_session_config_set_max_output_tokens(b.sc, max_out);
    if (b.sp) litert_lm_session_config_set_sampler_params(b.sc, b.sp);
    litert_lm_conversation_config_create(&b.cc);
    litert_lm_conversation_config_set_session_config(b.cc, b.sc);
    json sysmsg = {{"type", "text"}, {"text", system}};
    litert_lm_conversation_config_set_system_message(b.cc, jdump(sysmsg).c_str());
    litert_lm_conversation_create(engine, b.cc, &b.conv);
    return b;
  }

  // returns translation; fills stats
  std::string chat_cached(const std::string& system, const std::string& user, json& stats);
  static void report_error(const char* where, int st, json& stats) {
    const char* m = litert_lm_get_last_error_message();
    std::string e = std::string(where) + " status=" + std::to_string(st) + ": " + (m ? m : "");
    std::cerr << "[mt] " << e << "\n";
    stats["error"] = e;
    litert_lm_clear_last_error();
  }
  std::string chat(const std::string& system, const std::string& user, json& stats) {
    if (prefix_cache) return chat_cached(system, user, stats);
    LiteRtLmSamplerParams* sp = make_sampler();
    LiteRtLmSessionConfig* sc = nullptr;
    litert_lm_session_config_create(&sc);
    litert_lm_session_config_set_max_output_tokens(sc, max_out);
    if (sp) litert_lm_session_config_set_sampler_params(sc, sp);
    LiteRtLmConversationConfig* cc = nullptr;
    litert_lm_conversation_config_create(&cc);
    litert_lm_conversation_config_set_session_config(cc, sc);
    json sysmsg = {{"type", "text"}, {"text", system}};
    litert_lm_conversation_config_set_system_message(cc, jdump(sysmsg).c_str());

    auto t0 = Clock::now();
    LiteRtLmConversation* conv = nullptr;
    std::string text;
    if (litert_lm_conversation_create(engine, cc, &conv) == kLiteRtLmStatusOk) {
      json msg = {{"role", "user"}, {"content", json::array({{{"type", "text"}, {"text", user}}})}};
      LiteRtLmJsonResponse* resp = nullptr;
      auto st = litert_lm_conversation_send_message(conv, jdump(msg).c_str(), nullptr, nullptr, &resp);
      if (st != kLiteRtLmStatusOk) report_error("send_message", st, stats);
      if (st == kLiteRtLmStatusOk) {
        const char* s = nullptr;
        litert_lm_json_response_get_string(resp, &s);
        try {
          json r = json::parse(s ? s : "{}");
          if (r.contains("content")) {
            for (auto& c : r["content"])
              if (c.value("type", "") == "text") text += c.value("text", "");
          }
        } catch (...) {
          text = s ? s : "";
        }
        litert_lm_json_response_delete(resp);
      }
      LiteRtLmBenchmarkInfo* bi = nullptr;
      if (litert_lm_conversation_get_benchmark_info(conv, &bi) == kLiteRtLmStatusOk) {
        double ttft = 0, pf = 0, dc = 0;
        size_t np = 0, nd = 0, ptok = 0, dtok = 0;
        litert_lm_benchmark_info_get_time_to_first_token(bi, &ttft);
        litert_lm_benchmark_info_get_num_prefill_turns(bi, &np);
        litert_lm_benchmark_info_get_num_decode_turns(bi, &nd);
        if (np) {
          litert_lm_benchmark_info_get_prefill_tokens_per_sec_at(bi, np - 1, &pf);
          litert_lm_benchmark_info_get_prefill_token_count_at(bi, np - 1, &ptok);
        }
        if (nd) {
          litert_lm_benchmark_info_get_decode_tokens_per_sec_at(bi, nd - 1, &dc);
          litert_lm_benchmark_info_get_decode_token_count_at(bi, nd - 1, &dtok);
        }
        stats["ttft_ms"] = ttft * 1000;
        stats["prefill_tok"] = ptok;
        stats["prefill_tps"] = pf;
        stats["decode_tok"] = dtok;
        stats["decode_tps"] = dc;
        litert_lm_benchmark_info_delete(bi);
      }
      litert_lm_conversation_delete(conv);
    }
    stats["ms"] = ms_since(t0);
    litert_lm_conversation_config_delete(cc);
    litert_lm_session_config_delete(sc);
    if (sp) litert_lm_sampler_params_delete(sp);
    return clean_output(text);
  }
};

std::string MT::chat_cached(const std::string& system, const std::string& user, json& stats) {
  auto it = bases.find(system);
  if (it == bases.end()) {
    auto t0 = Clock::now();
    it = bases.emplace(system, make_base(system)).first;
    stats["base_create_ms"] = ms_since(t0);
  }
  auto t0 = Clock::now();
  LiteRtLmConversation* conv = nullptr;
  std::string text;
  if (it->second.conv && litert_lm_conversation_clone(it->second.conv, &conv) == kLiteRtLmStatusOk) {
    stats["clone_ms"] = ms_since(t0);
    json msg = {{"role", "user"}, {"content", json::array({{{"type", "text"}, {"text", user}}})}};
    LiteRtLmJsonResponse* resp = nullptr;
    auto st = litert_lm_conversation_send_message(conv, jdump(msg).c_str(), nullptr, nullptr, &resp);
    if (st != kLiteRtLmStatusOk) report_error("send_message", st, stats);
    if (st == kLiteRtLmStatusOk) {
      const char* s = nullptr;
      litert_lm_json_response_get_string(resp, &s);
      try {
        json r = json::parse(s ? s : "{}");
        for (auto& c : r.value("content", json::array()))
          if (c.value("type", "") == "text") text += c.value("text", "");
      } catch (...) { text = s ? s : ""; }
      litert_lm_json_response_delete(resp);
    }
    LiteRtLmBenchmarkInfo* bi = nullptr;
    if (litert_lm_conversation_get_benchmark_info(conv, &bi) == kLiteRtLmStatusOk) {
      double ttft = 0, pf = 0, dc = 0;
      size_t np = 0, nd = 0, ptok = 0, dtok = 0;
      litert_lm_benchmark_info_get_time_to_first_token(bi, &ttft);
      litert_lm_benchmark_info_get_num_prefill_turns(bi, &np);
      litert_lm_benchmark_info_get_num_decode_turns(bi, &nd);
      if (np) { litert_lm_benchmark_info_get_prefill_tokens_per_sec_at(bi, np - 1, &pf);
                litert_lm_benchmark_info_get_prefill_token_count_at(bi, np - 1, &ptok); }
      if (nd) { litert_lm_benchmark_info_get_decode_tokens_per_sec_at(bi, nd - 1, &dc);
                litert_lm_benchmark_info_get_decode_token_count_at(bi, nd - 1, &dtok); }
      stats["ttft_ms"] = ttft * 1000; stats["prefill_tok"] = ptok; stats["prefill_tps"] = pf;
      stats["decode_tok"] = dtok; stats["decode_tps"] = dc;
      litert_lm_benchmark_info_delete(bi);
    }
    litert_lm_conversation_delete(conv);
  }
  stats["ms"] = ms_since(t0);
  return clean_output(text);
}

// ---------------------------------------------------------------- ASR (sherpa-onnx)
struct ASR {
  const SherpaOnnxOfflineRecognizer* rec = nullptr;
  std::vector<std::string> keep;  // own the strings referenced by the config
  double load_ms = 0;

  bool init(const json& c, int threads) {
    auto t0 = Clock::now();
    SherpaOnnxOfflineRecognizerConfig cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.feat_config.sample_rate = 16000;
    cfg.feat_config.feature_dim = 80;
    auto S = [&](const char* k) { keep.push_back(c.value(k, std::string())); return keep.back().c_str(); };
    keep.reserve(16);
    cfg.model_config.transducer.encoder = S("encoder");
    cfg.model_config.transducer.decoder = S("decoder");
    cfg.model_config.transducer.joiner = S("joiner");
    cfg.model_config.tokens = S("tokens");
    cfg.model_config.model_type = S("model_type");
    cfg.model_config.num_threads = threads;
    cfg.model_config.provider = S("provider");
    if (!c.contains("provider")) cfg.model_config.provider = "cpu";
    cfg.decoding_method = "greedy_search";
    rec = SherpaOnnxCreateOfflineRecognizer(&cfg);
    load_ms = ms_since(t0);
    return rec != nullptr;
  }

  std::string run(const float* samples, int n, int sr) {
    const SherpaOnnxOfflineStream* s = SherpaOnnxCreateOfflineStream(rec);
    SherpaOnnxAcceptWaveformOffline(s, sr, samples, n);
    SherpaOnnxDecodeOfflineStream(rec, s);
    const SherpaOnnxOfflineRecognizerResult* r = SherpaOnnxGetOfflineStreamResult(s);
    std::string text = r && r->text ? r->text : "";
    SherpaOnnxDestroyOfflineRecognizerResult(r);
    SherpaOnnxDestroyOfflineStream(s);
    while (!text.empty() && text.front() == ' ') text.erase(0, 1);
    while (!text.empty() && text.back() == ' ') text.pop_back();
    return text;
  }
};

// ---------------------------------------------------------------- TTS
struct TTS {
  std::string kind;  // vifasttts | supertonic | matcha
  VifasttEngine vf = nullptr;
  const SherpaOnnxOfflineTts* st = nullptr;
  std::string extra;
  std::vector<std::string> keep;
  double load_ms = 0;
  int steps = 5;
  int sid = 0;

  bool init(const json& c, int threads) {
    steps = c.value("num_steps", 5);
    auto t0 = Clock::now();
    kind = c.value("kind", "");
    if (kind == "vifasttts") {
      vf = vifasttts_engine_new(c["acoustic"].get<std::string>().c_str(), c["vocoder"].get<std::string>().c_str());
      if (!vf) std::cerr << "vifasttts: " << vifasttts_last_error() << "\n";
      load_ms = ms_since(t0);
      return vf != nullptr;
    }
    keep.reserve(16);
    auto S = [&](const char* k) { keep.push_back(c.value(k, std::string())); return keep.back().c_str(); };
    SherpaOnnxOfflineTtsConfig cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.model.num_threads = threads;
    cfg.model.provider = S("provider");
    if (!c.contains("provider")) cfg.model.provider = "cpu";
    cfg.max_num_sentences = 2;
    if (kind == "supertonic") {
      cfg.model.supertonic.duration_predictor = S("duration_predictor");
      cfg.model.supertonic.text_encoder = S("text_encoder");
      cfg.model.supertonic.vector_estimator = S("vector_estimator");
      cfg.model.supertonic.vocoder = S("vocoder");
      cfg.model.supertonic.tts_json = S("tts_json");
      cfg.model.supertonic.unicode_indexer = S("unicode_indexer");
      cfg.model.supertonic.voice_style = S("voice_style");
      extra = json({{"lang", c.value("lang", "en")}}).dump();
    } else if (kind == "vits") {  // Piper / Mimic3 / MMS (espeak-ng frontend bundled in the Android lib)
      cfg.model.vits.model = S("model");
      cfg.model.vits.tokens = S("tokens");
      cfg.model.vits.data_dir = S("data_dir");
      cfg.model.vits.lexicon = S("lexicon");
      cfg.model.vits.noise_scale = c.value("noise_scale", 0.667f);
      cfg.model.vits.noise_scale_w = c.value("noise_scale_w", 0.8f);
      cfg.model.vits.length_scale = c.value("length_scale", 1.0f);
      sid = c.value("sid", 0);
    } else if (kind == "kitten") {
      cfg.model.kitten.model = S("model");
      cfg.model.kitten.voices = S("voices");
      cfg.model.kitten.tokens = S("tokens");
      cfg.model.kitten.data_dir = S("data_dir");
      cfg.model.kitten.length_scale = c.value("length_scale", 1.0f);
      sid = c.value("sid", 0);
    } else if (kind == "matcha") {
      cfg.model.matcha.acoustic_model = S("acoustic_model");
      cfg.model.matcha.vocoder = S("vocoder");
      cfg.model.matcha.lexicon = S("lexicon");
      cfg.model.matcha.tokens = S("tokens");
      cfg.model.matcha.dict_dir = S("dict_dir");
      cfg.model.matcha.noise_scale = 0.667f;
      cfg.model.matcha.length_scale = 1.0f;
      cfg.rule_fsts = S("rule_fsts");
    }
    st = SherpaOnnxCreateOfflineTts(&cfg);
    load_ms = ms_since(t0);
    return st != nullptr;
  }

  // returns WAV bytes (empty on failure); sets audio seconds
  std::string synth(const std::string& text, double* secs) {
    std::string wav;
    *secs = 0;
    if (vf) {
      size_t n = 0;
      uint8_t* buf = vifasttts_synthesize(vf, text.c_str(), nullptr, &n);
      if (!buf) { std::cerr << "vifasttts: " << vifasttts_last_error() << "\n"; return wav; }
      wav.assign((char*)buf, n);
      uint32_t sr = 24000; uint16_t bits = 16;
      if (n > 44) { memcpy(&sr, buf + 24, 4); memcpy(&bits, buf + 34, 2); }
      *secs = double(n - 44) / (sr * (bits / 8));
      vifasttts_buffer_free(buf, n);
      return wav;
    }
    SherpaOnnxGenerationConfig g;
    memset(&g, 0, sizeof(g));
    g.speed = 1.0f;
    g.silence_scale = 0.2f;
    g.num_steps = kind == "supertonic" ? steps : 0;
    g.sid = sid;
    if (!extra.empty()) g.extra = extra.c_str();
    const SherpaOnnxGeneratedAudio* a = SherpaOnnxOfflineTtsGenerateWithConfig(st, text.c_str(), &g, nullptr, nullptr);
    if (a) {
      *secs = double(a->n) / a->sample_rate;
      wav.resize(SherpaOnnxWaveFileSize(a->n));
      SherpaOnnxWriteWaveToBuffer(a->samples, a->n, a->sample_rate, wav.data());
      SherpaOnnxDestroyOfflineTtsGeneratedAudio(a);
    }
    return wav;
  }

  double run(const std::string& text, const std::string& wav_path) {
    double secs = 0;
    std::string wav = synth(text, &secs);
    if (!wav_path.empty() && !wav.empty()) { std::ofstream f(wav_path, std::ios::binary); f.write(wav.data(), wav.size()); }
    return secs;
  }
};

// ---------------------------------------------------------------- pipeline
struct Pipeline {
  json cfg, prompts, summary;
  std::map<std::string, std::unique_ptr<ASR>> asr;
  std::map<std::string, std::unique_ptr<TTS>> tts;
  MT mt;
  bool mt_ready = false;
  bool punct_pass = true;

  bool load_lang(const std::string& lang, bool need_asr, bool need_tts) {
    if (need_asr && !asr.count(lang)) {
      auto a = std::make_unique<ASR>();
      if (!a->init(cfg["asr"][lang], cfg.value("threads", 4))) { std::cerr << "ASR init failed: " << lang << "\n"; return false; }
      summary["load_ms"]["asr_" + lang] = a->load_ms;
      asr[lang] = std::move(a);
    }
    if (need_tts && !tts.count(lang)) {
      auto t = std::make_unique<TTS>();
      if (!t->init(cfg["tts"][lang], cfg.value("tts_threads", 2))) { std::cerr << "TTS init failed: " << lang << "\n"; return false; }
      summary["load_ms"]["tts_" + lang] = t->load_ms;
      tts[lang] = std::move(t);
    }
    return true;
  }

  bool load_mt() {
    if (mt_ready) return true;
    mt.prefix_cache = cfg["mt"].value("prefix_cache", true);
    mt.speculative = cfg["mt"].value("speculative", "off");
    mt.steps_per_sync = cfg["mt"].value("decode_steps_per_sync", 0);
    mt.num_threads = cfg["mt"].value("num_threads", 0);
    mt.dispatch_lib_dir = cfg["mt"].value("dispatch_lib_dir", "");
    mt.sampler = cfg["mt"].value("sampler", cfg["mt"].value("backend", "gpu") == "cpu" ? "topk1" : "greedy");
    if (!mt.init(cfg["mt"]["model"], cfg["mt"].value("backend", "gpu"), cfg["mt"].value("max_num_tokens", 384),
                 cfg["mt"].value("max_output_tokens", 128), cfg["mt"].value("cache_dir", "")))
      return false;
    summary["load_ms"]["mt"] = mt.load_ms;
    summary["mt_backend"] = cfg["mt"].value("backend", "gpu");
    summary["mt_model"] = cfg["mt"]["model"];
    summary["mt_num_threads"] = mt.num_threads;
    summary["mt_sampler"] = mt.sampler;
    summary["mt_prefix_cache"] = mt.prefix_cache;
    summary["mt_max_num_tokens"] = cfg["mt"].value("max_num_tokens", 384);
    mt_ready = true;
    return true;
  }

  void warm(const std::string& src, const std::string& tgt) {
    json s = json::object();
    mt.chat(prompts["system"][src + "-" + tgt], "xin chào", s);
    if (src == "vi" && punct_pass) mt.chat(prompts["punct"]["vi"], "xin chào", s);
    if (src == "vi" && !punct_pass && prompts.contains("system_lower"))
      mt.chat(prompts["system_lower"][src + "-" + tgt], "xin chào", s);
  }

  // text -> (punctuation pass) -> translation; fills o
  std::string translate(const std::string& text, const std::string& src, const std::string& tgt, bool from_asr, json& o) {
    std::string mt_in = text;
    if (from_asr) {
      auto t0 = Clock::now();
      if (punct_pass && src == "vi" && all_caps(text) && !text.empty()) {
        std::string low = lower_u8(text);
        json st = json::object();
        std::string p = mt.chat(prompts["punct"]["vi"], low, st);
        mt_in = (!p.empty() && words(p) == words(low)) ? capitalize_first(p) : prep_asr_text(text, src, prompts);
        o["punct_ms"] = ms_since(t0);
      } else {
        mt_in = prep_asr_text(text, src, prompts);
      }
      o["mt_in"] = mt_in;
    }
    // punct_pass=false: one Gemma call with a prompt that says the input is lowercase/unpunctuated
    std::string key = src + "-" + tgt;
    bool lower_prompt = from_asr && !punct_pass && src == "vi" && all_caps(text) &&
                        prompts.contains("system_lower") && prompts["system_lower"].contains(key);
    json st = json::object();
    std::string tr = mt_in.empty() ? "" : mt.chat(lower_prompt ? prompts["system_lower"][key] : prompts["system"][key], mt_in, st);
    o["mt_ms"] = st.value("ms", 0.0);
    o["mt_stats"] = st;
    o["hyp"] = tr;
    return tr;
  }

  // full item: e2e / asr / mt / tts. wav may come from a file path or memory.
  json run(const json& it, const std::string& wav_bytes, const std::string& out_wav_path, std::string* out_wav) {
    std::string task = it.value("task", "e2e"), id = it.value("id", "");
    std::string src = it.value("src", ""), tgt = it.value("tgt", "");
    json o = {{"id", id}, {"task", task}, {"src", src}, {"tgt", tgt}};
    auto t_all = Clock::now();
    std::string text = it.value("text", "");
    if (task == "e2e" || task == "asr") {
      const SherpaOnnxWave* w = wav_bytes.empty() ? SherpaOnnxReadWave(it["wav"].get<std::string>().c_str())
                                                  : SherpaOnnxReadWaveFromBinaryData(wav_bytes.data(), wav_bytes.size());
      if (!w) { o["error"] = "cannot read wav (need PCM16 WAV)"; return o; }
      o["audio_s"] = double(w->num_samples) / w->sample_rate;
      auto t0 = Clock::now();
      text = asr[src]->run(w->samples, w->num_samples, w->sample_rate);
      o["asr_ms"] = ms_since(t0);
      o["asr"] = text;
      SherpaOnnxFreeWave(w);
    }
    if (task == "e2e" || task == "mt") text = translate(text, src, tgt, task == "e2e", o);
    if ((task == "e2e" || task == "tts") && !text.empty()) {
      auto t0 = Clock::now();
      double secs = 0;
      std::string wav = tts[tgt]->synth(text, &secs);
      o["tts_ms"] = ms_since(t0);
      o["tts_audio_s"] = secs;
      if (!out_wav_path.empty() && !wav.empty()) { std::ofstream f(out_wav_path, std::ios::binary); f.write(wav.data(), wav.size()); }
      if (out_wav) *out_wav = std::move(wav);
    }
    o["total_ms"] = ms_since(t_all);
    return o;
  }

  ~Pipeline() {
    for (auto& [l, t] : tts) {
      if (t->vf) vifasttts_engine_free(t->vf);
      if (t->st) SherpaOnnxDestroyOfflineTts(t->st);
    }
    for (auto& [l, r] : asr) SherpaOnnxDestroyOfflineRecognizer(r->rec);
    for (auto& [k, b] : mt.bases) {
      if (b.conv) litert_lm_conversation_delete(b.conv);
      litert_lm_conversation_config_delete(b.cc);
      litert_lm_session_config_delete(b.sc);
      litert_lm_sampler_params_delete(b.sp);
    }
    if (mt.engine) litert_lm_engine_delete(mt.engine);
    if (mt.settings) litert_lm_engine_settings_delete(mt.settings);
  }
};

static std::string b64(const std::string& in) {
  static const char* T = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  std::string out;
  out.reserve((in.size() + 2) / 3 * 4);
  size_t i = 0;
  for (; i + 2 < in.size(); i += 3) {
    uint32_t v = (uint8_t(in[i]) << 16) | (uint8_t(in[i + 1]) << 8) | uint8_t(in[i + 2]);
    out += T[v >> 18]; out += T[(v >> 12) & 63]; out += T[(v >> 6) & 63]; out += T[v & 63];
  }
  if (i < in.size()) {
    uint32_t v = uint8_t(in[i]) << 16;
    if (i + 1 < in.size()) v |= uint8_t(in[i + 1]) << 8;
    out += T[v >> 18]; out += T[(v >> 12) & 63];
    out += (i + 1 < in.size()) ? T[(v >> 6) & 63] : '=';
    out += '=';
  }
  return out;
}

static int serve(Pipeline& P, const std::string& host, int port, const std::string& web_root) {
  httplib::Server svr;
  std::mutex mu;  // models are not thread-safe: one request at a time
  svr.set_mount_point("/", web_root);
  svr.Get("/api/health", [&](const httplib::Request&, httplib::Response& res) {
    json h = P.summary;
    h["peak_rss_kb"] = status_kb("VmHWM:");
    h["rss_kb"] = status_kb("VmRSS:");
    h["langs"] = json::array();
    for (auto& [l, _] : P.asr) h["langs"].push_back(l);
    res.set_content(jdump(h), "application/json");
  });
  // POST /api/translate?src=vi&tgt=en   body: PCM16 WAV     -> JSON incl. base64 WAV of the translation
  svr.Post("/api/translate", [&](const httplib::Request& req, httplib::Response& res) {
    std::lock_guard<std::mutex> lk(mu);
    std::string src = req.get_param_value("src"), tgt = req.get_param_value("tgt");
    if (!P.load_lang(src, true, false) || !P.load_lang(tgt, false, true)) { res.status = 400; return; }
    std::string wav;
    json o;
    // keep every live input for later diagnosis (out/live/<n>_<src>-<tgt>.wav)
    static int live_n = 0;
    std::string live_path = P.cfg.value("live_dir", "/data/local/tmp/cabin/out/live") + "/" +
                            std::to_string(++live_n) + "_" + std::to_string(time(nullptr)) + "_" + src + "-" + tgt + ".wav";
    { std::ofstream lf(live_path, std::ios::binary); lf.write(req.body.data(), req.body.size()); }
    try {
      o = P.run({{"id", "live"}, {"task", "e2e"}, {"src", src}, {"tgt", tgt}}, req.body, "", &wav);
    } catch (const std::exception& e) {
      res.status = 500;
      res.set_content(jdump({{"error", e.what()}}), "application/json");
      return;
    }
    o["audio_b64"] = b64(wav);
    o["peak_rss_kb"] = status_kb("VmHWM:");
    o["live_wav"] = live_path;
    std::cerr << "live " << live_path << " asr=[" << o.value("asr", "") << "] " << o.value("total_ms", 0.0)
              << " ms: " << o.value("hyp", "") << "\n";
    res.set_content(jdump(o), "application/json");
  });
  // POST /api/text  {"src":"vi","tgt":"en","text":"..."}
  svr.Post("/api/text", [&](const httplib::Request& req, httplib::Response& res) {
    std::lock_guard<std::mutex> lk(mu);
    json in = json::parse(req.body, nullptr, false);
    if (in.is_discarded()) { res.status = 400; return; }
    std::string src = in.value("src", "vi"), tgt = in.value("tgt", "en");
    if (!P.load_lang(tgt, false, true)) { res.status = 400; return; }
    std::string wav;
    json o = P.run({{"id", "text"}, {"task", "mt"}, {"src", src}, {"tgt", tgt}, {"text", in.value("text", "")}}, "", "", nullptr);
    double secs = 0;
    auto t0 = Clock::now();
    wav = P.tts[tgt]->synth(o.value("hyp", ""), &secs);
    o["tts_ms"] = ms_since(t0);
    o["audio_b64"] = b64(wav);
    res.set_content(jdump(o), "application/json");
  });
  std::cerr << "serving on http://" << host << ":" << port << "  (web root " << web_root << ")\n";
  return svr.listen(host, port) ? 0 : 1;
}

// ---------------------------------------------------------------- main
int main(int argc, char** argv) {
  std::map<std::string, std::string> a;
  for (int i = 1; i + 1 < argc; i += 2) a[argv[i]] = argv[i + 1];
  if (!a.count("--config") || (!a.count("--manifest") && !a.count("--serve"))) {
    std::cerr << "usage: cabin_edge --config config.json --manifest in.jsonl [--out out.jsonl] [--wav-dir dir]\n"
                 "       cabin_edge --config config.json --serve 8080 [--langs vi,en] [--host 127.0.0.1]\n";
    return 2;
  }
  Pipeline P;
  P.cfg = json::parse(read_file(a["--config"]));
  {  // paths starting with "./" are relative to the config file's directory, so a bundle runs from any folder
    std::string cf = a["--config"];
    char buf[4096];
    std::string dir = cf.find('/') == std::string::npos ? "." : cf.substr(0, cf.rfind('/'));
    if (realpath(dir.c_str(), buf)) dir = buf;
    std::function<void(json&)> fix = [&](json& j) {
      if (j.is_string()) {
        std::string v = j.get<std::string>();
        if (v.rfind("./", 0) == 0) j = dir + v.substr(1);
        else if (v.find(",./") != std::string::npos) {  // comma-separated lists (rule_fsts)
          std::string o; size_t i = 0;
          while (i <= v.size()) { size_t k = v.find(',', i); if (k == std::string::npos) k = v.size();
            std::string e = v.substr(i, k - i); o += (o.empty() ? "" : ",") + (e.rfind("./", 0) == 0 ? dir + e.substr(1) : e); i = k + 1; }
          j = o;
        }
      } else if (j.is_object() || j.is_array()) {
        for (auto& x : j) fix(x);
      }
    };
    fix(P.cfg);
  }
  P.prompts = json::parse(read_file(P.cfg["prompts"].get<std::string>()));
  P.punct_pass = P.cfg.value("punct_pass", true);
  P.summary = {{"rss_base_kb", status_kb("VmRSS:")}};

  if (a.count("--serve")) {
    std::string langs = a.count("--langs") ? a["--langs"] : "vi,en";
    std::vector<std::string> ls;
    std::stringstream ss(langs);
    for (std::string l; std::getline(ss, l, ',');) ls.push_back(l);
    for (auto& l : ls) if (!P.load_lang(l, true, true)) return 1;
    if (!P.load_mt()) return 1;
    for (auto& s : ls) for (auto& t : ls) if (s != t && (s == "vi" || t == "vi")) P.warm(s, t);
    P.summary["rss_after_load_kb"] = status_kb("VmRSS:");
    std::cerr << "loaded: " << jdump(P.summary) << "\n";
    return serve(P, a.count("--host") ? a["--host"] : "127.0.0.1", std::stoi(a["--serve"]),
                 P.cfg.value("web_root", "/data/local/tmp/cabin/web"));
  }

  std::string wav_dir = a.count("--wav-dir") ? a["--wav-dir"] : "";
  std::ofstream outf(a.count("--out") ? a["--out"] : "/dev/stdout");
  std::vector<json> items;
  {
    std::ifstream mf(a["--manifest"]);
    std::string line;
    while (std::getline(mf, line))
      if (!line.empty()) items.push_back(json::parse(line));
  }
  bool need_mt = false;
  for (auto& it : items) {
    std::string task = it.value("task", "e2e");
    if (task == "e2e" || task == "mt") need_mt = true;
    if (!P.load_lang(it.value("src", ""), task == "e2e" || task == "asr", false)) return 1;
    if (!P.load_lang(it.value("tgt", ""), false, task == "e2e" || task == "tts")) return 1;
  }
  if (need_mt && !P.load_mt()) return 1;
  P.summary["rss_after_load_kb"] = status_kb("VmRSS:");
  std::cerr << "loaded: " << jdump(P.summary) << "\n";

  // warm-up: prefill + cache every system prompt used, so no measured item pays for it
  if (need_mt) {
    std::map<std::string, bool> seen;
    for (auto& it : items) {
      std::string task = it.value("task", "e2e"), key = it.value("src", "") + "-" + it.value("tgt", "");
      if ((task == "e2e" || task == "mt") && !seen[key]) { seen[key] = true; P.warm(it["src"], it["tgt"]); }
    }
  }
  for (auto& it : items) {
    std::string wp = wav_dir.empty() ? "" : wav_dir + "/" + it.value("id", "x") + ".wav";
    json o;
    try {
      o = P.run(it, "", wp, nullptr);
    } catch (const std::exception& e) {
      o = {{"id", it.value("id", "")}, {"error", std::string("exception: ") + e.what()}};
      std::cerr << "item " << it.value("id", "") << " failed: " << e.what() << "\n";
    }
    outf << jdump(o) << "\n";
    outf.flush();
  }
  P.summary["peak_rss_kb"] = status_kb("VmHWM:");
  outf << jdump(json({{"summary", P.summary}})) << "\n";
  std::cerr << "done: " << jdump(P.summary) << "\n";
  return 0;
}
