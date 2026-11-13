// LiteRT-LM C API 1.0 (status-code ABI, used by cabin_edge.cc) implemented on top of the pre-1.0 C ABI of
// the NPU-enabled LiteRT-LM 0.18 runtime (libLiteRtLm.so from flutter_edge_ai native-v0.18.0-e, the runtime
// of the Google x Qualcomm VENTUNO Q hackathon). 0.18 returns objects / values directly; 1.0 returns a
// LiteRtLmStatusCode and writes through out-params. The 0.18 library is dlopen'ed (RTLD_LOCAL) so its
// identically named symbols never clash with these wrappers. Only the functions cabin_edge uses are covered.
#include <dlfcn.h>
#include <cstdio>
#include <cstdlib>

#include "conversation.h"
#include "engine.h"
#include "error_reporter.h"

namespace {
void* lib() {
  static void* h = [] {
    const char* p = getenv("CABIN_LITERT_LM_018");
    void* x = dlopen(p ? p : "libLiteRtLm.so", RTLD_NOW | RTLD_LOCAL);
    if (!x) { fprintf(stderr, "[compat018] dlopen libLiteRtLm.so failed: %s\n", dlerror()); abort(); }
    return x;
  }();
  return h;
}
template <class F> F sym(const char* n) {
  void* s = dlsym(lib(), n);
  if (!s) { fprintf(stderr, "[compat018] missing symbol %s\n", n); abort(); }
  return reinterpret_cast<F>(s);
}
#define OLD(ret, name, ...) static auto f = sym<ret (*)(__VA_ARGS__)>(#name)
inline LiteRtLmStatusCode st(const void* p) { return p ? kLiteRtLmStatusOk : kLiteRtLmStatusUnknown; }
}  // namespace

extern "C" {
const char* litert_lm_get_last_error_message(void) { return "(LiteRT-LM 0.18 runtime: see its log above)"; }
void litert_lm_clear_last_error(void) {}

LiteRtLmStatusCode litert_lm_set_min_log_level(LiteRtLmLogSeverity level) {
  OLD(void, litert_lm_set_min_log_level, LiteRtLmLogSeverity); f(level); return kLiteRtLmStatusOk;
}

// ---- sampler / session
LiteRtLmStatusCode litert_lm_sampler_params_create(LiteRtLmSamplerType type, LiteRtLmSamplerParams** out) {
  OLD(LiteRtLmSamplerParams*, litert_lm_sampler_params_create, LiteRtLmSamplerType); *out = f(type); return st(*out);
}
void litert_lm_sampler_params_delete(LiteRtLmSamplerParams* p) {
  OLD(void, litert_lm_sampler_params_delete, LiteRtLmSamplerParams*); f(p);
}
LiteRtLmStatusCode litert_lm_sampler_params_set_top_k(LiteRtLmSamplerParams* p, int32_t v) {
  OLD(void, litert_lm_sampler_params_set_top_k, LiteRtLmSamplerParams*, int32_t); f(p, v); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_sampler_params_set_top_p(LiteRtLmSamplerParams* p, float v) {
  OLD(void, litert_lm_sampler_params_set_top_p, LiteRtLmSamplerParams*, float); f(p, v); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_sampler_params_set_temperature(LiteRtLmSamplerParams* p, float v) {
  OLD(void, litert_lm_sampler_params_set_temperature, LiteRtLmSamplerParams*, float); f(p, v); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_sampler_params_set_seed(LiteRtLmSamplerParams* p, int32_t v) {
  OLD(void, litert_lm_sampler_params_set_seed, LiteRtLmSamplerParams*, int32_t); f(p, v); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_session_config_create(LiteRtLmSessionConfig** out) {
  OLD(LiteRtLmSessionConfig*, litert_lm_session_config_create, void); *out = f(); return st(*out);
}
LiteRtLmStatusCode litert_lm_session_config_set_max_output_tokens(LiteRtLmSessionConfig* c, int n) {
  OLD(void, litert_lm_session_config_set_max_output_tokens, LiteRtLmSessionConfig*, int); f(c, n); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_session_config_set_sampler_params(LiteRtLmSessionConfig* c, const LiteRtLmSamplerParams* p) {
  OLD(void, litert_lm_session_config_set_sampler_params, LiteRtLmSessionConfig*, const LiteRtLmSamplerParams*);
  f(c, p); return kLiteRtLmStatusOk;
}
void litert_lm_session_config_delete(LiteRtLmSessionConfig* c) {
  OLD(void, litert_lm_session_config_delete, LiteRtLmSessionConfig*); f(c);
}

// ---- engine
LiteRtLmStatusCode litert_lm_engine_settings_create(const char* model, const char* backend, const char* vision,
                                                    const char* audio, LiteRtLmEngineSettings** out) {
  OLD(LiteRtLmEngineSettings*, litert_lm_engine_settings_create, const char*, const char*, const char*, const char*);
  *out = f(model, backend, vision, audio); return st(*out);
}
void litert_lm_engine_settings_delete(LiteRtLmEngineSettings* s) {
  OLD(void, litert_lm_engine_settings_delete, LiteRtLmEngineSettings*); f(s);
}
LiteRtLmStatusCode litert_lm_engine_settings_set_max_num_tokens(LiteRtLmEngineSettings* s, int n) {
  OLD(void, litert_lm_engine_settings_set_max_num_tokens, LiteRtLmEngineSettings*, int); f(s, n); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_engine_settings_set_num_threads(LiteRtLmEngineSettings* s, int n) {
  OLD(void, litert_lm_engine_settings_set_num_threads, LiteRtLmEngineSettings*, int); f(s, n); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_engine_settings_set_cache_dir(LiteRtLmEngineSettings* s, const char* d) {
  OLD(void, litert_lm_engine_settings_set_cache_dir, LiteRtLmEngineSettings*, const char*); f(s, d); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_engine_settings_set_litert_dispatch_lib_dir(LiteRtLmEngineSettings* s, const char* d) {
  OLD(void, litert_lm_engine_settings_set_litert_dispatch_lib_dir, LiteRtLmEngineSettings*, const char*);
  f(s, d); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_engine_settings_enable_benchmark(LiteRtLmEngineSettings* s) {
  OLD(void, litert_lm_engine_settings_enable_benchmark, LiteRtLmEngineSettings*); f(s); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_engine_settings_set_gpu_decode_steps_per_sync(LiteRtLmEngineSettings* s, int n) {
  OLD(void, litert_lm_engine_settings_set_gpu_decode_steps_per_sync, LiteRtLmEngineSettings*, int);
  f(s, n); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_engine_create(const LiteRtLmEngineSettings* s, LiteRtLmEngine** out) {
  OLD(LiteRtLmEngine*, litert_lm_engine_create, const LiteRtLmEngineSettings*); *out = f(s); return st(*out);
}
void litert_lm_engine_delete(LiteRtLmEngine* e) { OLD(void, litert_lm_engine_delete, LiteRtLmEngine*); f(e); }

// ---- benchmark info
void litert_lm_benchmark_info_delete(LiteRtLmBenchmarkInfo* b) {
  OLD(void, litert_lm_benchmark_info_delete, LiteRtLmBenchmarkInfo*); f(b);
}
LiteRtLmStatusCode litert_lm_benchmark_info_get_time_to_first_token(const LiteRtLmBenchmarkInfo* b, double* out) {
  OLD(double, litert_lm_benchmark_info_get_time_to_first_token, const LiteRtLmBenchmarkInfo*); *out = f(b);
  return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_benchmark_info_get_num_prefill_turns(const LiteRtLmBenchmarkInfo* b, size_t* out) {
  OLD(int, litert_lm_benchmark_info_get_num_prefill_turns, const LiteRtLmBenchmarkInfo*); int n = f(b);
  *out = n > 0 ? n : 0; return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_benchmark_info_get_num_decode_turns(const LiteRtLmBenchmarkInfo* b, size_t* out) {
  OLD(int, litert_lm_benchmark_info_get_num_decode_turns, const LiteRtLmBenchmarkInfo*); int n = f(b);
  *out = n > 0 ? n : 0; return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_benchmark_info_get_prefill_token_count_at(const LiteRtLmBenchmarkInfo* b, size_t i, size_t* out) {
  OLD(int, litert_lm_benchmark_info_get_prefill_token_count_at, const LiteRtLmBenchmarkInfo*, int);
  int n = f(b, int(i)); *out = n > 0 ? n : 0; return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_benchmark_info_get_decode_token_count_at(const LiteRtLmBenchmarkInfo* b, size_t i, size_t* out) {
  OLD(int, litert_lm_benchmark_info_get_decode_token_count_at, const LiteRtLmBenchmarkInfo*, int);
  int n = f(b, int(i)); *out = n > 0 ? n : 0; return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_benchmark_info_get_prefill_tokens_per_sec_at(const LiteRtLmBenchmarkInfo* b, size_t i, double* out) {
  OLD(double, litert_lm_benchmark_info_get_prefill_tokens_per_sec_at, const LiteRtLmBenchmarkInfo*, int);
  *out = f(b, int(i)); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_benchmark_info_get_decode_tokens_per_sec_at(const LiteRtLmBenchmarkInfo* b, size_t i, double* out) {
  OLD(double, litert_lm_benchmark_info_get_decode_tokens_per_sec_at, const LiteRtLmBenchmarkInfo*, int);
  *out = f(b, int(i)); return kLiteRtLmStatusOk;
}

// ---- conversation
LiteRtLmStatusCode litert_lm_conversation_config_create(LiteRtLmConversationConfig** out) {
  OLD(LiteRtLmConversationConfig*, litert_lm_conversation_config_create, void); *out = f(); return st(*out);
}
LiteRtLmStatusCode litert_lm_conversation_config_set_session_config(LiteRtLmConversationConfig* c, const LiteRtLmSessionConfig* s) {
  OLD(void, litert_lm_conversation_config_set_session_config, LiteRtLmConversationConfig*, const LiteRtLmSessionConfig*);
  f(c, s); return kLiteRtLmStatusOk;
}
LiteRtLmStatusCode litert_lm_conversation_config_set_system_message(LiteRtLmConversationConfig* c, const char* j) {
  OLD(void, litert_lm_conversation_config_set_system_message, LiteRtLmConversationConfig*, const char*);
  f(c, j); return kLiteRtLmStatusOk;
}
void litert_lm_conversation_config_delete(LiteRtLmConversationConfig* c) {
  OLD(void, litert_lm_conversation_config_delete, LiteRtLmConversationConfig*); f(c);
}
LiteRtLmStatusCode litert_lm_conversation_create(LiteRtLmEngine* e, LiteRtLmConversationConfig* c, LiteRtLmConversation** out) {
  OLD(LiteRtLmConversation*, litert_lm_conversation_create, LiteRtLmEngine*, LiteRtLmConversationConfig*);
  *out = f(e, c); return st(*out);
}
void litert_lm_conversation_delete(LiteRtLmConversation* c) {
  OLD(void, litert_lm_conversation_delete, LiteRtLmConversation*); f(c);
}
LiteRtLmStatusCode litert_lm_conversation_clone(LiteRtLmConversation* c, LiteRtLmConversation** out) {
  OLD(LiteRtLmConversation*, litert_lm_conversation_clone, LiteRtLmConversation*); *out = f(c); return st(*out);
}
LiteRtLmStatusCode litert_lm_conversation_send_message(LiteRtLmConversation* c, const char* msg, const char* extra,
                                                       const LiteRtLmConversationOptionalArgs* args,
                                                       LiteRtLmJsonResponse** out) {
  OLD(LiteRtLmJsonResponse*, litert_lm_conversation_send_message, LiteRtLmConversation*, const char*, const char*,
      const LiteRtLmConversationOptionalArgs*);
  *out = f(c, msg, extra, args); return st(*out);
}
void litert_lm_json_response_delete(LiteRtLmJsonResponse* r) {
  OLD(void, litert_lm_json_response_delete, LiteRtLmJsonResponse*); f(r);
}
LiteRtLmStatusCode litert_lm_json_response_get_string(const LiteRtLmJsonResponse* r, const char** out) {
  OLD(const char*, litert_lm_json_response_get_string, const LiteRtLmJsonResponse*); *out = f(r); return st(*out);
}
LiteRtLmStatusCode litert_lm_conversation_get_benchmark_info(LiteRtLmConversation* c, LiteRtLmBenchmarkInfo** out) {
  OLD(LiteRtLmBenchmarkInfo*, litert_lm_conversation_get_benchmark_info, LiteRtLmConversation*); *out = f(c);
  return st(*out);
}
}  // extern "C"
