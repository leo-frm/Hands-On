#include "bench.h"

atomic_t ev_generated;
atomic_t ev_detected;
atomic_t ev_processed;
volatile bool measuring;
volatile uint32_t t_stim;
volatile uint32_t hb_max_dt;
struct lat_stat lat_detect, lat_handoff, lat_process, lat_proc_dur;

void lat_reset(struct lat_stat *s) {
	s->n = 0U;
	s->min = UINT32_MAX;
	s->max = 0U;
	s->sum = 0U;
}

void lat_add(struct lat_stat *s, uint32_t cycles) {
	s->n++;
	s->sum += cycles;
	if (cycles < s->min) {
		s->min = cycles;
	}

	if (cycles > s->max) {
		s->max = cycles;
	}
}

void bench_reset_all(void) {
	lat_reset(&lat_detect);
	lat_reset(&lat_handoff);
	lat_reset(&lat_process);
	lat_reset(&lat_proc_dur);

	atomic_set(&ev_generated, 0);
	atomic_set(&ev_detected, 0);

	atomic_set(&ev_processed, 0);

	hb_max_dt = 0U;
}

#define US_I(ns) ((uint32_t)((ns) / 1000ULL))

#define US_F(ns) ((uint32_t)(((ns) % 1000ULL) / 10ULL))

void lat_print(const char *name, const struct lat_stat *s) {
	if (s->n == 0U) {
		printk("%-13s: sem amostras\n", name);
		return;
	}

	uint64_t mn = k_cyc_to_ns_floor64(s->min);
	uint64_t av = k_cyc_to_ns_floor64(s->sum / s->n);
	uint64_t mx = k_cyc_to_ns_floor64(s->max);

	printk("%-13s: n=%-4u min=%u.%02u  med=%u.%02u  max=%u.%02u  (us)\n", name,
				 s->n, US_I(mn), US_F(mn), US_I(av), US_F(av), US_I(mx), US_F(mx));

	printk("CSV,LAT,%s,%s,%u,%u,%u,%u\n", mode_name(), name, s->n, (uint32_t)mn,
				 (uint32_t)av, (uint32_t)mx);
}

/* Tratamento do evento: identico nas quatro arquiteturas */
void app_process_event(void) {
	uint32_t t0 = k_cycle_get_32();

	atomic_inc(&ev_processed);

	gpio_pin_toggle_dt(&led);

	if (CONFIG_APP_PROCESSING_US > 0) {
		k_busy_wait(CONFIG_APP_PROCESSING_US); /* carga de CPU */
	}

#ifdef CONFIG_APP_VERBOSE
	printk("evento processado #%ld\n", (long)atomic_get(&ev_processed));
#endif

	if (measuring) {
		lat_add(&lat_proc_dur, k_cycle_get_32() - t0);
	}
}

#ifdef CONFIG_APP_HEARTBEAT

/* Thread periodica de alta prioridade: mede o quanto o escalonamento
 * e atrasado (ex.: por uma ISR longa). Baseline ~1-2 ms (1 tick). */
K_THREAD_STACK_DEFINE(hb_stack, 1024);

static struct k_thread hb_data;

static void hb_thread(void *p1, void *p2, void *p3) {
	uint32_t last = k_cycle_get_32();

	while (1) {
		k_msleep(1);
		uint32_t now = k_cycle_get_32();
		uint32_t dt = now - last;
		last = now;

		if (measuring && dt > hb_max_dt) {
			hb_max_dt = dt;
		}
	}
}

void heartbeat_start(void) {
	k_tid_t tid =
			k_thread_create(&hb_data, hb_stack, K_THREAD_STACK_SIZEOF(hb_stack),
											hb_thread, NULL, NULL, NULL, 0, 0, K_NO_WAIT);

	k_thread_name_set(tid, "heartbeat");
}

#else

void heartbeat_start(void) {}

#endif