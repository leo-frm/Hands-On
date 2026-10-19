# Entrega: Hands-on Zephyr (Polling × Interrupção × Work Queue)

Leonardo Moreno, NUSP 13654481

```
entrega_leonardo_moreno/
├── codigo/
│   ├── 00_bench_eventos/      projeto-base do curso (Exps. 1 a 7), sem alterações
│   ├── 01_polling/            desafio final (Exp. 8), versão polling
│   ├── 02_interrupt_thread/   desafio final, versão ISR + thread + semáforo
│   ├── 03_workqueue/          desafio final, versão ISR + work queue
│   └── exp0_blink_test/       validação do ambiente (Exp. 0)
├── logs/                      logs brutos (linhas CSV), saídas do build, ram/rom_report, traces de GPIO
├── resultados.xlsx            dados extraídos dos logs, tabelas da apostila e gráficos
├── relatorio.pdf              relatório (estrutura da seção 19.2)
└── emulacao/                  patch do QEMU e scripts que compilam, executam e analisam
```

## Origem dos dados

Os experimentos rodaram em um **ESP32 emulado**, não em placa física:

- o firmware é o binário real do `west build -b esp32_devkitc/esp32/procpu` (Zephyr 4.5.0-rc2, SDK 1.0.1);
- ele roda no QEMU da Espressif com um modelo de GPIO acrescentado (`emulacao/qemu-esp32-gpio.patch`): registradores de saída/entrada, interrupção por borda, jumper GPIO18 → GPIO4 e botão roteirizado;
- o tempo é virtual e determinístico (`-icount shift=2`, 4 ns por instrução);
- a memória (Flash/RAM) vem do build real.

Cada log começa com um cabeçalho que identifica a origem e a configuração. A seção 3 do relatório
descreve o método, a validação e as limitações.

## Reprodução

```bash
# 1) QEMU: espressif/qemu (esp-develop) + patch, alvo xtensa-softmmu
git apply emulacao/qemu-esp32-gpio.patch && ./configure --target-list=xtensa-softmmu && ninja
# 2) compilar e executar (workspace west com o manifesto do curso)
python3 emulacao/run_lab.py exp4          # ou exp1-3, exp5, exp6, exp7, exp8
# 3) planilha, figuras e relatório
python3 emulacao/analisar.py && python3 emulacao/figuras.py && python3 emulacao/gerar_relatorio.py
```

Em uma placa real, os mesmos projetos são compilados e gravados com `west build` e `west flash`.
