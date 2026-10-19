#!/usr/bin/env python3
"""Gera as figuras do relatorio a partir de /home/user/work/dados.pkl (analisar.py)."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/user/work/fig")
OUT.mkdir(parents=True, exist_ok=True)
D = pd.read_pickle("/home/user/work/dados.pkl")
lat, summ = D["lat"], D["summ"]

# Paleta de referencia (slots categoricos fixos por entidade)
COR = {"polling": "#2a78d6", "irq_thread": "#eb6834", "workqueue": "#1baf7a",
       "isr_only": "#eda100"}
NOME = {"polling": "Polling", "irq_thread": "ISR + thread", "workqueue": "ISR + work queue",
        "isr_only": "ISR only (anti-padrão)"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "legend.frameon": False, "figure.dpi": 200,
})


def lat_mean(exp, met, col="med_ns"):
    s = lat[(lat.exp == exp) & (lat.metrica == met)][col]
    return s.mean() / 1000 if len(s) else float("nan")


def lat_max(exp, met):
    s = lat[(lat.exp == exp) & (lat.metrica == met)]["max_ns"]
    return s.max() / 1000 if len(s) else float("nan")


def sum_mean(exp, col):
    return summ[summ.exp == exp][col].mean()


def fmt_us(v):
    return f"{v:,.0f}".replace(",", ".") if v >= 100 else f"{v:.2f}".replace(".", ",")


# --- Figura 1: Exp. 4 latencias (escala log) ---------------------------------
fig, ax = plt.subplots(figsize=(6.6, 3.0))
mets = [("lat_detect", "detecção"), ("lat_handoff", "hand-off"), ("lat_process", "estímulo → tratamento")]
w = 0.26
for k, m in enumerate(("polling", "irq_thread", "workqueue")):
    xs, ys = [], []
    for i, (met, _) in enumerate(mets):
        v = lat_mean(f"exp4_{m}", met)
        if v == v:
            xs.append(i + (k - 1) * w)
            ys.append(v)
    bars = ax.bar(xs, ys, width=w - 0.03, color=COR[m], label=NOME[m], zorder=2)
    for x, y in zip(xs, ys):
        ax.text(x, y * 1.25, fmt_us(y), ha="center", va="bottom", fontsize=7.5, color=INK)
ax.set_yscale("log")
ax.set_ylim(0.5, 60000)
ax.set_xticks(range(len(mets)), [m[1] for m in mets])
ax.set_ylabel("latência média (µs, escala log)")
ax.set_title("Exp. 4: latências médias por arquitetura", loc="left")
ax.legend(loc="upper right", ncol=3, fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "fig_exp4_latencias.png")
plt.close(fig)

# --- Figura 2: Exp. 5 small multiples ----------------------------------------
P = [1, 5, 10, 50, 100]
fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.6))
for pulse, ls, mk in ((20, "-", "o"), (5, "--", "s")):
    e = [f"exp5_poll{p}_pulse{pulse}" for p in P]
    latv = [lat_mean(x, "lat_detect") / 1000 for x in e]
    cpu = [sum_mean(x, "cpu_x100") / 100 for x in e]
    lost = [100 * (1 - sum_mean(x, "proc") / sum_mean(x, "gen")) for x in e]
    for ax, y in zip(axs, (latv, cpu, lost)):
        ax.plot(P, y, ls, marker=mk, ms=4.5, lw=1.6, color=COR["polling"],
                label=f"pulso {pulse} ms")
axs[0].set_title("Latência média de detecção", loc="left")
axs[0].set_ylabel("ms")
axs[1].set_title("CPU ocupada (kernel)", loc="left")
axs[1].set_ylabel("%")
axs[2].set_title("Eventos perdidos", loc="left")
axs[2].set_ylabel("%")
for ax in axs:
    ax.set_xscale("log")
    ax.set_xticks(P, [str(p) for p in P])
    ax.minorticks_off()
    ax.set_xlabel("período de polling P (ms)")
axs[0].plot(P, [p / 2 + 1 for p in P], ":", color=INK2, lw=1, label="P/2 + 1 tick")
axs[0].legend(fontsize=7, loc="upper left")
fig.tight_layout()
fig.savefig(OUT / "fig_exp5_varredura.png")
plt.close(fig)

# --- Figura 3: Exp. 6A carga por evento --------------------------------------
loads = [0, 1000, 10000, 50000]
fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.6))
w = 0.38
for k, m in enumerate(("irq_thread", "workqueue")):
    e = [f"exp6a_{m}_proc{x}" for x in loads]
    cpu = [sum_mean(x, "cpu_x100") / 100 for x in e]
    est = [sum_mean(x, "cpu_est_x100") / 100 for x in e]
    xs = [i + (k - 0.5) * w for i in range(len(loads))]
    axs[0].bar(xs, cpu, width=w - 0.04, color=COR[m], label=NOME[m], zorder=2)
    lp = [lat_mean(x, "lat_process") for x in e]
    axs[1].bar(xs, lp, width=w - 0.04, color=COR[m], label=NOME[m], zorder=2)
    for x, y in zip(xs, cpu):
        axs[0].text(x, y + 0.6, f"{y:.1f}".replace(".", ","), ha="center", fontsize=7, color=INK)
    for x, y in zip(xs, lp):
        axs[1].text(x, y + 0.1, f"{y:.2f}".replace(".", ","), ha="center", fontsize=7, color=INK)
for ax in axs:
    ax.set_xticks(range(len(loads)), ["0", "1 ms", "10 ms", "50 ms"])
    ax.set_xlabel("carga por evento")
axs[0].set_title("CPU ocupada (kernel)", loc="left")
axs[0].set_ylabel("%")
axs[1].set_title("Latência estímulo → tratamento", loc="left")
axs[1].set_ylabel("µs")
axs[0].legend(fontsize=7, loc="upper left")
fig.tight_layout()
fig.savefig(OUT / "fig_exp6_carga.png")
plt.close(fig)

# --- Figura 4: Exp. 7 heartbeat ----------------------------------------------
fig, ax = plt.subplots(figsize=(5.2, 2.4))
ms = ["isr_only", "irq_thread", "workqueue"]
vals = [sum_mean(f"exp7_{m}_hb", "hb_max_ms") for m in ms]
ax.barh(range(3), vals, color=[COR[m] for m in ms], height=0.55, zorder=2)
for i, v in enumerate(vals):
    ax.text(v + 0.3, i, f"{v:.2f} ms".replace(".", ","), va="center", fontsize=8, color=INK)
ax.set_yticks(range(3), [NOME[m] for m in ms])
ax.invert_yaxis()
ax.axvline(1.0, color=INK2, lw=0.8, ls=":")
ax.set_xlabel("maior intervalo entre execuções do heartbeat (ms)")
ax.set_title("Exp. 7: carga de 20 ms dentro × fora da ISR", loc="left")
ax.set_xlim(0, max(vals) * 1.2)
fig.tight_layout()
fig.savefig(OUT / "fig_exp7_heartbeat.png")
plt.close(fig)
print("figuras em", OUT)
