// A poor man's profiler for the native Windows build: JWEMU_SAMPLE=file samples
// the thread that called start_sampler() every millisecond and, at exit, writes
// the instruction pointers it saw, most frequent first.  Symbolise with
//   nm -C -n jwemu.exe   (or addr2line -f -C -e jwemu.exe ADDR)
// -pg would do the same job, but writes nothing when the process leaves through
// _Exit, which is how both the window and the headless runs end.
#ifdef _WIN32
#include <windows.h>
#include <mmsystem.h>

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <thread>
#include <vector>

namespace {
std::atomic<bool> g_stop{false};
bool g_done = false;
std::map<unsigned long long, unsigned> g_hits;
std::thread g_thread;
const char* g_path = nullptr;

void dump_impl() {
    if (!g_path || g_done) return;
    g_done = true;
    g_stop = true;
    if (g_thread.joinable()) g_thread.join();
    std::FILE* f = std::fopen(g_path, "w");
    if (!f) return;
    std::vector<std::pair<unsigned, unsigned long long>> v;
    unsigned total = 0;
    for (auto& kv : g_hits) { v.push_back({kv.second, kv.first}); total += kv.second; }
    std::sort(v.rbegin(), v.rend());
    std::fprintf(f, "total %u\n", total);
    for (auto& e : v) std::fprintf(f, "%u %llx\n", e.first, e.second);
    std::fclose(f);
}
}  // namespace

void sampler_dump() { dump_impl(); }

void start_sampler() {
    g_path = std::getenv("JWEMU_SAMPLE");
    if (!g_path) return;
    HANDLE self = nullptr;
    DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(), &self, 0, FALSE,
                    DUPLICATE_SAME_ACCESS);
    const unsigned long long base = reinterpret_cast<unsigned long long>(GetModuleHandleW(nullptr));
    timeBeginPeriod(1);
    g_thread = std::thread([self, base] {
        while (!g_stop) {
            Sleep(1);
            if (SuspendThread(self) == static_cast<DWORD>(-1)) continue;
            CONTEXT ctx;
            ctx.ContextFlags = CONTEXT_CONTROL;
            #if defined(_M_ARM64) || defined(__aarch64__)
            if (GetThreadContext(self, &ctx)) ++g_hits[ctx.Pc - base];
#else
            if (GetThreadContext(self, &ctx)) ++g_hits[ctx.Rip - base];
#endif
            ResumeThread(self);
        }
    });
    std::atexit(dump_impl);
}
#else
void start_sampler() {}
void sampler_dump() {}
#endif
