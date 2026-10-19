#include "bench.h"

static struct gpio_callback button_cb;
static volatile uint32_t t_isr;

const char *mode_name(void) { return "workqueue"; }

/* Executado na thread da system workqueue (nao na ISR) */

static void button_work_handler(struct k_work *work) {
	uint32_t now = k_cycle_get_32(); /* <- ponto t_ini */
	if (measuring) {
		lat_add(&lat_handoff, now - t_isr);
		lat_add(&lat_process, now - t_stim);
	}
	app_process_event();
}

K_WORK_DEFINE(button_work, button_work_handler);
/* ISR: curta. Apenas registra o tempo e submete o work item. */
static void button_isr(const struct device *port, struct gpio_callback *cb,
											 gpio_port_pins_t pins) {
	uint32_t now = k_cycle_get_32(); /* <- ponto t_isr */
	t_isr = now;
	atomic_inc(&ev_detected);
	if (measuring) {
		lat_add(&lat_detect, now - t_stim);
	}

	k_work_submit(&button_work); /* retorna 0 se ja estava pendente */
}

int mode_start(void) {
	int ret;
	gpio_init_callback(&button_cb, button_isr, BIT(button.pin));
	ret = gpio_add_callback(button.port, &button_cb);
	if (ret < 0) {
		return ret;
	}

	return gpio_pin_interrupt_configure_dt(&button, GPIO_INT_EDGE_TO_ACTIVE);
}