cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(desafio_workqueue)

# Desafio final (Exp. 8): mesma instrumentacao do projeto-base, um unico mecanismo
target_sources(app PRIVATE src/main.c src/bench.c src/mode_workqueue.c)
