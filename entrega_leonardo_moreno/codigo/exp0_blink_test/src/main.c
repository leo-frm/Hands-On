#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>

#define ZU DT_PATH(zephyr_user)

static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(ZU, led_gpios);

int main(void)
{
	if (!gpio_is_ready_dt(&led)) {
		return 0;
	}
	if (gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE) < 0) {
		return 0;
	}
	while (1) {
		gpio_pin_toggle_dt(&led);
		k_msleep(1000);
	}
	return 0;
}
