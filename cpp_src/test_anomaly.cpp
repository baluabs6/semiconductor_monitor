// Native tests for the anomaly engine. Built with ASan+UBSan in CI:
//   g++ -std=c++17 -g -fsanitize=address,undefined cpp_src/anomaly_engine.cpp cpp_src/test_anomaly.cpp -o test_anomaly
#include <cassert>
#include <cmath>
#include <cstdio>
#include <limits>
#include <string>
#include <random>

extern "C" {
void init_engine(int window_size);
int check_anomaly(int channel_id, float value, double sigma_warn, double sigma_crit, int *severity_out);
const char *channel_name(int channel_id);
}

static void feed_normal(std::mt19937 &rng, int n) {
    std::normal_distribution<float> d(70.0f, 2.0f);
    int sev;
    for (int i = 0; i < n; ++i) check_anomaly(0, d(rng), 3.0, 5.0, &sev);
}

int main() {
    std::mt19937 rng(42);
    int sev = 0;

    // 1. warm-up: never flags with < 10 samples
    init_engine(50);
    for (int i = 0; i < 9; ++i) assert(check_anomaly(0, 70.0f + i, 3.0, 5.0, &sev) == 0);

    // 2. a large spike right after warm-up is CRITICAL (regression: used to be capped below 5 sigma)
    init_engine(50);
    feed_normal(rng, 12);
    assert(check_anomaly(0, 200.0f, 3.0, 5.0, &sev) == 1 && sev == 2);

    // 3. faults do not mask the next fault
    init_engine(50);
    feed_normal(rng, 60);
    for (int i = 0; i < 20; ++i) assert(check_anomaly(0, 200.0f, 3.0, 5.0, &sev) == 1);

    // 4. NaN / Inf are flagged critical and do not poison the window
    init_engine(50);
    feed_normal(rng, 60);
    float nan = std::numeric_limits<float>::quiet_NaN(), inf = std::numeric_limits<float>::infinity();
    assert(check_anomaly(0, nan, 3.0, 5.0, &sev) == 1 && sev == 2);
    assert(check_anomaly(0, inf, 3.0, 5.0, &sev) == 1 && sev == 2);
    assert(check_anomaly(0, 500.0f, 3.0, 5.0, &sev) == 1);      // detection still works afterwards
    assert(check_anomaly(0, 70.0f, 3.0, 5.0, &sev) == 0);

    // 5. invalid channel ids are rejected safely
    assert(check_anomaly(-1, 1.0f, 3.0, 5.0, &sev) == 0 && sev == 0);
    assert(check_anomaly(99, 1.0f, 3.0, 5.0, &sev) == 0 && sev == 0);
    assert(std::string(channel_name(99)) == "unknown");

    // 6. flat channel: nothing to compare against, no divide-by-zero
    init_engine(50);
    for (int i = 0; i < 100; ++i) assert(check_anomaly(1, 1.0f, 3.0, 5.0, &sev) == 0);

    // 7. window size 1 / tiny sizes do not crash
    init_engine(1);
    for (int i = 0; i < 30; ++i) check_anomaly(2, static_cast<float>(i), 3.0, 5.0, &sev);

    std::puts("anomaly engine tests passed");
    return 0;
}
