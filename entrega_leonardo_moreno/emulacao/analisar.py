#!/usr/bin/env python3
"""Le os logs brutos (logs/*.log, *_build.txt, traces) e gera:
  - resultados.xlsx: dados brutos + tabelas da apostila (formulas) + graficos
  - figuras PNG para o relatorio (pasta passada em --fig)
"""
import argparse
import csv
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ENTREGA = HERE.parent
LOGS = ENTREGA / "logs"

RE_EXP = re.compile(r"^# Experimento: (\S+) \| execucao (\d+)")
RE_MODE = re.compile(r"modo: (\w+) \*\*\*")
RE_JANELA = re.compile(r"^janela\s+:\s+(\d+) ms")
RE_HB = re.compile(r"^heartbeat: maior intervalo = ([\d.]+) ms")
RE_THREAD = re.compile(
    r"^\s(\S+)\s+: STACK: unused\s+(\d+) usage\s+(\d+) / (\d+) \(\s*\d+ %\); CPU:\s+(\d+) %")
RE_MEM = re.compile(r"^\s*(FLASH|iram0_0_seg|dram0_0_seg|dram1_0_seg):\s+(\d+) (B|KB)")
RE_SIZEOF = re.compile(r"^sizeof\(k_thread\)=(\d+)\s+sizeof\(k_sem\)=(\d+)\s+"
                       r"sizeof\(k_work\)=(\d+)\s+sizeof\(k_work_q\)=(\d+)")


def parse_logs():
    lat, summ, threads, manual = [], [], [], []
    sizeof = None
    for log in sorted(LOGS.glob("*_run*.log")):
        lines = log.read_text(errors="replace").splitlines()
        m = RE_EXP.match(lines[2])
        exp, run = m.group(1), int(m.group(2))
        mode, janela, hb, block = None, None, None, []
        processed_verbose, status = 0, []
        for ln in lines:
            if (mm := RE_MODE.search(ln)):
                mode = mm.group(1)
            if (mm := RE_JANELA.match(ln)):
                janela = int(mm.group(1))
            if (mm := RE_HB.match(ln)):
                hb = float(mm.group(1))
            if (mm := RE_SIZEOF.match(ln)):
                sizeof = tuple(int(x) for x in mm.groups())
            if ln.startswith("Thread analyze"):
                block = []
            if (mm := RE_THREAD.match(ln)):
                block.append(mm.groups())
            if ln.startswith("evento processado #"):
                processed_verbose += 1
            if ln.startswith("[status] eventos processados = "):
                status.append(int(ln.rsplit("=", 1)[1]))
            if ln.startswith("CSV,LAT,"):
                p = ln.split(",")
                lat.append(dict(exp=exp, run=run, modo=p[2], metrica=p[3], n=int(p[4]),
                                min_ns=int(p[5]), med_ns=int(p[6]), max_ns=int(p[7])))
            if ln.startswith("CSV,SUM,"):
                p = ln.split(",")
                kv = dict(x.split("=") for x in p[3:])
                summ.append(dict(exp=exp, run=run, modo=p[2],
                                 **{k: int(v) for k, v in kv.items()}))
        if summ and summ[-1]["exp"] == exp and summ[-1]["run"] == run:
            summ[-1]["janela_ms"] = janela
            summ[-1]["hb_max_ms"] = hb
        for name, unused, used, total, cpu in block:
            threads.append(dict(exp=exp, run=run, thread=name, pilha_usada=int(used),
                                pilha_total=int(total), cpu_pct=int(cpu)))
        if exp.startswith("exp1-3"):
            trace = LOGS / f"{exp}_run{run}_gpio_trace.csv"
            presses = short = 0
            if trace.exists():
                rows = [(int(r["t_ns"]), r["gpio"], r["level"])
                        for r in csv.DictReader(trace.open())]
                down = None
                for t, g, lvl in rows:
                    if g != "4":
                        continue
                    if lvl == "0":
                        down = t
                    elif down is not None:
                        presses += 1
                        short += (t - down) < 10_000_000
                        down = None
            manual.append(dict(exp=exp, modo=mode, toques=presses, toques_curtos=short,
                               processados=status[-1] if status else processed_verbose,
                               status_10s=" / ".join(map(str, status[:3])),
                               pilha_evento=next((f"{u} / {t}" for n, _, u, t, _ in block
                                                  if n in ("poll", "worker", "sysworkq")), "")))
    return (pd.DataFrame(lat), pd.DataFrame(summ), pd.DataFrame(threads),
            pd.DataFrame(manual), sizeof)


def parse_builds():
    rows = []
    for b in sorted(LOGS.glob("*_build.txt")):
        exp = b.name[:-len("_build.txt")]
        mem = {}
        for ln in b.read_text(errors="replace").splitlines():
            if (mm := RE_MEM.match(ln)):
                val = int(mm.group(2)) * (1024 if mm.group(3) == "KB" else 1)
                mem[mm.group(1)] = val
        noinit = None
        sec = LOGS / f"{exp}_secoes.txt"
        if sec.exists():
            for ln in sec.read_text().splitlines():
                p = ln.split()
                if len(p) > 2 and p[1] == ".dram0.noinit":
                    noinit = int(p[2], 16)
        rows.append(dict(exp=exp, flash=mem.get("FLASH"), iram0=mem.get("iram0_0_seg"),
                         dram0=mem.get("dram0_0_seg"), noinit=noinit,
                         ram_total=(mem.get("dram0_0_seg") or 0) + (noinit or 0)))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Planilha
# ----------------------------------------------------------------------------
from openpyxl import Workbook  # noqa: E402
from openpyxl.chart import LineChart, Reference  # noqa: E402
from openpyxl.chart.series import SeriesLabel  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="DCE6F1")
THIN = Side(style="thin", color="B7B7B7")
BOX = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
MODES = [("polling", "Polling"), ("irq_thread", "ISR + thread"), ("workqueue", "ISR + work queue")]
US = "#,##0.00"
PCT = "0.00%"


def style_ws(ws, widths):
    for row in ws.iter_rows():
        for c in row:
            if c.font.b:
                c.font = Font(name=FONT, bold=True, size=c.font.sz or 10)
            else:
                c.font = Font(name=FONT, size=10)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def header(ws, row, values):
    for j, v in enumerate(values, 1):
        c = ws.cell(row=row, column=j, value=v)
        c.font = Font(name=FONT, bold=True)
        c.fill = HDR_FILL
        c.border = BOX
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")


def title(ws, row, text, note=None):
    ws.cell(row=row, column=1, value=text).font = Font(name=FONT, bold=True, size=12)
    if note:
        ws.cell(row=row + 1, column=1, value=note).font = Font(name=FONT, italic=True, size=9)
    return row + (3 if note else 2)


def raw_sheet(wb, name, df, cols, extra):
    """Dados brutos + colunas derivadas por formula. extra: [(titulo, formula(r), fmt)]"""
    ws = wb.create_sheet(name)
    header(ws, 1, [c[1] for c in cols] + [e[0] for e in extra])
    for i, rec in enumerate(df.to_dict("records"), start=2):
        for j, (key, _) in enumerate(cols, 1):
            v = rec.get(key)
            ws.cell(row=i, column=j, value=None if pd.isna(v) else v)
        for k, (_, f, fmt) in enumerate(extra, len(cols) + 1):
            c = ws.cell(row=i, column=k, value=f(i))
            c.number_format = fmt
    ws.freeze_panes = "A2"
    style_ws(ws, [26, 8, 11] + [12] * (len(cols) + len(extra)))
    return ws


def avg(sheet, col, *crit):
    """AVERAGEIFS sobre uma folha de dados; crit = pares (coluna, valor)."""
    c = ",".join(f'{sheet}!${k}:${k},"{v}"' for k, v in zip(crit[::2], crit[1::2]))
    return f'=IFERROR(AVERAGEIFS({sheet}!${col}:${col},{c}),"sem amostras")'


def agg(fn, sheet, col, *crit):
    c = ",".join(f'{sheet}!${k}:${k},"{v}"' for k, v in zip(crit[::2], crit[1::2]))
    return f'=IFERROR(_xlfn.{fn}({sheet}!${col}:${col},{c}),"sem amostras")'


def build_workbook(lat, summ, threads, manual, mem, sizeof, out):
    wb = Workbook()
    ws = wb.active
    ws.title = "Leia-me"
    info = [
        ("Resultados do hands-on: Polling, Interrupcoes, Threads e Work Queue no Zephyr RTOS", True),
        ("Leonardo Moreno - NUSP 13654481", False),
        ("", False),
        ("ORIGEM DOS DADOS", True),
        ("Firmware real compilado com west build (Zephyr 4.5.0-rc2, Zephyr SDK 1.0.1, placa "
         "esp32_devkitc/esp32/procpu).", False),
        ("Execucao EMULADA: QEMU da Espressif (esp-develop) com modelo de GPIO estendido "
         "(saida/entrada, interrupcao por borda, jumper GPIO18->GPIO4).", False),
        ("Tempo virtual deterministico: -icount shift=2 (4 ns por instrucao, ~1 ciclo por "
         "instrucao a 240 MHz). Nao e medicao em placa fisica.", False),
        ("Memoria (Flash/RAM) vem do build real e e identica a de uma placa com a mesma versao.",
         False),
        ("", False),
        ("ABAS", True),
        ("Dados_LAT, Dados_SUM, Dados_Threads, Dados_Memoria, Dados_Manual: linhas extraidas "
         "dos logs brutos (pasta logs/).", False),
        ("Exp1-3, Exp4, Exp5, Exp6, Exp7, Exp8: tabelas da apostila calculadas por formula "
         "a partir das abas de dados.", False),
        ("Latencias em microssegundos (us); CPU e perdas em %. 'sem amostras' = nenhum evento "
         "detectado.", False),
    ]
    for i, (t, b) in enumerate(info, 1):
        ws.cell(row=i, column=1, value=t).font = Font(name=FONT, bold=b, size=11 if b else 10)
    ws.column_dimensions["A"].width = 120

    raw_sheet(wb, "Dados_LAT", lat,
              [("exp", "experimento"), ("run", "execucao"), ("modo", "modo"),
               ("metrica", "metrica"), ("n", "n"), ("min_ns", "min (ns)"),
               ("med_ns", "media (ns)"), ("max_ns", "max (ns)")],
              [("min (us)", lambda r: f"=F{r}/1000", US),
               ("media (us)", lambda r: f"=G{r}/1000", US),
               ("max (us)", lambda r: f"=H{r}/1000", US)])
    raw_sheet(wb, "Dados_SUM", summ,
              [("exp", "experimento"), ("run", "execucao"), ("modo", "modo"),
               ("poll_ms", "poll_ms"), ("proc_us", "proc_us"), ("period_ms", "period_ms"),
               ("pulse_ms", "pulse_ms"), ("gen", "gerados"), ("det", "detectados"),
               ("proc", "processados"), ("cpu_x100", "cpu_x100"),
               ("cpu_est_x100", "cpu_est_x100"), ("janela_ms", "janela (ms)"),
               ("hb_max_ms", "heartbeat max (ms)")],
              [("perdidos", lambda r: f"=MAX(0,H{r}-J{r})", "0"),
               ("perdidos (%)", lambda r: f"=IF(H{r}>0,O{r}/H{r},0)", "0.0%"),
               ("CPU ocupada", lambda r: f"=K{r}/10000", PCT),
               ("CPU estimada", lambda r: f"=L{r}/10000", PCT)])
    raw_sheet(wb, "Dados_Threads", threads,
              [("exp", "experimento"), ("run", "execucao"), ("thread", "thread"),
               ("pilha_usada", "pilha usada (B)"), ("pilha_total", "pilha total (B)"),
               ("cpu_pct", "CPU (%) Thread Analyzer")],
              [("uso da pilha", lambda r: f"=D{r}/E{r}", "0%"),
               ("CPU (fracao)", lambda r: f"=F{r}/100", "0%")])
    raw_sheet(wb, "Dados_Memoria", mem,
              [("exp", "build"), ("flash", "FLASH (B)"), ("iram0", "iram0_0_seg (B)"),
               ("dram0", "dram0_0_seg (B)"), ("noinit", ".dram0.noinit - pilhas (B)")],
              [("RAM estatica total (B)", lambda r: f"=D{r}+E{r}", "#,##0")])
    raw_sheet(wb, "Dados_Manual", manual,
              [("exp", "experimento"), ("modo", "modo"), ("toques", "toques no botao (trace)"),
               ("toques_curtos", "toques de 4 ms"), ("processados", "eventos processados"),
               ("status_10s", "contador a cada 10 s"), ("pilha_evento", "pilha thread evento")],
              [])

    L, S, T, M = "Dados_LAT", "Dados_SUM", "Dados_Threads", "Dados_Memoria"

    # ---------------- Exp 1-3 ----------------
    ws = wb.create_sheet("Exp1-3")
    r = title(ws, 1, "Experimentos 1 a 3 - modo manual (25 toques roteirizados, 30 s)",
              "Toques de 80-220 ms a cada 0,4-1,5 s; 1 a cada 5 e um toque rapido de 4 ms. "
              "Sem bounce (o botao emulado e limpo).")
    header(ws, r, ["Modo", "Toques gerados", "Toques de 4 ms", "Eventos processados",
                   "Nao detectados", "Pilha da thread do evento (B)"])
    for i, (m, lbl) in enumerate(MODES):
        rr = r + 1 + i
        ws.cell(row=rr, column=1, value=lbl)
        src = f'"exp1-3_{m}_manual"'
        ws.cell(row=rr, column=2, value=f"=SUMIFS(Dados_Manual!$C:$C,Dados_Manual!$A:$A,{src})")
        ws.cell(row=rr, column=3, value=f"=SUMIFS(Dados_Manual!$D:$D,Dados_Manual!$A:$A,{src})")
        ws.cell(row=rr, column=4, value=f"=SUMIFS(Dados_Manual!$E:$E,Dados_Manual!$A:$A,{src})")
        ws.cell(row=rr, column=5, value=f"=B{rr}-D{rr}")
        ws.cell(row=rr, column=6, value=f"=INDEX(Dados_Manual!$G:$G,MATCH({src},Dados_Manual!$A:$A,0))")
    style_ws(ws, [22, 16, 16, 20, 16, 26])

    # ---------------- Exp 4 ----------------
    ws = wb.create_sheet("Exp4")
    r = title(ws, 1, "Tabela 10.1 - Tempo (us): media das 3 execucoes",
              "Padroes do Kconfig: 200 eventos, periodo 97 ms, pulso 20 ms, sem carga, polling 10 ms.")
    header(ws, r, ["Metrica", "Polling (P = 10 ms)", "ISR + thread", "ISR + work queue"])
    rows = [("lat_detect - media", "lat_detect", "J", "AVERAGE"),
            ("lat_detect - maximo", "lat_detect", "K", "MAX"),
            ("lat_handoff - media", "lat_handoff", "J", "AVERAGE"),
            ("lat_handoff - maximo", "lat_handoff", "K", "MAX"),
            ("lat_process - media", "lat_process", "J", "AVERAGE"),
            ("lat_process - maximo", "lat_process", "K", "MAX"),
            ("lat_proc_dur - media", "lat_proc_dur", "J", "AVERAGE")]
    for i, (lbl, met, col, fn) in enumerate(rows):
        rr = r + 1 + i
        ws.cell(row=rr, column=1, value=lbl)
        for j, (m, _) in enumerate(MODES, 2):
            if met == "lat_handoff" and m == "polling":
                ws.cell(row=rr, column=j, value="n/a")
                continue
            f = (avg(L, col, "A", f"exp4_{m}", "D", met) if fn == "AVERAGE"
                 else agg("MAXIFS", L, col, "A", f"exp4_{m}", "D", met))
            ws.cell(row=rr, column=j, value=f).number_format = US
    rr = r + 1 + len(rows)
    ws.cell(row=rr, column=1, value="Jitter de lat_process (max - min)")
    for j, (m, _) in enumerate(MODES, 2):
        ws.cell(row=rr, column=j,
                value=f'=_xlfn.MAXIFS({L}!$K:$K,{L}!$A:$A,"exp4_{m}",{L}!$D:$D,"lat_process")'
                      f'-_xlfn.MINIFS({L}!$I:$I,{L}!$A:$A,"exp4_{m}",{L}!$D:$D,"lat_process")'
                ).number_format = US
    rr += 1
    ws.cell(row=rr, column=1, value="Amplitude da media de lat_process entre as 3 execucoes")
    for j, (m, _) in enumerate(MODES, 2):
        ws.cell(row=rr, column=j,
                value=f'=_xlfn.MAXIFS({L}!$J:$J,{L}!$A:$A,"exp4_{m}",{L}!$D:$D,"lat_process")'
                      f'-_xlfn.MINIFS({L}!$J:$J,{L}!$A:$A,"exp4_{m}",{L}!$D:$D,"lat_process")'
                ).number_format = US
    t101_end = rr

    r = title(ws, rr + 2, "Tabela 10.1b - Polling com estimulo fora de fase e sensibilidade ao CPI",
              "Periodo 95 ms = 97 ticks reais (k_msleep arredonda +1 tick). CPI~2: -icount shift=3 "
              "(8 ns/instrucao), 1 execucao.")
    header(ws, r, ["Metrica (us)", "Polling, periodo 95 ms", "Polling CPI~2", "ISR + thread CPI~2",
                   "ISR + work queue CPI~2"])
    cols = ["exp4_polling_periodo95", "exp4_polling_cpi2", "exp4_irq_thread_cpi2",
            "exp4_workqueue_cpi2"]
    for i, (lbl, met, col, fn) in enumerate(rows[:6]):
        rr = r + 1 + i
        ws.cell(row=rr, column=1, value=lbl)
        for j, e in enumerate(cols, 2):
            if met == "lat_handoff" and "polling" in e:
                ws.cell(row=rr, column=j, value="n/a")
                continue
            f = (avg(L, col, "A", e, "D", met) if fn == "AVERAGE"
                 else agg("MAXIFS", L, col, "A", e, "D", met))
            ws.cell(row=rr, column=j, value=f).number_format = US

    r = title(ws, rr + 2, "Tabela 10.2 - Eventos (media das 3 execucoes)")
    header(ws, r, ["Metrica", "Polling", "ISR + thread", "ISR + work queue"])
    for i, (lbl, col) in enumerate([("Gerados", "H"), ("Detectados", "I"), ("Processados", "J"),
                                    ("Perdidos", "O")]):
        rr = r + 1 + i
        ws.cell(row=rr, column=1, value=lbl)
        for j, (m, _) in enumerate(MODES, 2):
            ws.cell(row=rr, column=j, value=avg(S, col, "A", f"exp4_{m}")).number_format = "0"

    r = title(ws, rr + 2, "Tabela 10.3 - CPU (media das 3 execucoes)")
    header(ws, r, ["Metrica", "Polling", "ISR + thread", "ISR + work queue"])
    ev_thread = {"polling": "poll", "irq_thread": "worker", "workqueue": "sysworkq"}
    cpu_rows = [("CPU ocupada (kernel)", lambda m: avg(S, "Q", "A", f"exp4_{m}")),
                ("CPU estimada (processamento)", lambda m: avg(S, "R", "A", f"exp4_{m}")),
                ("idle (Thread Analyzer)", lambda m: avg(T, "H", "A", f"exp4_{m}", "C", "idle")),
                ("Thread do evento (poll/worker/sysworkq)",
                 lambda m: avg(T, "H", "A", f"exp4_{m}", "C", ev_thread[m])),
                ("main (gerador de estimulo)", lambda m: avg(T, "H", "A", f"exp4_{m}", "C", "main"))]
    for i, (lbl, f) in enumerate(cpu_rows):
        rr = r + 1 + i
        ws.cell(row=rr, column=1, value=lbl)
        for j, (m, _) in enumerate(MODES, 2):
            ws.cell(row=rr, column=j, value=f(m)).number_format = PCT if i < 2 else "0%"

    r = title(ws, rr + 2, "Tabela 10.4 - Memoria",
              "Flash = regiao FLASH do resumo do build. RAM = dram0_0_seg (dados+bss) + .dram0.noinit "
              "(pilhas, contadas na regiao dram1 do resumo). Pilhas: Thread Analyzer (usada / total).")
    header(ws, r, ["Metrica", "Polling", "ISR + thread", "ISR + work queue"])

    def mem_ref(m, col):
        return f'=INDEX({M}!${col}:${col},MATCH("exp4_{m}",{M}!$A:$A,0))'

    def stack(m, th):
        crit = f'{T}!$A:$A,"exp4_{m}",{T}!$C:$C,"{th}"'
        return (f'=IFERROR(TEXT(_xlfn.MAXIFS({T}!$D:$D,{crit}),"0")&" / "&'
                f'TEXT(_xlfn.MAXIFS({T}!$E:$E,{crit}),"0"),"n/a")')

    mem_rows = [("Flash usada (bytes)", lambda m: mem_ref(m, "B")),
                ("RAM dram0_0_seg - dados + bss (bytes)", lambda m: mem_ref(m, "D")),
                ("RAM .dram0.noinit - pilhas de todas as threads (bytes)", lambda m: mem_ref(m, "E")),
                ("RAM estatica total (bytes)", lambda m: mem_ref(m, "F")),
                ("IRAM iram0_0_seg (bytes)", lambda m: mem_ref(m, "C")),
                ("Pilha da thread do evento", lambda m: stack(m, ev_thread[m]) if m != "workqueue"
                 else "n/a (usa a sysworkq)"),
                ("Pilha da sysworkq", lambda m: stack(m, "sysworkq") if m == "workqueue"
                 else "n/a (nao listada)"),
                ("Pilha da ISR (ISR0)", lambda m: stack(m, "ISR0")),
                ("Pilha da main", lambda m: stack(m, "main"))]
    for i, (lbl, f) in enumerate(mem_rows):
        rr = r + 1 + i
        ws.cell(row=rr, column=1, value=lbl)
        for j, (m, _) in enumerate(MODES, 2):
            ws.cell(row=rr, column=j, value=f(m)).number_format = "#,##0"
    rr += 1
    ws.cell(row=rr, column=1, value="sizeof(k_thread) / k_sem / k_work / k_work_q (bytes)")
    for j in range(2, 5):
        ws.cell(row=rr, column=j, value=" / ".join(map(str, sizeof)) if sizeof else "")
    rr += 1
    ws.cell(row=rr, column=1, value="Flash: diferenca para o polling (bytes)")
    ws.cell(row=rr, column=2, value=0)
    for j in (3, 4):
        ws.cell(row=rr, column=j, value=f"={get_column_letter(j)}{r + 1}-$B${r + 1}").number_format = "#,##0"
    rr += 1
    ws.cell(row=rr, column=1, value="RAM estatica total: diferenca para o polling (bytes)")
    ws.cell(row=rr, column=2, value=0)
    for j in (3, 4):
        ws.cell(row=rr, column=j, value=f"={get_column_letter(j)}{r + 4}-$B${r + 4}").number_format = "#,##0"
    style_ws(ws, [52, 24, 22, 22, 22])

    # ---------------- Exp 5 ----------------
    ws = wb.create_sheet("Exp5")
    r = title(ws, 1, "Tabela 11.1 - Varredura do periodo de polling (media de 3 execucoes)",
              "Periodo do estimulo 95 ms (97 ticks reais) para varrer todas as fases do polling.")
    header(ws, r, ["P (ms)", "Pulso (ms)", "Lat. media (us)", "Lat. max (us)", "CPU ocupada",
                   "Detectados", "Gerados", "Perdidos (%)"])
    first = r + 1
    for i, (pulse, p) in enumerate([(w, p) for w in (20, 5) for p in (1, 5, 10, 50, 100)]):
        rr = first + i
        e = f"exp5_poll{p}_pulse{pulse}"
        ws.cell(row=rr, column=1, value=p)
        ws.cell(row=rr, column=2, value=pulse)
        ws.cell(row=rr, column=3, value=avg(L, "J", "A", e, "D", "lat_detect")).number_format = US
        ws.cell(row=rr, column=4, value=agg("MAXIFS", L, "K", "A", e, "D", "lat_detect")).number_format = US
        ws.cell(row=rr, column=5, value=avg(S, "Q", "A", e)).number_format = PCT
        ws.cell(row=rr, column=6, value=avg(S, "I", "A", e)).number_format = "0"
        ws.cell(row=rr, column=7, value=avg(S, "H", "A", e)).number_format = "0"
        ws.cell(row=rr, column=8, value=avg(S, "P", "A", e)).number_format = "0.0%"
    last = first + 9
    for col, ttl, ytitle, anchor in [(3, "Latencia media de deteccao x P", "us", "J3"),
                                     (5, "CPU ocupada x P", "CPU ocupada", "J21"),
                                     (8, "Eventos perdidos x P", "perdidos", "J39")]:
        ch = LineChart()
        ch.title, ch.y_axis.title, ch.x_axis.title = ttl, ytitle, "P (ms)"
        ch.height, ch.width = 8, 15
        for start, lbl in ((first, "pulso 20 ms"), (first + 5, "pulso 5 ms")):
            ref = Reference(ws, min_col=col, min_row=start, max_row=start + 4)
            ch.add_data(ref, titles_from_data=False)
            ch.series[-1].tx = SeriesLabel(v=lbl)
        ch.set_categories(Reference(ws, min_col=1, min_row=first, max_row=first + 4))
        ws.add_chart(ch, anchor)
    style_ws(ws, [10, 11, 16, 16, 14, 12, 10, 14])

    # ---------------- Exp 6 ----------------
    ws = wb.create_sheet("Exp6")
    r = title(ws, 1, "Tabela 12.1 - Carga por evento (periodo do estimulo = 97 ms)")
    header(ws, r, ["Carga (us)", "Modo", "CPU ocupada", "CPU estimada", "Lat. process media (us)",
                   "Perdidos"])
    first = r + 1
    i = 0
    for load in (0, 1000, 10000, 50000):
        for m, lbl in MODES[1:]:
            rr = first + i
            e = f"exp6a_{m}_proc{load}"
            ws.cell(row=rr, column=1, value=load).number_format = "#,##0"
            ws.cell(row=rr, column=2, value=lbl)
            ws.cell(row=rr, column=3, value=avg(S, "Q", "A", e)).number_format = PCT
            ws.cell(row=rr, column=4, value=avg(S, "R", "A", e)).number_format = PCT
            ws.cell(row=rr, column=5, value=avg(L, "J", "A", e, "D", "lat_process")).number_format = US
            ws.cell(row=rr, column=6, value=avg(S, "O", "A", e)).number_format = "0"
            i += 1
    rr = first + i
    r = title(ws, rr + 2, "Tabela 12.2 - Saturacao (tratamento 30 ms > periodo 23 ms; main prioridade 0)")
    header(ws, r, ["Modo", "Gerados", "Detectados", "Processados", "Perdidos (%)", "CPU ocupada"])
    for i, (m, lbl) in enumerate(MODES):
        rr = r + 1 + i
        e = f"exp6b_{m}_saturacao"
        ws.cell(row=rr, column=1, value=lbl + (" (P = 10 ms)" if m == "polling" else ""))
        for j, col, fmt in ((2, "H", "0"), (3, "I", "0"), (4, "J", "0"), (5, "P", "0.0%"),
                            (6, "Q", PCT)):
            ws.cell(row=rr, column=j, value=avg(S, col, "A", e)).number_format = fmt
    style_ws(ws, [24, 18, 14, 14, 22, 12])

    # ---------------- Exp 7 ----------------
    ws = wb.create_sheet("Exp7")
    r = title(ws, 1, "Tabela 13.1 - Impacto no escalonamento (carga de 20 ms por evento)",
              "Heartbeat: thread de prioridade 0 que acorda a cada 1 ms (baseline ~1-2 ms).")
    header(ws, r, ["Modo (carga 20 ms)", "Maior intervalo do heartbeat (ms)", "CPU ocupada (kernel)",
                   "CPU estimada", "Perdidos"])
    for i, (m, lbl) in enumerate([("isr_only", "ISR only (anti-padrao)"),
                                  ("irq_thread", "ISR + thread"), ("workqueue", "ISR + work queue")]):
        rr = r + 1 + i
        e = f"exp7_{m}_hb"
        ws.cell(row=rr, column=1, value=lbl)
        ws.cell(row=rr, column=2, value=avg(S, "N", "A", e)).number_format = "0.00"
        ws.cell(row=rr, column=3, value=avg(S, "Q", "A", e)).number_format = PCT
        ws.cell(row=rr, column=4, value=avg(S, "R", "A", e)).number_format = PCT
        ws.cell(row=rr, column=5, value=avg(S, "O", "A", e)).number_format = "0"
    style_ws(ws, [26, 22, 18, 14, 10])

    # ---------------- Exp 8 ----------------
    ws = wb.create_sheet("Exp8")
    r = title(ws, 1, "Desafio final - processamento de 100 ms por evento",
              "sleep = k_msleep(100) (thread dorme); busy = k_busy_wait(100 ms) (consome CPU). "
              "Periodo 197 ms (~5 ev/s); rajada = periodo 47 ms (~20 ev/s) com busy. 50 eventos.")
    header(ws, r, ["Versao", "Cenario", "Gerados", "Processados", "Perdidos (%)",
                   "Lat. process media (us)", "Lat. process max (us)", "Duracao do tratamento (ms)",
                   "CPU ocupada", "CPU estimada", "Flash (B)", "RAM estatica total (B)",
                   "Pilha thread evento (B)"])
    i = 0
    for m, lbl in MODES:
        for sc in ("sleep", "busy", "rajada"):
            rr = r + 1 + i
            e = f"exp8_{m}_{sc}"
            ws.cell(row=rr, column=1, value=lbl)
            ws.cell(row=rr, column=2, value=sc)
            ws.cell(row=rr, column=3, value=avg(S, "H", "A", e)).number_format = "0"
            ws.cell(row=rr, column=4, value=avg(S, "J", "A", e)).number_format = "0"
            ws.cell(row=rr, column=5, value=avg(S, "P", "A", e)).number_format = "0.0%"
            ws.cell(row=rr, column=6, value=avg(L, "J", "A", e, "D", "lat_process")).number_format = US
            ws.cell(row=rr, column=7, value=agg("MAXIFS", L, "K", "A", e, "D", "lat_process")).number_format = US
            ws.cell(row=rr, column=8, value=f'=IFERROR({avg(L, "J", "A", e, "D", "lat_proc_dur")[1:]}/1000,"")').number_format = "0.0"
            ws.cell(row=rr, column=9, value=avg(S, "Q", "A", e)).number_format = PCT
            ws.cell(row=rr, column=10, value=avg(S, "R", "A", e)).number_format = PCT
            ws.cell(row=rr, column=11, value=f'=INDEX({M}!$B:$B,MATCH("{e}",{M}!$A:$A,0))').number_format = "#,##0"
            ws.cell(row=rr, column=12, value=f'=INDEX({M}!$F:$F,MATCH("{e}",{M}!$A:$A,0))').number_format = "#,##0"
            ws.cell(row=rr, column=13, value=stack_cell(T, e, ev_thread[m]))
            i += 1
    style_ws(ws, [18, 10, 10, 12, 12, 18, 18, 16, 12, 12, 12, 12, 18])

    for w in wb.worksheets:
        w.sheet_view.showGridLines = w.title.startswith("Dados")
    wb.save(out)


def stack_cell(T, e, th):
    crit = f'{T}!$A:$A,"{e}",{T}!$C:$C,"{th}"'
    return (f'=IFERROR(TEXT(_xlfn.MAXIFS({T}!$D:$D,{crit}),"0")&" / "&'
            f'TEXT(_xlfn.MAXIFS({T}!$E:$E,{crit}),"0"),"n/a")')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(ENTREGA / "resultados.xlsx"))
    ap.add_argument("--pickle", default="/home/user/work/dados.pkl")
    args = ap.parse_args()
    lat, summ, threads, manual, sizeof = parse_logs()
    mem = parse_builds()
    pd.to_pickle(dict(lat=lat, summ=summ, threads=threads, manual=manual, mem=mem,
                      sizeof=sizeof), args.pickle)
    build_workbook(lat, summ, threads, manual, mem, sizeof, args.xlsx)
    print(f"{len(lat)} linhas LAT, {len(summ)} SUM, {len(threads)} threads, "
          f"{len(mem)} builds -> {args.xlsx}")


if __name__ == "__main__":
    main()
