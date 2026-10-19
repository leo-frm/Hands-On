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
├── logs/                      logs brutos (linhas CSV), saídas do build, ram/rom_report, registro dos pinos
├── resultados.xlsx            dados extraídos dos logs, tabelas da apostila e gráficos
├── relatorio.pdf              relatório (estrutura da seção 19.2)
├── relatorio.docx             o mesmo relatório em Word
└── emulacao/                  ferramentas de execução e análise
```

Ambiente: Zephyr 4.5.0-rc2, Zephyr SDK 1.0.1, placa `esp32_devkitc/esp32/procpu`. A execução foi
feita em ESP32 emulado (QEMU Espressif), com os detalhes no Apêndice B do relatório.

## Reprodução

```bash
# 1) QEMU: espressif/qemu (esp-develop) + patch, alvo xtensa-softmmu
git apply emulacao/qemu-esp32-gpio.patch && ./configure --target-list=xtensa-softmmu && ninja
# 2) compilar e executar (workspace west com o manifesto do curso)
python3 emulacao/run_lab.py exp4          # ou exp1-3, exp5, exp6, exp7, exp8
# 3) planilha, figuras e relatório
python3 emulacao/analisar.py && python3 emulacao/figuras.py && python3 emulacao/gerar_relatorio.py
# 4) .docx a partir do HTML do relatório
pandoc relatorio.html -t docx --reference-doc=emulacao/modelo_docx.docx \
       --lua-filter=emulacao/filtro_docx.lua -o bruto.docx
python3 emulacao/pos_processar_docx.py bruto.docx relatorio.docx
```

Em uma placa, os mesmos projetos são compilados e gravados com `west build` e `west flash`.
