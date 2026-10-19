#include "bench.h"

K_THREAD_STACK_DEFINE(poll_stack, 1024);
static struct k_thread poll_data;

const char *mode_name(void) { return "polling"; }

static void poll_thread(void *p1, void *p2, void *p3) {

	int last = 0;

	while (1) {
		int state = gpio_pin_get_dt(&button); /* 1 = pressionado */

		if (state > 0 && last == 0) { /* borda de subida */
			uint32_t now = k_cycle_get_32();
			atomic_inc(&ev_detected);

			if (measuring) {
				lat_add(&lat_detect, now - t_stim);
				lat_add(&lat_process, now - t_stim);
			}
			app_process_event();
		}
		last = state;

		k_msleep(CONFIG_APP_POLL_PERIOD_MS);
	}
}

int mode_start(void) {
	k_tid_t tid = k_thread_create(
			&poll_data, poll_stack, K_THREAD_STACK_SIZEOF(poll_stack), poll_thread,
			NULL, NULL, NULL, CONFIG_APP_WORKER_PRIORITY, 0, K_NO_WAIT);

	k_thread_name_set(tid, "poll");
	return 0;
}