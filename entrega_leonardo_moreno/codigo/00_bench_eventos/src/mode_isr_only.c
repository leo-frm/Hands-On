#include "bench.h"

static struct gpio_callback button_cb;

const char *mode_name(void) { return "isr_only"; }

static void button_isr(const struct device *port, struct gpio_callback *cb,
						 gpio_port_pins_t pins) {
	uint32_t now = k_cycle_get_32();
	atomic_inc(&ev_detected);

	if (measuring) {
		lat_add(&lat_detect, now - t_stim);
		lat_add(&lat_process, now - t_stim);
	}
	app_process_event(); /* ANTI-PADRAO: processamento dentro da ISR */
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