/*
 * anomaly_engine.cpp - Anomaly Detection Engine
 *
 * Maintains a rolling window per sensor channel and flags a reading
 * as an anomaly when it deviates too many standard deviations from
 * the recent rolling mean (a simple, fast, explainable statistical
 * process control approach -- the same idea behind SPC control
 * charts used on real fab lines).
 *
 * Exposed via a plain C ABI (extern "C") so Python can load this as
 * a shared library with ctypes without needing a C++-aware binding
 * layer.
 */

#include <deque>
#include <cmath>
#include <cstddef>

namespace {

struct Channel {
    std::deque<float> window;
    size_t max_size;
    explicit Channel(size_t sz = 50) : max_size(sz) {}
};

constexpr int kNumChannels = 4;
Channel g_channels[kNumChannels];
const char *g_names[kNumChannels] = {"Temperature", "Pressure", "Vibration", "Voltage"};

void rolling_stats(const std::deque<float> &w, double &mean, double &stddev) {
    double sum = 0.0;
    for (float v : w) sum += v;
    mean = sum / static_cast<double>(w.size());

    double sq_sum = 0.0;
    for (float v : w) sq_sum += (v - mean) * (v - mean);
    stddev = std::sqrt(sq_sum / static_cast<double>(w.size()));
}

} // namespace

extern "C" {

void init_engine(int window_size) {
    for (int i = 0; i < kNumChannels; ++i) {
        g_channels[i] = Channel(static_cast<size_t>(window_size));
    }
}

/*
 * Feeds one new value into channel_id's rolling window and checks
 * whether it is an anomaly relative to that window.
 *
 * severity_out: 0 = none, 1 = warning, 2 = critical
 * Returns 1 if any anomaly (warning or critical) was flagged, else 0.
 */
int check_anomaly(int channel_id, float value, double sigma_warn,
                   double sigma_crit, int *severity_out) {
    *severity_out = 0;
    if (channel_id < 0 || channel_id >= kNumChannels) return 0;

    Channel &ch = g_channels[channel_id];
    ch.window.push_back(value);
    if (ch.window.size() > ch.max_size) ch.window.pop_front();

    if (ch.window.size() < 10) return 0; /* warm-up period, not enough history */

    double mean, stddev;
    rolling_stats(ch.window, mean, stddev);
    if (stddev < 1e-6) return 0; /* channel is flat, nothing to compare against */

    double z = std::fabs(static_cast<double>(value) - mean) / stddev;
    if (z >= sigma_crit) { *severity_out = 2; return 1; }
    if (z >= sigma_warn)  { *severity_out = 1; return 1; }
    return 0;
}

const char *channel_name(int channel_id) {
    if (channel_id < 0 || channel_id >= kNumChannels) return "unknown";
    return g_names[channel_id];
}

} // extern "C"
