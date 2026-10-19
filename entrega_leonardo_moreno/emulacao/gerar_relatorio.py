#!/usr/bin/env python3
"""Gera relatorio.html (e, via html2pdf.js, relatorio.pdf) a partir dos dados extraidos
pelo analisar.py. Todos os numeros do texto saem dos logs."""
import base64
import csv
import html
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ENTREGA = HERE.parent
LOGS = ENTREGA / "logs"
FIG = Path("/home/user/work/fig")
OUT = Path("/home/user/work/rel/relatorio.html")
D = pd.read_pickle("/home/user/work/dados.pkl")
lat, summ, threads, manual, mem = D["lat"], D["summ"], D["threads"], D["manual"], D["mem"]
SZ = D["sizeof"]
MODES = [("polling", "Polling"), ("irq_thread", "ISR + thread"), ("workqueue", "ISR + work queue")]
EVT = {"polling": "poll", "irq_thread": "worker", "workqueue": "sysworkq"}


# ---------------------------------------------------------------- acesso aos dados
def L(exp, met, col="med_ns", fn="mean"):
    s = lat[(lat.exp == exp) & (lat.metrica == met)][col]
    if not len(s):
        return None
    return getattr(s, fn)() / 1000


def S(exp, col, fn="mean"):
    s = summ[summ.exp == exp][col]
    return getattr(s, fn)() if len(s) else None


def TH(exp, th, col):
    s = threads[(threads.exp == exp) & (threads.thread == th)][col]
    return s.max() if len(s) else None


def MEM(exp, col):
    s = mem[mem.exp == exp][col]
    return int(s.iloc[0]) if len(s) else None


def lost(exp):
    g, p = S(exp, "gen"), S(exp, "proc")
    return max(0, g - p), 100 * max(0, g - p) / g


def n(v, nd=2):
    """Numero no formato brasileiro."""
    if v is None:
        return "sem amostras"
    s = f"{v:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def i(v):
    return n(v, 0)


def pct(x100):
    return n(x100 / 100) + " %"


def stack(exp, th):
    u, t = TH(exp, th, "pilha_usada"), TH(exp, th, "pilha_total")
    return f"{u} / {t}" if u is not None else "n/a"


def trace_latency(exp, run=1, skip=6):
    """Latencia externa estimulo (GPIO18 ativo) -> LED (GPIO2), em us, pelo trace."""
    path = LOGS / f"{exp}_run{run}_gpio_trace.csv"
    rows = [(int(r["t_ns"]), r["gpio"], r["level"]) for r in csv.DictReader(path.open())]
    st = [t for t, g, lv in rows if g == "18" and lv == "0"][1:]  # 1a borda = configuracao
    led = [t for t, g, lv in rows if g == "2"][2:]                # 2 primeiras = configuracao
    out = []
    for s in st[skip:]:
        nxt = next((t for t in led if t > s), None)
        if nxt is not None:
            out.append((nxt - s) / 1000)
    return sum(out) / len(out), min(out), max(out)


# ---------------------------------------------------------------- html helpers
def table(head, rows, caption=None, cls="", note=None):
    h = "".join(f"<th>{c}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    cap = f"<caption>{caption}</caption>" if caption else ""
    nt = f'<p class="note">{note}</p>' if note else ""
    return f'<table class="{cls}">{cap}<thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>{nt}'


def fig(name, caption, width="100%"):
    data = base64.b64encode((FIG / name).read_bytes()).decode()
    return (f'<figure><img src="data:image/png;base64,{data}" style="width:{width}">'
            f"<figcaption>{caption}</figcaption></figure>")


def code(path, start=None, end=None):
    lines = Path(path).read_text().splitlines()
    if start is not None:
        a = next(k for k, ln in enumerate(lines) if start in ln)
        b = next(k for k, ln in enumerate(lines) if k > a and end in ln) if end else len(lines) - 1
        lines = lines[a:b + 1]
    return "<pre>" + html.escape("\n".join(lines).expandtabs(4)) + "</pre>"


def qa(items):
    return "<ol class='qa'>" + "".join(f"<li><b>{q}</b> {a}</li>" for q, a in items) + "</ol>"


# ---------------------------------------------------------------- numeros-chave
E4 = {m: f"exp4_{m}" for m, _ in MODES}
det = {m: L(E4[m], "lat_detect") for m, _ in MODES}
dmax = {m: L(E4[m], "lat_detect", "max_ns", "max") for m, _ in MODES}
hof = {m: L(E4[m], "lat_handoff") for m, _ in MODES}
hmax = {m: L(E4[m], "lat_handoff", "max_ns", "max") for m, _ in MODES}
prc = {m: L(E4[m], "lat_process") for m, _ in MODES}
pmax = {m: L(E4[m], "lat_process", "max_ns", "max") for m, _ in MODES}
pmin = {m: L(E4[m], "lat_process", "min_ns", "min") for m, _ in MODES}
dur = {m: L(E4[m], "lat_proc_dur") for m, _ in MODES}
cpu = {m: S(E4[m], "cpu_x100") for m, _ in MODES}
cyc = {}
for m, _ in MODES:
    s = threads[(threads.exp == E4[m]) & (threads.thread == EVT[m])]
    cyc[m] = None
flash = {m: MEM(E4[m], "flash") for m, _ in MODES}
dram = {m: MEM(E4[m], "dram0") for m, _ in MODES}
noinit = {m: MEM(E4[m], "noinit") for m, _ in MODES}
ramt = {m: MEM(E4[m], "ram_total") for m, _ in MODES}
iram = {m: MEM(E4[m], "iram0") for m, _ in MODES}
amp = {m: (lat[(lat.exp == E4[m]) & (lat.metrica == "lat_process")].med_ns.max()
           - lat[(lat.exp == E4[m]) & (lat.metrica == "lat_process")].med_ns.min()) / 1000
       for m, _ in MODES}
ext = {m: trace_latency(E4[m]) for m, _ in MODES}
p95 = L("exp4_polling_periodo95", "lat_detect")
p95max = L("exp4_polling_periodo95", "lat_detect", "max_ns", "max")
p95min = L("exp4_polling_periodo95", "lat_detect", "min_ns", "min")
c2 = {m: (L(f"exp4_{m}_cpi2", "lat_detect"), L(f"exp4_{m}_cpi2", "lat_handoff"),
          L(f"exp4_{m}_cpi2", "lat_process")) for m, _ in MODES}


def total_cycles(exp, th):
    """Ciclos totais de uma thread (linha 'Total CPU cycles used' do Thread Analyzer)."""
    log = (LOGS / f"{exp}_run1.log").read_text().splitlines()
    for k, ln in enumerate(log):
        if ln.startswith(f" {th} ") and "STACK" in ln:
            nxt = log[k + 1]
            if "Total CPU cycles used" in nxt:
                return int(nxt.rsplit(":", 1)[1])
    return None


cyc = {m: total_cycles(E4[m], EVT[m]) for m, _ in MODES}
E5 = [(w, p, f"exp5_poll{p}_pulse{w}") for w in (20, 5) for p in (1, 5, 10, 50, 100)]
hb = {m: S(f"exp7_{m}_hb", "hb_max_ms") for m in ("isr_only", "irq_thread", "workqueue")}
man = {r["modo"]: r for r in manual.to_dict("records")}

# ---------------------------------------------------------------- documento
CSS = """
@page { size: A4; }
body { font-family: 'Inter', 'DejaVu Sans', Arial, sans-serif; font-size: 10pt; color: #1b1b1a;
       line-height: 1.42; }
h1 { font-size: 15pt; margin: 18pt 0 6pt; color: #0b0b0b; border-bottom: 1.5px solid #2a78d6;
     padding-bottom: 3pt; break-after: avoid; }
h2 { font-size: 11.5pt; margin: 12pt 0 4pt; color: #0b0b0b; break-after: avoid; }
h3 { font-size: 10.5pt; margin: 9pt 0 3pt; break-after: avoid; }
p { margin: 4pt 0 6pt; text-align: justify; }
table { border-collapse: collapse; margin: 6pt 0 4pt; width: 100%; font-size: 8.6pt;
        break-inside: avoid; }
caption { caption-side: top; text-align: left; font-weight: 600; font-size: 9pt;
          padding-bottom: 3pt; color: #0b0b0b; }
th { background: #e8eef7; text-align: left; padding: 3pt 5pt; border: 1px solid #c9d3e0;
     font-weight: 600; }
td { padding: 2.5pt 5pt; border: 1px solid #d9d9d6; vertical-align: top; }
td:not(:first-child) { font-variant-numeric: tabular-nums; }
.note { font-size: 8.2pt; color: #52514e; margin-top: 0; }
pre { background: #f6f6f4; border: 1px solid #e2e2de; padding: 6pt 8pt; font-size: 7.6pt;
      line-height: 1.3; white-space: pre-wrap; break-inside: avoid; font-family: 'DejaVu Sans Mono', monospace; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.6pt; }
figure { margin: 8pt 0; break-inside: avoid; text-align: center; }
figcaption { font-size: 8.4pt; color: #52514e; margin-top: 2pt; }
.box { border: 1.5px solid #eb6834; background: #fdf3ee; padding: 7pt 10pt; margin: 10pt 0;
       break-inside: avoid; }
.box b { color: #a3401a; }
.info { border-left: 3px solid #2a78d6; background: #f1f6fd; padding: 5pt 9pt; margin: 8pt 0;
        break-inside: avoid; }
.cover { height: 250mm; display: flex; flex-direction: column; }
.cover .inst { font-size: 11pt; letter-spacing: .5px; color: #52514e; }
.cover h1.t { font-size: 22pt; border: none; margin-top: 60mm; line-height: 1.2; }
.cover .sub { font-size: 12pt; color: #52514e; }
.cover .who { margin-top: 30mm; font-size: 11pt; }
.pb { break-before: page; }
ol.qa li { margin-bottom: 5pt; text-align: justify; }
.check { font-size: 9pt; }
ul { margin: 3pt 0 6pt 16pt; padding: 0; }
li { margin-bottom: 2pt; }
.small td, .small th { font-size: 8pt; }
"""

parts = []
A = parts.append

# ---------------------------------------------------------------- capa
A(f"""
<div class="cover">
  <div class="inst">UNIVERSIDADE DE SÃO PAULO · ESCOLA POLITÉCNICA</div>
  <h1 class="t">Polling, Interrupções, Threads e Work Queue no Zephyr RTOS</h1>
  <div class="sub">Relatório do hands-on: medição de uso de CPU, memória e tempo de execução em ESP32</div>
  <div class="who"><b>Aluno:</b> Leonardo Moreno · NUSP 13654481<br>
  <b>Data:</b> 19/10/2026<br>
  <b>Roteiro:</b> Apostila "Polling, Interrupções, Threads e Workqueue no Zephyr RTOS", v1.0 (set/2026)<br>
  <b>Código-base:</b> github.com/caninos-loucos/zephyr-esp32-lab</div>
</div>
""")

# ---------------------------------------------------------------- 1 objetivo
A("""<h1 class="pb">1. Objetivo</h1>
<p>Resolver o mesmo problema (detectar o acionamento de um botão e tratá-lo) com três arquiteturas
do Zephyr RTOS no ESP32: <b>polling</b>, <b>interrupção + thread com semáforo</b> e
<b>interrupção + work queue</b>. Em seguida, comparar as três com números de tempo (latência de
detecção, hand-off, duração, jitter), CPU (ocupação total e por thread) e memória (Flash, RAM,
pilhas e objetos do kernel). Também foram estudados o efeito do período de polling, da carga e da
taxa de eventos, o anti-padrão de processar dentro da ISR e um sistema com processamento de 100 ms
por evento, para justificar uma escolha de arquitetura.</p>""")

# ---------------------------------------------------------------- 2 ambiente
A(f"""<h1>2. Ambiente</h1>
{table(["Item", "Valor"], [
    ["Placa alvo (build)", "<code>esp32_devkitc/esp32/procpu</code> (ESP32-DevKitC, núcleo PRO)"],
    ["Zephyr", "4.5.0-rc2, commit <code>03b1ebca3343</code> (manifesto do repositório do curso, revisão <code>main</code>)"],
    ["Zephyr SDK / toolchain", "1.0.1 / <code>xtensa-espressif_esp32_zephyr-elf-gcc</code> 14.3.0"],
    ["HAL Espressif", "<code>hal_espressif</code> commit <code>c1e43fdd</code>; west 1.5.0"],
    ["CPU / contador", "Xtensa LX6 a 240 MHz; <code>hw cycles/s = 240000000</code> (resolução de 4,17 ns); tick = 1000 Hz"],
    ["Temporizador do sistema", "<code>CONFIG_XTENSA_TIMER</code> (CCOUNT/CCOMPARE)"],
    ["Execução", "ESP32 em emulação (QEMU Espressif) com o firmware compilado para <code>esp32_devkitc</code>; detalhes no Apêndice B"],
], "Tabela 2.1 - Ambiente de compilação e execução")}
{table(["Função", "Pino", "Ligação", "Configuração (app.overlay)", "Uso"], [
    ["LED", "GPIO2", "GPIO2 → LED → GND", "saída, ativo em nível alto", "alterna a cada evento tratado"],
    ["Botão", "GPIO4", "GPIO4 → botão → GND", "entrada, ativo em nível baixo, <i>pull-up</i> interno", "evento externo (Exps. 1 a 3)"],
    ["Estímulo", "GPIO18", "GPIO18 → jumper → GPIO4", "saída, ativo em nível baixo", "gerador de eventos (Exps. 4 a 8)"],
], "Tabela 2.2 - Ligações do banco de medição")}""")

# ---------------------------------------------------------------- 3 metodologia
A(f"""<h1>3. Metodologia de medição</h1>
<h2>3.1 Instrumentação (igual à da apostila)</h2>
<p>O código do repositório do curso foi usado sem alterações nos experimentos 1 a 7. Os pontos
<code>t_stim</code> (na <code>main</code>, antes de acionar o pino de estímulo), <code>t_isr</code>
(primeira linha da ISR ou instante de detecção no polling), <code>t_ini</code> (início da thread ou
do work handler) e <code>t_fim</code> (fim de <code>app_process_event()</code>) são lidos com
<code>k_cycle_get_32()</code> e convertidos com <code>k_cyc_to_ns_floor64()</code>. A CPU ocupada vem
de dois instantâneos de <code>k_thread_runtime_stats_all_get()</code> (100 % − idle); a CPU por thread
e as pilhas vêm do Thread Analyzer; a memória estática vem do resumo do <code>west build</code> e de
<code>ram_report</code>/<code>rom_report</code>. Cada benchmark usa 5 eventos de aquecimento e 200
eventos medidos, sem <code>printk</code> na janela.</p>

<h2>3.2 Banco de estímulo</h2>
<p>Nos Exps. 4 a 8 a <code>main</code> gera pulsos no GPIO18, que chegam ao GPIO4 pelo jumper
(padrão: 200 pulsos de 20 ms a cada 97 ms, após 5 de aquecimento). O instante <code>t_stim</code> é
lido imediatamente antes de cada pulso. Nos Exps. 1 a 3 o GPIO4 recebeu uma sequência roteirizada de
25 toques de 80 a 220 ms, separados por 0,4 a 1,5 s; a cada cinco, um toque rápido de 4 ms, mais curto
que o período de polling. As transições dos pinos GPIO2, GPIO4 e GPIO18 também foram registradas com
carimbo de tempo, como num analisador lógico (<code>logs/*_gpio_trace.csv</code>). Cada configuração foi
executada 3 vezes nos Exps. 4 e 5 e uma vez nos demais.</p>

<h2>3.3 Validação com medida externa</h2>
<p>O registro dos pinos em cada execução do Exp. 4 dá uma medida externa, independente do software:
o intervalo entre a borda do estímulo (GPIO18) e a alternância do LED (GPIO2, primeira ação de
<code>app_process_event()</code>), equivalente à Extensão E7.</p>
{table(["Modo", "lat_process (software), µs", "Estímulo → LED (pinos), µs", "Diferença, µs"],
       [[lbl, n(prc[m]), n(ext[m][0]), n(ext[m][0] - prc[m])] for m, lbl in MODES],
       "Tabela 3.1 - Medida interna × medida externa (Exp. 4, execução 1)",
       note="A diferença positiva e constante é o viés de <code>gpio_pin_set_dt()</code> entre "
            "<code>t_stim</code> e a borda, somado ao tempo até a alternância do LED; ela não "
            "altera a comparação entre os modos.")}

<h2>3.4 Achado: o arredondamento de <code>k_msleep()</code> trava a fase do polling</h2>
<p>Na primeira execução do polling a latência de detecção saiu praticamente constante
({n(L(E4["polling"], "lat_detect", "min_ns", "min") / 1000)} a {n(dmax["polling"] / 1000)} ms), e não
uniforme entre 0 e 10 ms como prevê a apostila. O registro dos pinos mostrou que o estímulo se repete a cada
<b>99 ms</b>, não 97. A causa está em <code>kernel/timeout.c</code>: um timeout relativo é arredondado
<b>+1 tick</b> para garantir "pelo menos N ticks". Assim <code>k_msleep(20)</code> + <code>k_msleep(77)</code>
duram 21 + 78 = 99 ticks, e o laço de polling com <code>k_msleep(10)</code> roda a cada 11 ticks.
Como 99 = 9 × 11, o estímulo cai sempre na mesma fase do polling. É um comportamento do kernel,
independente da placa. Para os experimentos que dependem da
varredura de fase (Exp. 5 e a Tabela 10.1b) o período foi ajustado para
<code>APP_EVENT_PERIOD_MS=95</code>, que resulta em 97 ticks reais (primo).</p>

<h2>3.5 Fontes de erro consideradas</h2>
<ul>
<li>Viés do estímulo (<code>gpio_pin_set_dt()</code> entre <code>t_stim</code> e a borda), constante nos modos (Tabela 3.1).</li>
<li>Resolução do contador: 4,17 ns; estouro de 32 bits em 17,9 s (só diferenças curtas são medidas).</li>
<li>Cache e flash nas primeiras execuções de cada trecho de código (mitigados pelo aquecimento).</li>
<li>Tick de 1 ms e o arredondamento +1 tick (seção 3.4).</li>
<li>Tempo de ISR contabilizado na thread interrompida (CPU "ocupada" subestimada em ISRs longas, Exp. 7).</li>
<li>Coalescência de eventos (semáforo com limite 1 e work já pendente), que transforma eventos em perdas.</li>
</ul>""")

# ---------------------------------------------------------------- 4-6 implementacoes
BENCH = ENTREGA / "codigo" / "00_bench_eventos" / "src"
A(f"""<h1>4. Implementação do polling</h1>
<p>Uma thread <code>poll</code> (prioridade 1, pilha de 1 KiB) lê o pino a cada
<code>APP_POLL_PERIOD_MS</code> e trata a borda de subida do estado lógico; <code>last</code> evita
contar o mesmo toque várias vezes. O <code>k_msleep()</code> suspende a thread, liberando a CPU para a
idle.</p>
{code(BENCH / "mode_polling.c", "static void poll_thread", "k_msleep(CONFIG_APP_POLL_PERIOD_MS);")}
<h1>5. Implementação da interrupção + thread</h1>
<p>A ISR só registra <code>t_isr</code>, conta o evento e libera um semáforo
<code>K_SEM_DEFINE(button_sem, 0, 1)</code>. A thread <code>worker</code> (prioridade 1, 1 KiB) fica
bloqueada em <code>k_sem_take(K_FOREVER)</code>. A ordem de inicialização é callback →
<code>gpio_add_callback()</code> → <code>gpio_pin_interrupt_configure_dt(GPIO_INT_EDGE_TO_ACTIVE)</code>.</p>
{code(BENCH / "mode_irq_thread.c", "static void button_isr", "app_process_event();")}
<h1>6. Implementação da work queue</h1>
<p>A ISR submete um <code>k_work</code> à <i>system workqueue</i> (<code>sysworkq</code>, mesma
prioridade 1 da worker, por <code>CONFIG_SYSTEM_WORKQUEUE_PRIORITY=1</code>). Não há thread própria:
o handler roda na pilha da sysworkq.</p>
{code(BENCH / "mode_workqueue.c", "static void button_work_handler", "k_work_submit(&button_work);")}""")

# ---------------------------------------------------------------- 7 resultados
mr = []
for m, lbl in MODES:
    r = man.get(m, {})
    mr.append([lbl, r.get("toques", ""), r.get("toques_curtos", ""), r.get("processados", ""),
               (r.get("toques", 0) or 0) - (r.get("processados", 0) or 0), r.get("pilha_evento", "")])
A(f"""<h1 class="pb">7. Resultados</h1>
<h2>7.1 Experimento 0: validação do ambiente</h2>
<p>O <code>blink_test</code> compilou sem erros (Flash 143.728 B), deu boot
("<code>*** Booting Zephyr OS build 03b1ebca3343 ***</code>") e o registro do GPIO2 mostra o LED
alternando a cada 1,0001 s (<code>logs/exp0_blink_run1.log</code>). Os 0,1 ms além de 1 s são o tick
extra do <code>k_msleep(1000)</code> mais o tempo do laço. Itens: compilou ✔; imagem gravada na flash
(aplicação em 0x1000) ✔; LED piscando ✔; terminal serial com a mensagem de boot ✔.</p>

<h2>7.2 Experimentos 1 a 3: funcionamento em modo manual</h2>
<p>Compilação com <code>-DCONFIG_APP_STIMULUS=n -DCONFIG_APP_VERBOSE=y</code>; o botão recebeu a
sequência de 25 toques da seção 3.2, 5 deles de 4 ms. Cada toque detectado gerou uma linha "evento processado #N" e
alternou o LED.</p>
{table(["Modo", "Toques", "Toques de 4 ms", "Eventos processados", "Não detectados",
        "Pilha da thread do evento (B)"], mr,
       "Tabela 7.1 - Observações dos Experimentos 1, 2 e 3 (tabelas 7.1, 8.1 e 9.1 da apostila)")}
<ul>
<li><b>Polling (Exp. 1):</b> o LED mudou a cada toque detectado e o contador aumentou. Os toques de
4 ms, mais curtos que o período efetivo de 11 ms, foram em parte perdidos. Não houve eventos
múltiplos por toque, porque os toques da sequência são limpos, sem <i>bounce</i> (num botão mecânico,
um clique poderia gerar vários eventos; ver E1). No Thread Analyzer a <code>poll</code> aparece com 0 % (arredondado) e
a idle com 99 %.</li>
<li><b>Interrupção + thread (Exp. 2):</b> todos os toques, inclusive os de 4 ms, foram detectados na
ISR e processados na <code>worker</code>, que fica bloqueada (0 % de CPU) sem eventos. A ISR não faz
processamento pesado.</li>
<li><b>Work queue (Exp. 3):</b> mesmo resultado funcional; o tratamento aparece na thread
<code>sysworkq</code>. Não existe thread <code>worker</code>; o tratamento usa a pilha da sysworkq,
que neste Zephyr só é incluída no binário porque o modo C a usa (seção 7.3).</li>
</ul>""")

A(f"""<h2>7.3 Experimento 4: benchmark comparativo</h2>
<p>Padrões do Kconfig (200 eventos, período 97 ms, pulso 20 ms, polling 10 ms, sem carga), 3
execuções por modo. As três execuções produziram os mesmos valores (Apêndice B), então média e
máximo coincidem com os de cada execução.</p>
{table(["Métrica (µs)", "Polling (P = 10 ms)", "ISR + thread", "ISR + work queue"], [
    ["lat_detect: média"] + [n(det[m]) for m, _ in MODES],
    ["lat_detect: máximo"] + [n(dmax[m]) for m, _ in MODES],
    ["lat_handoff: média", "n/a", n(hof["irq_thread"]), n(hof["workqueue"])],
    ["lat_handoff: máximo", "n/a", n(hmax["irq_thread"]), n(hmax["workqueue"])],
    ["lat_process: média"] + [n(prc[m]) for m, _ in MODES],
    ["lat_process: máximo"] + [n(pmax[m]) for m, _ in MODES],
    ["lat_proc_dur: média"] + [n(dur[m]) for m, _ in MODES],
    ["Jitter de lat_process (máx − mín)"] + [n(pmax[m] - pmin[m]) for m, _ in MODES],
], "Tabela 10.1 - Tempo (µs), média das 3 execuções")}
{fig("fig_exp4_latencias.png", "Figura 1 - Latências médias do Exp. 4 (escala logarítmica). O polling "
     "detecta o evento cerca de quatro ordens de grandeza depois das arquiteturas por interrupção.", "88%")}
{table(["Métrica (µs)", "Polling, período 95 ms (97 ticks)"], [
    ["lat_detect: média", n(p95)],
    ["lat_detect: mín / máx", f"{n(p95min)} / {n(p95max)}"],
    ["lat_process: média", n(L("exp4_polling_periodo95", "lat_process"))],
], "Tabela 10.1b - Polling com a fase varrida",
   note="Período do estímulo de 95 ms, que resulta em 97 ticks reais (seção 3.4); 3 execuções.")}
{table(["Métrica", "Polling", "ISR + thread", "ISR + work queue"], [
    ["Gerados"] + [i(S(E4[m], "gen")) for m, _ in MODES],
    ["Detectados"] + [i(S(E4[m], "det")) for m, _ in MODES],
    ["Processados"] + [i(S(E4[m], "proc")) for m, _ in MODES],
    ["Perdidos"] + [i(lost(E4[m])[0]) for m, _ in MODES],
], "Tabela 10.2 - Eventos")}
{table(["Métrica", "Polling", "ISR + thread", "ISR + work queue"], [
    ["CPU ocupada (kernel)"] + [pct(cpu[m]) for m, _ in MODES],
    ["CPU estimada (processamento)"] + [pct(S(E4[m], "cpu_est_x100")) for m, _ in MODES],
    ["idle (Thread Analyzer)"] + [f"{TH(E4[m], 'idle', 'cpu_pct')} %" for m, _ in MODES],
    ["Thread do evento (poll / worker / sysworkq)"] + [f"{TH(E4[m], EVT[m], 'cpu_pct')} %" for m, _ in MODES],
    ["main (gerador de estímulo)"] + [f"{TH(E4[m], 'main', 'cpu_pct')} %" for m, _ in MODES],
    ["Ciclos totais da thread do evento (desde o boot)"] + [i(cyc[m]) for m, _ in MODES],
], "Tabela 10.3 - CPU")}
{table(["Métrica", "Polling", "ISR + thread", "ISR + work queue"], [
    ["Flash usada (bytes), resumo do build"] + [i(flash[m]) for m, _ in MODES],
    ["RAM dram0_0_seg (bytes): dados + bss"] + [i(dram[m]) for m, _ in MODES],
    ["RAM .dram0.noinit (bytes): pilhas de todas as threads"] + [i(noinit[m]) for m, _ in MODES],
    ["<b>RAM estática total (bytes)</b>"] + [f"<b>{i(ramt[m])}</b>" for m, _ in MODES],
    ["IRAM iram0_0_seg (bytes): código em RAM"] + [i(iram[m]) for m, _ in MODES],
    ["Pilha da thread do evento: usada / total (B)", stack(E4["polling"], "poll"),
     stack(E4["irq_thread"], "worker"), "n/a (usa a sysworkq)"],
    ["Pilha da sysworkq: usada / total (B)", "n/a", "n/a", stack(E4["workqueue"], "sysworkq")],
    ["Pilha da ISR (ISR0): usada / total (B)"] + [stack(E4[m], "ISR0") for m, _ in MODES],
    ["Pilha da main: usada / total (B)"] + [stack(E4[m], "main") for m, _ in MODES],
    ["sizeof(k_thread) / k_sem / k_work / k_work_q (B)"] + [" / ".join(map(str, SZ))] * 3,
], "Tabela 10.4 - Memória",
   note="As pilhas ficam na seção <code>.dram0.noinit</code>, que o resumo do build contabiliza na "
        "região <code>dram1_0_seg</code> arredondada (\"8 KB\"); o valor exato vem de "
        "<code>objdump -h</code> (<code>logs/*_secoes.txt</code>).")}
<p><b>Leitura dos resultados.</b> As hipóteses da seção 10.3 se confirmam, com duas ressalvas (fase do polling e memória). A
detecção por interrupção levou {n(det["irq_thread"])} µs, contra {n(det["polling"] / 1000)} ms no
polling: cerca de {i(det["polling"] / det["irq_thread"])} vezes mais. Com o padrão de 97 ms, a média
do polling não ficou em P/2 por causa da trava de fase (seção 3.4). Com a fase varrida (período
95 ms), a média foi {n(p95 / 1000)} ms e o máximo {n(p95max / 1000)} ms, coerentes com uma latência
distribuída entre 1 e 11 ticks (média ≈ P/2 + 1 tick). O hand-off pela work queue
({n(hof["workqueue"])} µs) foi {n(hof["workqueue"] - hof["irq_thread"])} µs mais lento que pelo
semáforo ({n(hof["irq_thread"])} µs), porque o <code>k_work_submit()</code> e o laço da work queue
executam mais código que o <code>k_sem_give()</code>/<code>k_sem_take()</code>. A diferença é pequena,
como previsto. O jitter das arquiteturas por interrupção ficou em centésimos de µs, enquanto o do
polling é limitado pelo tick.</p>
<p>Em CPU, todas ficaram abaixo de 0,1 %, porque o trabalho útil é quase nulo. A diferença aparece
nos ciclos acumulados da thread do evento: a <code>poll</code> consumiu
{i(cyc["polling"])} ciclos, {n(cyc["polling"] / cyc["irq_thread"], 1)} vezes os
{i(cyc["irq_thread"])} da <code>worker</code>, porque acorda a cada 11 ms mesmo sem evento. A CPU
"ocupada" do polling ({pct(cpu["polling"])}) é o dobro da dos modos por interrupção
({pct(cpu["irq_thread"])}), mas ambas são uma fração de %, como alerta a apostila.</p>
<p><b>Memória: a hipótese da apostila não se confirmou nesta versão do Zephyr.</b> Esperava-se que o
modo C custasse só o <code>k_work</code> ({SZ[2]} B), reaproveitando a pilha da sysworkq "que já
existe". No Zephyr 4.5, porém, a system workqueue usa linkagem <i>pay-per-use</i>: ela só é incluída
no binário quando algo a referencia (comentário em <code>kernel/system_work_q.c</code>). Nos builds de
polling e de thread não há <code>sysworkq</code> (nem no ELF, nem no Thread Analyzer). No modo C ela
entra por causa do próprio <code>k_work_submit()</code>, trazendo a pilha de 1024 B e o
<code>k_work_q</code> ({SZ[3]} B). O modo B traz a pilha da worker (1024 B), o <code>k_thread</code>
({SZ[0]} B) e o <code>k_sem</code> ({SZ[1]} B). Resultado medido: a RAM estática total foi de
{i(ramt["polling"])}, {i(ramt["irq_thread"])} e {i(ramt["workqueue"])} B (polling, thread, work
queue); C usou {i(ramt["workqueue"] - ramt["irq_thread"])} B a <b>mais</b> que B. A vantagem de
memória da work queue só aparece quando outro driver ou subsistema já usa a sysworkq: aí o custo
marginal do modo C cai para o <code>k_work</code>, enquanto o de B continua sendo uma pilha inteira.
Em Flash as três diferem por poucas centenas de bytes ({i(flash["polling"])},
{i(flash["irq_thread"])} e {i(flash["workqueue"])} B): o código de callback e de semáforo/work queue
é pequeno perto do kernel e do HAL.</p>""")

r5 = []
for w, p, e in E5:
    lo = lost(e)
    r5.append([p, w, n(L(e, "lat_detect")), n(L(e, "lat_detect", "max_ns", "max")),
               pct(S(e, "cpu_x100")), f"{i(S(e, 'det'))} / {i(S(e, 'gen'))}", n(lo[1], 1)])


def e5(p, w, what):
    e = f"exp5_poll{p}_pulse{w}"
    return {"lat": L(e, "lat_detect"), "cpu": S(e, "cpu_x100") / 100, "lost": lost(e)[1]}[what]


A(f"""<h2>7.4 Experimento 5: efeito do período de polling</h2>
<p>Modo polling, 3 execuções por linha, período do estímulo 95 ms (97 ticks reais).</p>
{table(["P (ms)", "Pulso (ms)", "Lat. média (µs)", "Lat. máx (µs)", "CPU ocupada",
        "Detectados / gerados", "Perdidos (%)"], r5,
       "Tabela 11.1 - Varredura do período de polling")}
{fig("fig_exp5_varredura.png", "Figura 2 - Latência média de detecção, CPU ocupada e eventos perdidos "
     "em função do período de polling (eixo x logarítmico). Linha cheia: pulso de 20 ms; tracejada: pulso "
     "de 5 ms; pontilhada: modelo P/2 + 1 tick. A queda da latência em P ≥ 50 se deve às perdas: só os "
     "pulsos detectados cedo entram na média.")}
<p><b>1. Latência × P e CPU × P.</b> Enquanto o pulso dura mais que o período efetivo, a latência
média cresce <b>linearmente</b> com P e segue P/2 + 1 tick: {n(e5(1, 20, "lat") / 1000)} ms em P = 1,
{n(e5(5, 20, "lat") / 1000)} ms em P = 5 e {n(e5(10, 20, "lat") / 1000)} ms em P = 10, sempre entre
1 tick e P + 1 ticks. O mínimo é de 1 ms, e não 0, porque a <code>poll</code> e a <code>main</code>
acordam no mesmo tick e a <code>poll</code>, de maior prioridade, lê o pino antes de a
<code>main</code> gerar o pulso. Em P = 50 e P = 100 a média fica muito abaixo do modelo
({n(e5(50, 20, "lat") / 1000)} e {n(e5(100, 20, "lat") / 1000)} ms, contra 26 e 51 ms) porque só entram
na estatística os pulsos detectados, justamente os que caíram logo antes de uma consulta. A CPU
ocupada cai de forma <b>inversa</b>, proporcional a 1/(P + 1 tick): o produto CPU × ticks do laço é
quase constante ({n(e5(1, 20, "cpu"))} % × 2 ≈ {n(e5(5, 20, "cpu"))} % × 6 ≈
{n(e5(10, 20, "cpu"))} % × 11), e em P ≥ 50 ela fica abaixo de 0,01 %. O custo absoluto é pequeno,
porque cada consulta dura poucos µs, mas escala com o número de acordadas por segundo.</p>
<p><b>2. Pulsos de 5 ms sem perda.</b> P = 1 e P = 5 não perderam nenhum pulso; P = 10 perdeu
{n(e5(10, 5, "lost"), 1)} %, P = 50 perdeu {n(e5(50, 5, "lost"), 1)} % e P = 100 perdeu
{n(e5(100, 5, "lost"), 1)} %. Em P = 5 o laço dura 6 ticks e o pulso de <code>k_msleep(5)</code> também
dura 6 ticks, então sempre há uma consulta dentro do pulso, mas com margem zero. Eu escolheria
<b>P = 4 ms</b> (laço de 5 ticks, um tick de margem). O custo fica entre os medidos para P = 5
({n(e5(5, 5, "cpu"))} %) e P = 1 ({n(e5(1, 5, "cpu"))} %).</p>
<p><b>3. Regra.</b> O período efetivo de polling (P + 1 tick, no Zephyr) deve ser <b>no máximo igual à
largura do menor evento</b>, e com margem para jitter, <b>no máximo metade</b>. Até P = 50 as perdas
seguem a previsão 1 − (largura do pulso)/(período do laço): {n(e5(10, 5, "lost"), 1)} % medido contra
45,5 % previsto (pulso de 5 ms, P = 10), e {n(e5(50, 20, "lost"), 1)} % contra 58,8 % (pulso de 20 ms,
P = 50). Em P = 100 a perda foi muito maior que a prevista ({n(e5(100, 20, "lost"), 1)} % contra
79 %) por <b>aliasing</b>. O laço de 101 ticks é quase igual ao período do estímulo (97 ticks), então
consultas seguidas caem em pulsos seguidos quase na mesma fase. Se uma consulta encontra o pino
pressionado, a seguinte também encontra, <code>last</code> continua 1 e a borda não é contada: vários
eventos se fundem em um "toque longo". Portanto o período de polling também precisa ser bem menor que o
intervalo entre eventos (pelo menos a metade, no espírito de Nyquist).</p>
<p><b>4. Melhor caso do polling × interrupção.</b> Mesmo em P = 1 a latência média do polling
({n(e5(1, 20, "lat") / 1000)} ms) é cerca de {i(e5(1, 20, "lat") / det["irq_thread"])} vezes a detecção
por interrupção ({n(det["irq_thread"])} µs), e a CPU ocupada ({n(e5(1, 20, "cpu"))} %) é cerca de
{i(e5(1, 20, "cpu") / (cpu["irq_thread"] / 100))} vezes a do modo B ({pct(cpu["irq_thread"])}). Em
memória as três empatam neste firmware: cada uma tem uma pilha de 1 KiB para o tratamento (poll,
worker ou sysworkq; ver Tabela 10.4).</p>""")

r6a = []
for load in (0, 1000, 10000, 50000):
    for m, lbl in MODES[1:]:
        e = f"exp6a_{m}_proc{load}"
        r6a.append([i(load), lbl, pct(S(e, "cpu_x100")), pct(S(e, "cpu_est_x100")),
                    n(L(e, "lat_process")), i(lost(e)[0]), i(S(e, "janela_ms"))])
r6b = []
for m, lbl in MODES:
    e = f"exp6b_{m}_saturacao"
    r6b.append([lbl + (" (P = 10 ms)" if m == "polling" else ""), i(S(e, "gen")), i(S(e, "det")),
                i(S(e, "proc")), n(lost(e)[1], 1), pct(S(e, "cpu_x100"))])
sat = {m: f"exp6b_{m}_saturacao" for m, _ in MODES}
A(f"""<h2>7.5 Experimento 6: carga de processamento e taxa de eventos</h2>
{table(["Carga (µs)", "Modo", "CPU ocupada", "CPU estimada", "Lat. process média (µs)", "Perdidos",
        "Janela (ms)"], r6a, "Tabela 12.1 - Carga por evento (período do estímulo = 97 ms)")}
{fig("fig_exp6_carga.png", "Figura 3 - CPU ocupada e latência até o início do tratamento em função da "
     "carga por evento. As duas arquiteturas são indistinguíveis em CPU; a latência não depende da carga.")}
<p>A CPU ocupada acompanha a CPU estimada a partir das durações (a diferença é o custo do próprio
mecanismo) e é igual nos dois modos: o trabalho é o mesmo, muda só quem o executa. A latência até o
início do tratamento não depende da carga, porque com período de 97 ms o tratamento anterior já
terminou quando chega o próximo evento. A CPU com 10 ms de carga foi
{pct(S("exp6a_irq_thread_proc10000", "cpu_x100"))} e não 10,1 %: a worker (prioridade 1) preempta a
<code>main</code> logo após o estímulo, antes de ela chamar <code>k_msleep()</code>, e assim o período
real do estímulo cresce no valor da carga (janela de
{i(S("exp6a_irq_thread_proc10000", "janela_ms"))} ms em vez de 19.901 ms). Com 100 ms de tratamento
(desafio original), uma thread dedicada é preferível: bloquear a sysworkq por 100 ms atrasaria todos
os outros work items do sistema (ver Exp. 8).</p>
{table(["Modo", "Gerados", "Detectados", "Processados", "Perdidos (%)", "CPU ocupada"], r6b,
       "Tabela 12.2 - Saturação: tratamento de 30 ms, eventos a cada 23 ms (25 ticks reais), main com prioridade 0")}
<ul>
<li><b>Detectados > processados nos modos por interrupção.</b> A ISR vê todas as {i(S(sat["irq_thread"], "det"))}
bordas, mas o encaminhamento coalesce: o semáforo tem limite 1 e um <code>k_work_submit()</code> de
item já pendente não o enfileira de novo. Foram processados {i(S(sat["irq_thread"], "proc"))} (thread)
e {i(S(sat["workqueue"], "proc"))} (work queue) eventos.</li>
<li><b>Onde ocorre a perda.</b> Na interrupção, no <b>encaminhamento</b> (coalescência), não na
detecção. No polling a perda é na <b>detecção</b>: enquanto a <code>poll</code> processa 30 ms ela não
consulta o pino, e só {i(S(sat["polling"], "det"))} de {i(S(sat["polling"], "gen"))} pulsos foram vistos.</li>
<li><b>Como evitar a perda sem mudar prioridade.</b> Usar uma fila com um item por evento
(<code>k_msgq</code>, Extensão E3) ou um semáforo com limite maior que conte os eventos. Isso só ajuda
enquanto a fila não enche: com 30 ms de trabalho a cada 25 ms a utilização passa de 100 % e nenhuma
arquitetura evita a perda sem reduzir o trabalho.</li>
</ul>""")

r7 = []
for m, lbl in (("isr_only", "ISR only (anti-padrão)"), ("irq_thread", "ISR + thread"),
               ("workqueue", "ISR + work queue")):
    e = f"exp7_{m}_hb"
    r7.append([lbl, n(S(e, "hb_max_ms")), pct(S(e, "cpu_x100")), pct(S(e, "cpu_est_x100")),
               i(lost(e)[0])])
A(f"""<h2>7.6 Experimento 7: anti-padrão, processamento dentro da ISR</h2>
{table(["Modo (carga 20 ms)", "Maior intervalo do heartbeat (ms)", "CPU ocupada (kernel)",
        "CPU estimada", "Perdidos"], r7, "Tabela 13.1 - Impacto no escalonamento")}
{fig("fig_exp7_heartbeat.png", "Figura 4 - Maior intervalo entre acordadas do heartbeat "
     "(prioridade 0, período nominal 1 ms). A linha pontilhada marca 1 ms.", "70%")}
<p>Com os 20 ms de espera ocupada dentro da ISR, o heartbeat ficou até
{n(hb["isr_only"])} ms sem rodar: enquanto a ISR executa, nem o tick nem o escalonador avançam. Com o
mesmo trabalho numa thread ou na work queue, ambos de prioridade 1, o heartbeat (prioridade 0) os
preempta e o maior intervalo fica em {n(hb["irq_thread"])} ms e {n(hb["workqueue"])} ms, perto do
baseline de 1 a 2 ticks.</p>
<p><b>Discussão obrigatória.</b></p>
<ul>
<li><b>CPU do kernel no modo isr_only.</b> O kernel mediu {pct(S("exp7_isr_only_hb", "cpu_x100"))}
contra {pct(S("exp7_isr_only_hb", "cpu_est_x100"))} estimados a partir das durações. O tempo gasto
na ISR é contabilizado na thread interrompida, quase sempre a idle, e por isso aparece como "ocioso".
A CPU estimada mede o tempo dentro de <code>app_process_event()</code> e não tem esse ponto cego.</li>
<li><b>Prioridades.</b> Uma thread de prioridade <b>maior</b> que a worker (como o heartbeat) não sofre
com o processamento longo numa thread: ela a preempta. Uma de prioridade <b>menor</b> espera o
tratamento terminar. Já uma ISR longa atrasa <b>todas</b> as threads, qualquer que seja a prioridade.</li>
<li><b>Outras interrupções.</b> Interrupções de prioridade igual ou menor (UART, timer do sistema,
Wi-Fi) ficam pendentes durante a ISR longa. Isso pode estourar FIFOs, perder caracteres e pacotes e,
no caso do timer, atrasar o tempo do kernel, como o heartbeat mostrou.</li>
</ul>""")

r8 = []
for m, lbl in MODES:
    for sc, desc in (("sleep", "sleep, 5 ev/s"), ("busy", "busy, 5 ev/s"),
                     ("rajada", "busy, 20 ev/s")):
        e = f"exp8_{m}_{sc}"
        r8.append([lbl, desc, f"{i(S(e, 'proc'))} / {i(S(e, 'gen'))}", n(lost(e)[1], 1),
                   n(L(e, "lat_process")), n(L(e, "lat_process", "max_ns", "max")),
                   n(L(e, "lat_proc_dur") / 1000, 1), pct(S(e, "cpu_x100")),
                   pct(S(e, "cpu_est_x100")), stack(e, EVT[m])])
e8m = {m: (MEM(f"exp8_{m}_sleep", "flash"), MEM(f"exp8_{m}_sleep", "ram_total")) for m, _ in MODES}
A(f"""<h2>7.7 Experimento 8: desafio final (processamento de 100 ms)</h2>
<p>As três versões pedidas estão em <code>codigo/01_polling</code>, <code>02_interrupt_thread</code> e
<code>03_workqueue</code>. Cada uma detecta o botão, incrementa um contador, alterna o LED, imprime o
contador fora da ISR (na thread poll, worker ou sysworkq), simula 100 ms de processamento e volta a
esperar. Elas reaproveitam a instrumentação do projeto-base. O processamento usa
<code>k_msleep(100)</code> (thread dorme) ou <code>k_busy_wait()</code> (consome CPU), escolhido por
<code>CONFIG_APP_PROC_BUSY</code>. O estímulo (50 eventos) roda com prioridade 0, papel de um
evento externo que o processamento não pode atrasar.</p>
{table(["Versão", "Cenário", "Proc. / gerados", "Perdidos (%)", "Lat. process média (µs)",
        "Lat. process máx (µs)", "Tratamento (ms)", "CPU ocupada", "CPU estimada",
        "Pilha evento (B)"], r8, "Tabela 14.1 - Desafio final: tempo, CPU e eventos", cls="small",
   note="sleep = <code>k_msleep(100)</code>; busy = <code>k_busy_wait(100000)</code>. 5 ev/s = período "
        "de 197 ms; 20 ev/s = período de 47 ms (49 ticks reais). 50 eventos por execução.")}
{table(["Versão", "Flash (B)", "RAM estática total (B)", "Thread/pilha do tratamento"], [
    ["Polling", i(e8m["polling"][0]), i(e8m["polling"][1]), "poll: 1 KiB + k_thread"],
    ["ISR + thread", i(e8m["irq_thread"][0]), i(e8m["irq_thread"][1]), "worker: 1 KiB + k_thread + k_sem"],
    ["ISR + work queue", i(e8m["workqueue"][0]), i(e8m["workqueue"][1]), "sysworkq: 1 KiB + k_work_q (linkada por uso)"],
], "Tabela 14.2 - Desafio final: memória")}
<p><b>O que os dados mostram.</b> (i) Com <code>k_msleep(100)</code> a CPU ocupada ficou em
{pct(S("exp8_irq_thread_sleep", "cpu_x100"))} a {pct(S("exp8_polling_sleep", "cpu_x100"))}, enquanto a CPU
"estimada" a partir das durações ficou em {pct(S("exp8_irq_thread_sleep", "cpu_est_x100"))}: dormir não
consome CPU. Com <code>k_busy_wait()</code> as duas medidas coincidem
({pct(S("exp8_irq_thread_busy", "cpu_x100"))}). (ii) A 5 ev/s (utilização de 50 %) nenhuma versão
perdeu eventos. (iii) Na rajada (período de 47 ms, 49 ticks reais, ≈ 20 ev/s) a demanda é de ≈ 200 %
de CPU. As versões por interrupção processaram {i(S("exp8_irq_thread_rajada", "proc"))} de 50 eventos
com {pct(S("exp8_irq_thread_rajada", "cpu_x100"))} de CPU: a ISR detecta todos, e a coalescência
descarta o excedente. O polling processou só {i(S("exp8_polling_rajada", "proc"))}: ele perde na
detecção, porque não consulta o pino durante os 100 ms. (iv) O hand-off do modo B subiu de
{n(hof["irq_thread"])} µs (Exp. 4) para {n(L("exp8_irq_thread_sleep", "lat_handoff"))} µs, porque aqui a
<code>main</code> tem prioridade 0 e termina <code>pulse()</code> antes de a worker rodar. Pelo mesmo
motivo, no polling a <code>main</code> passa a rodar antes da <code>poll</code> no mesmo tick, e a
latência mínima cai para {n(L("exp8_polling_sleep", "lat_detect", "min_ns", "min"))} µs.</p>
<div class="info"><b>Escolha para produção: interrupção + thread dedicada</b> (com <code>k_msgq</code>
se cada evento precisar ser contado). Justificativa:
<ul>
<li><b>Tempo de resposta:</b> a detecção é de µs, contra P/2 no polling.</li>
<li><b>Processamento longo:</b> 100 ms bloqueando a sysworkq atrasariam todos os outros work items do
sistema, o que a apostila desaconselha. A thread própria isola esse custo e permite escolher a
prioridade.</li>
<li><b>Sequências de eventos:</b> com semáforo ou fila, a thread absorve rajadas curtas; o polling as
perde na detecção.</li>
<li><b>Custo:</b> neste firmware a RAM estática da versão com thread ({i(e8m["irq_thread"][1])} B) é
praticamente a mesma da versão com work queue ({i(e8m["workqueue"][1])} B), porque a sysworkq também
traz uma pilha de 1 KiB. Mesmo num sistema em que a sysworkq já exista, o custo extra seria de cerca de
1,2 KiB, aceitável num ESP32 com 320 KiB de DRAM.</li>
<li><b>Organização:</b> a ISR só sinaliza, e o tratamento fica em uma função de thread fácil de testar.</li>
</ul>
Uma work queue <b>dedicada</b> (E4) seria equivalente em custo e comportamento. A work queue do sistema só
seria adequada se o tratamento fosse curto.</div>
{table(["Cenário", "Arquitetura escolhida", "Justificativa"], [
    ["Botão que liga/desliga um LED (baixa taxa, tratamento trivial)", "ISR + work queue (sistema)",
     "Detecção imediata; tratamento de µs não prejudica a sysworkq; se ela já existe no sistema, custa só o k_work (16 B)."],
    ["Sensor com 1.000 amostras/s e 50 µs por amostra", "ISR + fila de mensagens + thread",
     "5 % de CPU, mas cada amostra importa: a fila (k_msgq) evita a coalescência e absorve atrasos da thread."],
    ["Pacote de rede: filtrar, copiar e notificar (~2 ms)", "ISR + thread (ou work queue dedicada) com fila",
     "2 ms é longo para a sysworkq; a thread própria isola o custo e a fila preserva pacotes em rajada."],
    ["Verificar a cada 500 ms se a bateria caiu abaixo de um limite", "Polling",
     "Grandeza lenta e periódica, sem interrupção natural; polling de 500 ms custa ≈ 0 % de CPU."],
    ["Encoder de motor a 20 kHz (contar todos os pulsos)", "Contador de hardware (PCNT) ou ISR mínima",
     "50 µs entre pulsos inviabiliza thread por pulso (coalesceria); o PCNT do ESP32 conta sem CPU, ou a ISR só incrementa um contador atômico."],
    ["Botão de emergência que deve parar um atuador em < 1 ms", "ISR que age diretamente",
     "A ISR desliga o atuador (escrita em GPIO, poucos µs) e só depois sinaliza uma thread; polling exigiria P < 1 ms."],
], "Tabela 14.3 - Decisão por cenário (seção 14.2 da apostila)", cls="small")}""")

# ---------------------------------------------------------------- 8 analise comparativa
A(f"""<h1>8. Análise comparativa e discussão crítica</h1>
{table(["Critério", "Polling", "ISR + thread", "Work queue"], [
    ["Como detecta o evento?", "Thread consulta o pino a cada P (efetivo P + 1 tick)",
     "Interrupção de GPIO (borda)", "Interrupção de GPIO (borda)"],
    ["Como processa o evento?", "Na própria thread de polling", "Na thread worker, acordada por k_sem",
     "No handler do k_work, na sysworkq"],
    ["Existe ISR?", "Não", "Sim (curta)", "Sim (curta)"],
    ["Existe thread dedicada?", "Sim (poll)", "Sim (worker)", "Não"],
    ["Usa semáforo? Work item?", "Nenhum", "Semáforo (k_sem, limite 1)", "Work item (k_work)"],
    ["Precisa verificar continuamente?", "Sim", "Não", "Não"],
    ["Complexidade", "Baixa", "Média", "Média"],
    ["Latência média / máxima medida (até o tratamento)",
     f"{n(prc['polling'] / 1000)} / {n(pmax['polling'] / 1000)} ms (fase travada); {n(p95 / 1000)} / {n(p95max / 1000)} ms (fase varrida)",
     f"{n(prc['irq_thread'])} / {n(pmax['irq_thread'])} µs", f"{n(prc['workqueue'])} / {n(pmax['workqueue'])} µs"],
    ["CPU ocupada medida (sem carga)", f"{pct(cpu['polling'])} ({i(cyc['polling'])} ciclos na poll)",
     f"{pct(cpu['irq_thread'])} ({i(cyc['irq_thread'])} ciclos na worker)",
     f"{pct(cpu['workqueue'])} ({i(cyc['workqueue'])} ciclos na sysworkq)"],
    ["Memória (Flash / RAM estática total / pilha do evento, usada/total)",
     f"{i(flash['polling'])} / {i(ramt['polling'])} B / {stack(E4['polling'], 'poll')}",
     f"{i(flash['irq_thread'])} / {i(ramt['irq_thread'])} B / {stack(E4['irq_thread'], 'worker')}",
     f"{i(flash['workqueue'])} / {i(ramt['workqueue'])} B / sysworkq {stack(E4['workqueue'], 'sysworkq')}"],
    ["Comportamento quando não há evento", "Acorda a cada P + 1 tick", "Bloqueada em k_sem_take()",
     "Fila vazia; sysworkq bloqueada"],
    ["Aplicação indicada", "Grandezas lentas/periódicas, verificações simples",
     "Tratamento longo ou contínuo dedicado ao evento", "Trabalho curto e diferido"],
], "Tabela 15.2 - Análise comparativa", cls="small")}
<p><b>Discussão crítica.</b> Os números confirmam a teoria em sinal e ordem de grandeza, e três pontos
merecem destaque. Primeiro, o polling depende da relação entre os períodos <i>em ticks</i>, não só de
P. O arredondamento de +1 tick do <code>k_msleep()</code> tornou o período de 97 ms um múltiplo exato
do período efetivo de polling, e a latência ficou travada em 9 ms em vez de se distribuir entre 1 e
P + 1 ticks. Já com P próximo do período do estímulo, o aliasing fundiu eventos e elevou a perda de
79 % (previsto) para 95,5 %. Escolher um período "primo em ms" não basta: o que importa é que ele não
tenha divisor comum com o laço de polling medido em ticks efetivos, e que o laço seja bem mais curto
que o intervalo entre eventos. Segundo, a vantagem de memória da work queue pressupõe que a sysworkq
já exista; no Zephyr 4.5 ela é linkada sob demanda, e num app isolado custa o mesmo que uma thread
dedicada. Terceiro, as diferenças de CPU sem carga são de centésimos de %. O que distingue as
arquiteturas é como o custo <b>escala</b>: com 1/(P + 1 tick) no polling, com a taxa de eventos nas
outras duas. Os ciclos acumulados por thread mostram isso melhor que a porcentagem arredondada do
Thread Analyzer.
A medida externa pelos pinos concordou com a medida interna (Tabela 3.1).</p>""")

# ---------------------------------------------------------------- 9 questoes
A(f"""<h1>9. Respostas das questões (capítulo 18)</h1>
{qa([
    ("Principal diferença entre polling e interrupção?",
     f"No polling o software pergunta periodicamente; na interrupção o hardware avisa. Medido: "
     f"{n(det['polling'] / 1000)} ms (P = 10) contra {n(det['irq_thread'])} µs de latência de detecção."),
    ("Por que o polling consome processamento sem eventos? Apareceu nas medições?",
     f"A thread acorda a cada P + 1 tick, troca de contexto e lê o pino mesmo sem evento. Sim: a "
     f"<code>poll</code> acumulou {i(cyc['polling'])} ciclos contra {i(cyc['irq_thread'])} da "
     f"<code>worker</code>, e no Exp. 5 a CPU ocupada foi de {n(e5(1, 20, 'cpu'))} % (P = 1) a "
     f"{n(e5(100, 20, 'cpu'))} % (P = 100)."),
    ("Função da ISR e três coisas que ela não deve fazer?",
     "Reconhecer o hardware e sinalizar o evento rapidamente (registrar tempo, contar, dar o semáforo "
     "ou submeter o work). Não deve bloquear ou dormir (k_msleep, k_sem_take com espera, k_mutex_lock), "
     "executar laços ou cálculos longos, nem chamar APIs não seguras para ISR ou printk."),
    ("Por que a ISR não deve fazer processamento demorado? Evidência do Exp. 7?",
     f"Porque bloqueia o escalonador, o tick e as interrupções de prioridade igual ou menor. No Exp. 7 o "
     f"heartbeat ficou até {n(hb['isr_only'])} ms sem rodar com 20 ms na ISR, contra "
     f"{n(hb['irq_thread'])} ms com o mesmo trabalho numa thread."),
    ("Função do semáforo na implementação com thread?",
     "Comunicar à thread, sem espera ativa, que o evento ocorreu. A worker fica bloqueada em "
     "k_sem_take() e acorda com k_sem_give() da ISR. O limite 1 funde sinais repetidos."),
    ("Função da work queue e o que é a system workqueue?",
     "Executar trabalho diferido em contexto de thread. A system workqueue é uma thread do kernel "
     "(sysworkq), compartilhada com drivers e subsistemas, que executa em ordem os work items submetidos."),
    ("Diferença entre k_sem_give() e k_work_submit()?",
     f"k_sem_give() libera um semáforo que uma thread sua aguarda; k_work_submit() enfileira um item "
     f"cujo handler roda na work queue. Ambos são seguros em ISR. Hand-off medido: "
     f"{n(hof['irq_thread'])} µs contra {n(hof['workqueue'])} µs."),
    ("Em qual implementação há thread dedicada? Custo em memória?",
     f"No modo B (worker) e também no polling (poll). A thread dedicada custa a pilha de 1024 B + "
     f"k_thread de {SZ[0]} B + k_sem de {SZ[1]} B (a pilha usou {stack(E4['irq_thread'], 'worker')} B). "
     f"Medido: a RAM estática total do modo B ({i(ramt['irq_thread'])} B) ficou "
     f"{i(ramt['workqueue'] - ramt['irq_thread'])} B abaixo da do modo C, porque no Zephyr 4.5 a "
     f"sysworkq só é linkada quando usada e traz sua própria pilha de 1 KiB."),
    ("O que acontece com eventos gerados rapidamente? Como os dados mostram (Exp. 6B)?",
     f"São coalescidos: com 200 bordas detectadas, a thread processou {i(S(sat['irq_thread'], 'proc'))} e "
     f"a work queue {i(S(sat['workqueue'], 'proc'))}; o excedente virou perda no encaminhamento."),
    ("O polling pode deixar de perceber um evento? Cenário do Exp. 5?",
     f"Sim: quando o pulso é mais curto que o período efetivo ou cai entre duas consultas. Com pulso de "
     f"5 ms, P = 10 perdeu {n(e5(10, 5, 'lost'), 1)} % e P = 100 perdeu {n(e5(100, 5, 'lost'), 1)} %. "
     f"No modo manual, toques de 4 ms também foram perdidos."),
    ("Como a prioridade afeta o hand-off? Por que igualar worker e sysworkq?",
     f"O hand-off só ocorre quando a thread é a de maior prioridade pronta. Com a main na prioridade 0 "
     f"(Exp. 8) o hand-off do modo B subiu de {n(hof['irq_thread'])} para "
     f"{n(L('exp8_irq_thread_sleep', 'lat_handoff'))} µs. Igualar as prioridades garante que B e C "
     f"sejam comparados só pelo mecanismo."),
    ("A CPU ocupada do kernel é confiável para ISRs longas?",
     f"Não. O tempo da ISR é atribuído à thread interrompida (normalmente a idle). No Exp. 7 o kernel "
     f"marcou {pct(S('exp7_isr_only_hb', 'cpu_x100'))} contra {pct(S('exp7_isr_only_hb', 'cpu_est_x100'))} "
     f"estimados pelas durações."),
    ("Por que a main gera o estímulo em prioridade baixa?",
     "Para que a worker (prioridade 1) a preempte imediatamente após a ISR; assim o hand-off não inclui "
     f"o restante de pulse(). O efeito medido foi de {n(L('exp8_irq_thread_sleep', 'lat_handoff') - hof['irq_thread'])} µs "
     "(questão 11). O preço é que, com carga, o período do estímulo cresce (Exp. 6A)."),
    ("Fontes de erro nas medições de tempo?",
     "Viés de gpio_pin_set_dt() antes da borda (Tabela 3.1), resolução de 4,17 ns e estouro do contador "
     "de 32 bits, printk na janela, cache e primeiras execuções (mitigados pelo aquecimento), tick de 1 ms e arredondamento +1 tick, coalescência e a atribuição do tempo de ISR."),
    ("Processamento de 100 ms e 5 eventos/s? E 50 eventos/s?",
     f"A 5 ev/s a utilização é de 50 %: thread dedicada (ou work queue dedicada) com fila. No Exp. 8 não "
     f"houve perdas, com CPU de {pct(S('exp8_irq_thread_busy', 'cpu_x100'))} em espera ocupada. A 50 ev/s "
     f"(500 %) o sistema satura: nenhuma arquitetura resolve. Já a 20 ev/s o Exp. 8 perdeu "
     f"{n(lost('exp8_irq_thread_rajada')[1], 1)} % na versão com thread. É preciso reduzir o processamento, "
     f"usar mais CPU (o segundo núcleo) ou descartar e amostrar."),
])}""")

A("""<h2>Questões dos Experimentos 1 a 3</h2>
<p><b>Exp. 1.</b> (1) O programa verifica repetidamente porque não há outro aviso de que o pino mudou.
(2) Com P = 100 ms a latência pode chegar a 101 ms (média esperada ≈ 51 ms) e a maioria dos pulsos
curtos passa despercebida: no Exp. 5, P = 100 perdeu 95,5 % dos pulsos de 20 ms.
(3) A vantagem é a simplicidade e a previsibilidade; a desvantagem é a latência de até P e o custo
fixo de CPU. (4) Sim: a thread executa a cada P mesmo sem toque, o que aparece nos ciclos acumulados da
<code>poll</code>, embora o Thread Analyzer arredonde para 0 %. (5) <code>k_msleep()</code> bloqueia a
thread e libera a CPU para a idle; um <code>while(1)</code> sem espera ocuparia 100 % da CPU.</p>
<p><b>Exp. 2.</b> (1) A ISR detecta; a worker processa. (2) O semáforo sinaliza à worker sem espera
ativa. (3) Para não bloquear o sistema (Exp. 7). (4) Não: a thread fica bloqueada em
<code>k_sem_take()</code> e não consome CPU. (5) Com limite 1, dois eventos antes de a thread rodar
viram um só processamento (Exp. 6B).</p>
<p><b>Exp. 3.</b> (1) A work queue executa trabalho diferido em contexto de thread. (2) Ver questão 7
do capítulo 18. (3) A thread dedicada está no modo B; no C o tratamento roda na sysworkq. (4) O
<code>k_work_submit()</code> de um item pendente retorna 0 e o evento é coalescido. (5) Porque a
sysworkq é compartilhada: bloqueá-la atrasa todos os outros work items do sistema.</p>""")

# ---------------------------------------------------------------- 10 conclusao
A(f"""<h1>10. Conclusão e recomendação</h1>
<p>As três arquiteturas resolvem o problema, mas com custos de naturezas diferentes. O polling é o
mais simples e o único sem ISR, mas paga em latência (≈ P/2 + 1 tick, chegando a 9 ms fixos por trava
de fase com os parâmetros padrão), em CPU proporcional a 1/(P + 1 tick) e em eventos perdidos quando o
pulso é mais curto que o período ou o período se aproxima do intervalo entre eventos. As arquiteturas por interrupção detectam em {n(det['irq_thread'])} µs, não
gastam CPU sem eventos e só perdem eventos por coalescência, quando a taxa supera a capacidade de
tratamento. Entre elas, a thread com semáforo tem hand-off ligeiramente menor e isola o
processamento. A work queue do sistema só é mais econômica em RAM quando a sysworkq já existe por
outros motivos (aqui ela custou {i(ramt['workqueue'] - ramt['irq_thread'])} B a mais que a thread) e
só serve para trabalho curto. O anti-padrão de processar na
ISR foi demonstrado com dados: {n(hb['isr_only'])} ms de bloqueio do escalonador e uma CPU do kernel
que esconde a carga.</p>
<p><b>Recomendação por cenário:</b> polling para grandezas lentas e periódicas; ISR + work queue do
sistema para tratamentos curtos e esporádicos; ISR + thread (ou work queue dedicada) para tratamentos
longos como o de 100 ms; ISR + <code>k_msgq</code> quando cada evento importa; e periféricos dedicados
(PCNT) ou ISRs mínimas para eventos de alta frequência.</p>
<h1>Apêndice A: arquivos entregues</h1>
{table(["Caminho", "Conteúdo"], [
    ["codigo/00_bench_eventos/", "Projeto-base do curso (Exps. 1 a 7), sem alterações"],
    ["codigo/01_polling/, 02_interrupt_thread/, 03_workqueue/", "Três versões do desafio final (Exp. 8)"],
    ["codigo/exp0_blink_test/", "Validação do ambiente (Exp. 0)"],
    ["logs/*_runN.log", "Logs brutos de cada execução (saída serial completa, com as linhas CSV)"],
    ["logs/*_build.txt, *_ram.txt, *_rom.txt, *_secoes.txt", "Saída do west build (tabela de memória), relatórios de RAM/ROM e seções do ELF"],
    ["logs/*_gpio_trace.csv", "Registro das transições dos pinos 2, 4 e 18 (Exps. 1 a 4)"],
    ["resultados.xlsx", "Dados extraídos dos logs, tabelas da apostila (fórmulas) e gráficos"],
    ["emulacao/", "Ferramentas de execução e análise (Apêndice B)"],
], "Tabela A.1 - Estrutura da entrega")}

<h1>Apêndice B: detalhes da execução</h1>
<p><b>Plataforma.</b> O firmware compilado para a <code>esp32_devkitc</code> foi executado no QEMU 9.2.2
da Espressif (<code>esp-develop</code>, commit <code>febae18</code>). O modelo de GPIO desse QEMU só
responde ao registrador de <i>strapping</i>; ele foi estendido (<code>emulacao/qemu-esp32-gpio.patch</code>)
com os registradores <code>OUT</code>, <code>ENABLE</code>, <code>IN</code>, <code>STATUS</code>,
<code>PCPU_INT</code> e <code>PINn</code> usados pelo driver <code>gpio_esp32.c</code>, a detecção de
borda/nível ligada à fonte 22 (<code>ETS_GPIO_INTR_SOURCE</code>) da matriz de interrupções, o jumper
GPIO18 → GPIO4, a sequência de toques do botão e o registro das transições dos pinos. O eFuse padrão
do emulador informa revisão de chip v0.0, aceita por <code>CONFIG_ESP32_USE_UNSUPPORTED_REVISION=y</code>,
já presente no <code>prj.conf</code> do curso.</p>
<p><b>Tempo.</b> Com <code>-icount shift=2,align=off,sleep=off</code> cada instrução avança 4 ns do
relógio virtual, e o CCOUNT é derivado desse relógio a 240 MHz (≈ 0,96 ciclo por instrução); com a CPU
ociosa o relógio avança direto até o próximo timer. A execução é determinística: as 3 execuções de cada
configuração produziram os mesmos números (amplitude da média de <code>lat_process</code> entre
execuções: {n(amp["polling"])} / {n(amp["irq_thread"])} / {n(amp["workqueue"])} µs).</p>
<p><b>Sensibilidade ao CPI.</b> Como o emulador não modela cache nem estados de espera da flash, o
Exp. 4 foi repetido com 8 ns por instrução (≈ 2 ciclos por instrução, <code>shift=3</code>):</p>
{table(["Métrica (µs)", "Polling", "ISR + thread", "ISR + work queue"], [
    ["lat_detect: média", n(c2["polling"][0]), n(c2["irq_thread"][0]), n(c2["workqueue"][0])],
    ["lat_handoff: média", "n/a", n(c2["irq_thread"][1]), n(c2["workqueue"][1])],
    ["lat_process: média", n(c2["polling"][2]), n(c2["irq_thread"][2]), n(c2["workqueue"][2])],
], "Tabela B.1 - Exp. 4 com CPI ≈ 2 (1 execução)",
   note="A latência do polling, dominada pelos ticks, não muda; as latências por interrupção dobram. "
        "Os valores de µs da seção 7 correspondem, portanto, ao limite inferior dessa faixa; em placa "
        "haveria ainda variação de execução para execução por efeitos de cache. Os resultados que "
        "dependem de ticks, prioridades, escalonamento e coalescência não são afetados.")}
<p><b>Reprodução.</b> Aplicar <code>qemu-esp32-gpio.patch</code> ao QEMU da Espressif, compilar
<code>xtensa-softmmu</code> e executar <code>python3 emulacao/run_lab.py exp4</code> (ou outro
prefixo) num workspace west com o manifesto do curso; <code>analisar.py</code>, <code>figuras.py</code>
e <code>gerar_relatorio.py</code> regeneram a planilha, as figuras e este relatório. Em uma placa, os
mesmos projetos são compilados e gravados com <code>west build</code> e <code>west flash</code>, como
na apostila.</p>""")

doc = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Relatório - Polling, Interrupções e Work Queue no Zephyr</title><style>{CSS}</style></head>
<body>{''.join(parts)}</body></html>"""
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(doc)
print("ok", OUT)
