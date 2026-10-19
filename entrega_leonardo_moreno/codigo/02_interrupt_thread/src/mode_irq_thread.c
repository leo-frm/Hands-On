#include "bench.h"

K_SEM_DEFINE(button_sem, 0, 1); /* inicial 0, limite 1 */

K_THREAD_STACK_DEFINE(worker_stack, 1024);

static struct k_thread worker_data;
static struct gpio_callback button_cb;
static volatile uint32_t t_isr;

const char *mode_name(void) { return "irq_thread"; }

/* ISR: curta. Apenas registra o tempo e sinaliza o semaforo. */
static void button_isr(const struct device *port, struct gpio_callback *cb,
											 gpio_port_pins_t pins) {
	uint32_t now = k_cycle_get_32(); /* <- ponto t_isr */
	t_isr = now;

	atomic_inc(&ev_detected);

	if (measuring) {
		lat_add(&lat_detect, now - t_stim);
	}
	k_sem_give(&button_sem);
}

static void worker(void *p1, void *p2, void *p3) {
	while (1) {
		k_sem_take(&button_sem, K_FOREVER); /* bloqueada sem evento */

		uint32_t now = k_cycle_get_32(); /* <- ponto t_ini */
		if (measuring) {
			lat_add(&lat_handoff, now - t_isr);
			lat_add(&lat_process, now - t_stim);
		}
		app_process_event();
	}
}

int mode_start(void) {
	int ret;
	k_tid_t tid = k_thread_create(
			&worker_data, worker_stack, K_THREAD_STACK_SIZEOF(worker_stack), worker,
			NULL, NULL, NULL, CONFIG_APP_WORKER_PRIORITY, 0, K_NO_WAIT);

	k_thread_name_set(tid, "worker");
	gpio_init_callback(&button_cb, button_isr, BIT(button.pin));

	ret = gpio_add_callback(button.port, &button_cb);

	if (ret < 0) {
		return ret;
	}

	return gpio_pin_interrupt_configure_dt(&button, GPIO_INT_EDGE_TO_ACTIVE);
}