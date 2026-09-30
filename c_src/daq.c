/*
 * daq.c - Data Acquisition module
 *
 * Simulates raw sensor reads from semiconductor fab / test equipment
 * (temperature, chamber pressure, vibration, supply voltage).
 * In a real deployment this file would talk to actual hardware
 * (SPI/I2C sensors, DAQ cards, SECS/GEM equipment interfaces, etc.)
 * but the interface exposed to Python stays identical either way.
 */

#include <stdlib.h>
#include <time.h>

typedef struct {
    float temperature;   /* degrees C   */
    float pressure;      /* normalized  */
    float vibration;     /* g-force     */
    float voltage;       /* volts       */
} SensorReading;

static int g_seeded = 0;

static float rand_range(float lo, float hi) {
    return lo + ((float)rand() / (float)RAND_MAX) * (hi - lo);
}

/* Call once at startup. Safe to call multiple times. */
void init_daq(unsigned int seed) {
    srand(seed);
    g_seeded = 1;
}

/*
 * Reads the current sensor values into `out`.
 * If inject_fault != 0, one channel is randomly pushed out of its
 * normal operating band to simulate a real fault condition
 * (overheating, pressure leak, bearing wear, brown-out, etc.)
 */
void read_sensors(SensorReading *out, int inject_fault) {
    if (!g_seeded) {
        init_daq((unsigned int)time(NULL));
    }

    out->temperature = rand_range(60.0f, 75.0f);
    out->pressure    = rand_range(1.0f, 1.2f);
    out->vibration   = rand_range(0.01f, 0.05f);
    out->voltage     = rand_range(3.25f, 3.35f);

    if (inject_fault) {
        switch (rand() % 4) {
            case 0: out->temperature += rand_range(20.0f, 45.0f); break;
            case 1: out->pressure    += rand_range(0.5f, 1.6f);   break;
            case 2: out->vibration   += rand_range(0.3f, 0.9f);   break;
            case 3: out->voltage     -= rand_range(0.5f, 1.1f);   break;
        }
    }
}
