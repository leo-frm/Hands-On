#ifndef BENCH_H_

#define BENCH_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>

/* GPIOs (definidos em main.c a partir do app.overlay) */

extern const struct gpio_dt_spec led;
extern const struct gpio_dt_spec button;
extern const struct gpio_dt_spec stim;

/* Contadores e estado da medicao */

extern atomic_t ev_generated;       /* pulsos gerados pelo estimulo        */
extern atomic_t ev_detected;        /* eventos vistos (ISR ou polling)     */
extern atomic_t ev_processed;       /* eventos efetivamente processados    */
extern volatile bool measuring;     /* true dentro da janela de medicao    */
extern volatile uint32_t t_stim;    /* instante do estimulo (ciclos)       */
extern volatile uint32_t hb_max_dt; /* maior intervalo do heartbeat        */

struct lat_stat {
  uint32_t n;
  uint32_t min;
  uint32_t max;
  uint64_t sum;
};

extern struct lat_stat lat_detect;   /* estimulo -> deteccao (ISR/polling)  */
extern struct lat_stat lat_handoff;  /* ISR -> inicio do tratamento         */
extern struct lat_stat lat_process;  /* estimulo -> inicio do tratamento    */
extern struct lat_stat lat_proc_dur; /* duracao do tratamento               */

void lat_reset(struct lat_stat *s);
void lat_add(struct lat_stat *s, uint32_t cycles);
void lat_print(const char *name, const struct lat_stat *s);
void bench_reset_all(void);
void app_process_event(void); /* tratamento do evento (igual nos modos) */
void heartbeat_start(void);
int mode_start(void); /* implementado por cada modo             */
const char *mode_name(void);

#endif /* BENCH_H_ */