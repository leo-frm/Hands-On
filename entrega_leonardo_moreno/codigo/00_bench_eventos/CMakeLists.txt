cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(hands_on_eventos)

target_sources(app PRIVATE src/main.c src/bench.c)
target_sources_ifdef(CONFIG_APP_MODE_POLLING    app PRIVATE src/mode_polling.c)
target_sources_ifdef(CONFIG_APP_MODE_IRQ_THREAD app PRIVATE src/mode_irq_thread.c)
target_sources_ifdef(CONFIG_APP_MODE_WORKQUEUE  app PRIVATE src/mode_workqueue.c)
target_sources_ifdef(CONFIG_APP_MODE_ISR_ONLY   app PRIVATE src/mode_isr_only.c)