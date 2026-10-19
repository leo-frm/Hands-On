#include "bench.h"
#include <zephyr/debug/thread_analyzer.h>
#include <zephyr/kernel.h>

#define ZU DT_PATH(zephyr_user)

const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(ZU, led_gpios);
const struct gpio_dt_spec button = GPIO_DT_SPEC_GET(ZU, button_gpios);
const struct gpio_dt_spec stim = GPIO_DT_SPEC_GET(ZU, stim_gpios);

BUILD_ASSERT(CONFIG_APP_PULSE_WIDTH_MS < CONFIG_APP_EVENT_PERIOD_MS,
						 "APP_PULSE_WIDTH_MS deve ser menor que APP_EVENT_PERIOD_MS");

#ifdef CONFIG_APP_STIMULUS
/* Gera um pulso no pino de estimulo e espera o restante do periodo */
static void pulse(void) {
	t_stim = k_cycle_get_32(); /* <- ponto t_stim */
	atomic_inc(&ev_generated);
	gpio_pin_set_dt(&stim, 1);
	k_msleep(CONFIG_APP_PULSE_WIDTH_MS);
	gpio_pin_set_dt(&stim, 0);
	k_msleep(CONFIG_APP_EVENT_PERIOD_MS - CONFIG_APP_PULSE_WIDTH_MS);
}

static void print_report(const k_thread_runtime_stats_t *a,
												 const k_thread_runtime_stats_t *b, int64_t window_ms) {
	uint64_t total = b->execution_cycles - a->execution_cycles;
	uint64_t idle = 0U;

#ifdef CONFIG_SCHED_THREAD_USAGE_ALL
	idle = b->idle_cycles - a->idle_cycles;
#endif

	/* CPU ocupada em centesimos de % (0..10000) */
	uint32_t busy =
			(total > idle) ? (uint32_t)(((total - idle) * 10000ULL) / total) : 0U;

	/* CPU estimada so a partir do tempo em app_process_event() */
	uint64_t proc_ns = k_cyc_to_ns_floor64(lat_proc_dur.sum);
	uint32_t est = (uint32_t)(proc_ns / ((uint64_t)window_ms * 100ULL));
	uint32_t generated = (uint32_t)atomic_get(&ev_generated);
	uint32_t detected = (uint32_t)atomic_get(&ev_detected);
	uint32_t processed = (uint32_t)atomic_get(&ev_processed);

	printk("\n===== RELATORIO (%s) =====\n", mode_name());
	printk("janela               : %lld ms\n", window_ms);
	printk("eventos gerados      : %u\n", generated);
	printk("eventos detectados   : %u\n", detected);
	printk("eventos processados  : %u\n", processed);
	printk("eventos perdidos     : %u\n",
				 generated > processed ? generated - processed : 0U);

	lat_print("lat_detect", &lat_detect);
	lat_print("lat_handoff", &lat_handoff);
	lat_print("lat_process", &lat_process);
	lat_print("lat_proc_dur", &lat_proc_dur);

	printk("CPU ocupada (kernel) : %u.%02u %%\n", busy / 100U, busy % 100U);
	printk("CPU estimada (proc.) : %u.%02u %%\n", est / 100U, est % 100U);

#ifdef CONFIG_APP_HEARTBEAT
	uint64_t hb = k_cyc_to_ns_floor64(hb_max_dt);
	printk("heartbeat: maior intervalo = %u.%02u ms (baseline ~1-2 ms)\n",
				 (uint32_t)(hb / 1000000ULL), (uint32_t)((hb % 1000000ULL) / 10000ULL));
#endif

	printk("sizeof(k_thread)=%u  sizeof(k_sem)=%u  sizeof(k_work)=%u  "
				 "sizeof(k_work_q)=%u  (bytes)\n",
				 (unsigned int)sizeof(struct k_thread),
				 (unsigned int)sizeof(struct k_sem),
				 (unsigned int)sizeof(struct k_work),
				 (unsigned int)sizeof(struct k_work_q));

	printk("CSV,SUM,%s,poll_ms=%d,proc_us=%d,period_ms=%d,pulse_ms=%d,"
				 "gen=%u,det=%u,proc=%u,cpu_x100=%u,cpu_est_x100=%u\n",
				 mode_name(), CONFIG_APP_POLL_PERIOD_MS, CONFIG_APP_PROCESSING_US,
				 CONFIG_APP_EVENT_PERIOD_MS, CONFIG_APP_PULSE_WIDTH_MS, generated,
				 detected, processed, busy, est);

#ifdef CONFIG_THREAD_ANALYZER
	printk("\n----- Thread Analyzer -----\n");
	thread_analyzer_print(0); /* versoes antigas: thread_analyzer_print() */
#endif
}

static void run_benchmark(void) {
	k_thread_runtime_stats_t s0, s1;

	printk("Aquecimento: %d eventos...\n", CONFIG_APP_WARMUP_EVENTS);
	for (int i = 0; i < CONFIG_APP_WARMUP_EVENTS; i++) {
		pulse();
	}
	k_msleep(100 + CONFIG_APP_PROCESSING_US / 1000);

	bench_reset_all();

	k_thread_runtime_stats_all_get(&s0);

	int64_t t0 = k_uptime_get();

	measuring = true;

	printk("Medindo: %d eventos, periodo %d ms...\n", CONFIG_APP_NUM_EVENTS,
				 CONFIG_APP_EVENT_PERIOD_MS);

	for (int i = 0; i < CONFIG_APP_NUM_EVENTS; i++) {
		pulse();
	}

	k_msleep(100 + CONFIG_APP_PROCESSING_US / 1000); /* ultimo evento */

	measuring = false;

	k_thread_runtime_stats_all_get(&s1);

	int64_t window = k_uptime_get() - t0;

	print_report(&s0, &s1, window);
}
#endif /* CONFIG_APP_STIMULUS */

int main(void) {
	k_thread_priority_set(k_current_get(), CONFIG_APP_MAIN_PRIORITY);

	if (!gpio_is_ready_dt(&led) || !gpio_is_ready_dt(&button) ||
			!gpio_is_ready_dt(&stim)) {
		printk("ERRO: GPIO nao esta pronto (verifique o app.overlay)\n");
		return 0;
	}

	if (gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE) < 0 ||
			gpio_pin_configure_dt(&stim, GPIO_OUTPUT_INACTIVE) < 0 ||
			gpio_pin_configure_dt(&button, GPIO_INPUT) < 0) {
		printk("ERRO: falha ao configurar os GPIOs\n");
		return 0;
	}

	bench_reset_all();

	printk("\n*** Hands-on eventos | modo: %s ***\n", mode_name());

	printk("hw cycles/s = %u  | tick = %d Hz\n",
				 (uint32_t)sys_clock_hw_cycles_per_sec(),
				 CONFIG_SYS_CLOCK_TICKS_PER_SEC);

	heartbeat_start();

	if (mode_start() < 0) {
		printk("ERRO: falha ao iniciar o modo\n");
		return 0;
	}

#ifdef CONFIG_APP_STIMULUS
	run_benchmark();
#else

	/* Modo manual: use o botao fisico; status a cada 10 s */
	while (1) {
		k_msleep(10000);
		printk("[status] eventos processados = %ld\n",
					 (long)atomic_get(&ev_processed));

#ifdef CONFIG_THREAD_ANALYZER
		thread_analyzer_print(0);
#endif
	}

#endif
	return 0;
}