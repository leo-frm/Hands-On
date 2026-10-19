#!/usr/bin/env python3
"""Compila as variantes do hands-on e executa cada uma no ESP32 emulado.

A placa e substituida pelo QEMU da Espressif com um modelo de GPIO estendido
(ver qemu-esp32-gpio.patch): registradores de saida/entrada, interrupcoes de
borda/nivel, jumper GPIO18 -> GPIO4 e um botao com toques roteirizados.
O firmware e o binario real gerado pelo west build para esp32_devkitc.

Uso:
    run_lab.py --list
    run_lab.py exp4_polling exp4_irq_thread ...   (ou prefixo: exp5)
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENTREGA = HERE.parent
ZEPHYR_WS = Path(os.environ.get("ZEPHYR_WS", "/home/user/zephyrproject"))
QEMU = Path(os.environ.get("QEMU_ESP32", "/home/user/qemu-esp/build/qemu-system-xtensa"))
QEMU_BIOS = QEMU.parent.parent / "pc-bios"
BUILD_ROOT = Path(os.environ.get("BUILD_ROOT", "/home/user/work/builds"))
LOGS = ENTREGA / "logs"
BOARD = "esp32_devkitc/esp32/procpu"
ICOUNT_SHIFT = 2          # 2^2 = 4 ns de tempo virtual por instrucao
FLASH_APP_OFFSET = 0x1000 # ESP simple boot: imagem da aplicacao em 0x1000

BENCH = ENTREGA / "codigo" / "00_bench_eventos"
JUMPER = {"jumper-src": 18, "jumper-dst": 4}
# Toques "humanos" no botao para os experimentos manuais (1 a 3): 25 toques
# de 80-220 ms separados por 0,4-1,5 s; a cada 5 toques um toque rapido de 4 ms.
BUTTON = {"btn-count": 25, "btn-short-every": 5, "btn-short-ms": 4}
MANUAL = {"CONFIG_APP_STIMULUS": "n", "CONFIG_APP_VERBOSE": "y"}
MODES = {
    "polling": "CONFIG_APP_MODE_POLLING",
    "irq_thread": "CONFIG_APP_MODE_IRQ_THREAD",
    "workqueue": "CONFIG_APP_MODE_WORKQUEUE",
    "isr_only": "CONFIG_APP_MODE_ISR_ONLY",
}
EXP8 = {
    "polling": ENTREGA / "codigo" / "01_polling",
    "irq_thread": ENTREGA / "codigo" / "02_interrupt_thread",
    "workqueue": ENTREGA / "codigo" / "03_workqueue",
}


def mode(name, **defs):
    return {MODES[name]: "y", **{f"CONFIG_{k}": str(v) for k, v in defs.items()}}


def experiments():
    """Cada entrada: nome -> (app, defines, GPIO, parada, execucoes[, icount shift])."""
    exps = {}
    for m in ("polling", "irq_thread", "workqueue"):
        exps[f"exp1-3_{m}_manual"] = (BENCH, {**mode(m), **MANUAL}, BUTTON, ("status", 3), 1)
        exps[f"exp4_{m}"] = (BENCH, mode(m), JUMPER, "report", 3)
    # k_msleep() arredonda +1 tick: o periodo padrao de 97 ms vira 99 ticks = 9 x 11
    # (polling de 10 ms = 11 ticks) e trava a fase. Com 95 ms o periodo real e 97 ticks.
    exps["exp4_polling_periodo95"] = (
        BENCH, mode("polling", APP_EVENT_PERIOD_MS=95), JUMPER, "report", 3)
    # Sensibilidade ao CPI: 8 ns/instrucao (~2 ciclos por instrucao a 240 MHz)
    for m in ("polling", "irq_thread", "workqueue"):
        exps[f"exp4_{m}_cpi2"] = (BENCH, mode(m), JUMPER, "report", 1, 3)
    for pulse in (20, 5):
        for p in (1, 5, 10, 50, 100):
            exps[f"exp5_poll{p}_pulse{pulse}"] = (
                BENCH, mode("polling", APP_POLL_PERIOD_MS=p, APP_PULSE_WIDTH_MS=pulse,
                            APP_EVENT_PERIOD_MS=95),
                JUMPER, "report", 3)
    for load in (0, 1000, 10000, 50000):
        for m in ("irq_thread", "workqueue"):
            exps[f"exp6a_{m}_proc{load}"] = (
                BENCH, mode(m, APP_PROCESSING_US=load), JUMPER, "report", 1)
    for m in ("polling", "irq_thread", "workqueue"):
        exps[f"exp6b_{m}_saturacao"] = (
            BENCH, mode(m, APP_MAIN_PRIORITY=0, APP_EVENT_PERIOD_MS=23,
                        APP_PULSE_WIDTH_MS=5, APP_PROCESSING_US=30000),
            JUMPER, "report", 1)
    for m in ("isr_only", "irq_thread", "workqueue"):
        exps[f"exp7_{m}_hb"] = (
            BENCH, mode(m, APP_HEARTBEAT="y", APP_PROCESSING_US=20000), JUMPER, "report", 1)
    for m, app in EXP8.items():
        exps[f"exp8_{m}_sleep"] = (app, {"CONFIG_APP_PROC_BUSY": "n"}, JUMPER, "report", 1)
        exps[f"exp8_{m}_busy"] = (app, {"CONFIG_APP_PROC_BUSY": "y"}, JUMPER, "report", 1)
        exps[f"exp8_{m}_rajada"] = (
            app, {"CONFIG_APP_PROC_BUSY": "y", "CONFIG_APP_EVENT_PERIOD_MS": "47"},
            JUMPER, "report", 1)
    return exps


def west_env():
    env = dict(os.environ)
    env["PATH"] = f"{ZEPHYR_WS / '.venv' / 'bin'}:{env['PATH']}"
    env["ZEPHYR_BASE"] = str(ZEPHYR_WS / "zephyr")
    return env


def build(name, app, defs):
    bdir = BUILD_ROOT / name
    cmd = ["west", "build", "-p", "always", "-b", BOARD, "-d", str(bdir), str(app), "--"]
    cmd += [f"-D{k}={v}" for k, v in defs.items()]
    res = subprocess.run(cmd, cwd=ZEPHYR_WS, env=west_env(), capture_output=True, text=True)
    out = res.stdout + res.stderr
    (LOGS / f"{name}_build.txt").write_text(
        "# Saida do west build (compilacao real para " + BOARD + ")\n"
        "# Comando: " + " ".join(cmd[1:]) + "\n" + out)
    if res.returncode != 0:
        sys.exit(f"[{name}] falha na compilacao, veja logs/{name}_build.txt")
    save_sections(name, bdir)
    return bdir


def save_sections(name, bdir):
    """Tamanho exato das secoes do ELF (as pilhas ficam em .dram0.noinit)."""
    objdump = Path(os.environ.get("ZEPHYR_SDK_INSTALL_DIR", "/home/user/zephyr-sdk-1.0.1")) / \
        "gnu/xtensa-espressif_esp32_zephyr-elf/bin/xtensa-espressif_esp32_zephyr-elf-objdump"
    res = subprocess.run([str(objdump), "-h", str(bdir / "zephyr" / "zephyr.elf")],
                         capture_output=True, text=True)
    (LOGS / f"{name}_secoes.txt").write_text(res.stdout)


def memory_reports(name, bdir):
    for target in ("ram_report", "rom_report"):
        res = subprocess.run(["west", "build", "-d", str(bdir), "-t", target],
                             cwd=ZEPHYR_WS, env=west_env(), capture_output=True, text=True)
        (LOGS / f"{name}_{target.split('_')[0]}.txt").write_text(res.stdout + res.stderr)


def flash_image(bdir):
    app = (bdir / "zephyr" / "zephyr.bin").read_bytes()
    img = bytearray(b"\xff" * (4 * 1024 * 1024))
    img[FLASH_APP_OFFSET:FLASH_APP_OFFSET + len(app)] = app
    path = bdir / "flash_4MB.bin"
    path.write_bytes(img)
    return path


def run(name, run_idx, bdir, defs, gpio, stop, trace=False, shift=ICOUNT_SHIFT,
        wall_timeout=900):
    log = LOGS / f"{name}_run{run_idx}.log"
    props = dict(gpio)
    if trace:
        props["trace"] = str(LOGS / f"{name}_run{run_idx}_gpio_trace.csv")
        props["trace-mask"] = (1 << 2) | (1 << 4) | (1 << 18)
    cmd = [str(QEMU), "-machine", "esp32", "-display", "none", "-monitor", "none",
           "-serial", "stdio", "-L", str(QEMU_BIOS),
           "-drive", f"file={flash_image(bdir)},if=mtd,format=raw",
           "-icount", f"shift={shift},align=off,sleep=off"]
    for k, v in props.items():
        cmd += ["-global", f"driver=esp32.gpio,property={k},value={v}"]
    header = [
        "# ORIGEM: execucao EMULADA - firmware real (west build, esp32_devkitc) rodando no",
        "#         QEMU da Espressif com modelo de GPIO estendido; NAO e medicao em placa fisica.",
        f"# Experimento: {name} | execucao {run_idx}",
        "# Configuracao: " + " ".join(f"-D{k}={v}" for k, v in defs.items()),
        f"# Emulador: -icount shift={shift} ({2 ** shift} ns/instrucao) | GPIO: "
        + ", ".join(f"{k}={v}" for k, v in gpio.items()),
        "",
    ]
    serial = bdir / f"serial_run{run_idx}.txt"
    serial.unlink(missing_ok=True)
    cmd[cmd.index("stdio")] = f"file:{serial}"
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    lines, seen_report, status_seen, done_at = [], False, 0, None
    buf, pos = b"", 0
    t0 = time.time()
    try:
        while True:
            if time.time() - t0 > wall_timeout:
                lines.append("# [run_lab] tempo limite de execucao atingido")
                break
            if done_at and time.time() - done_at > 0.5:
                break
            time.sleep(0.2)
            if not serial.exists():
                continue
            with serial.open("rb") as f:
                f.seek(pos)
                chunk = f.read()
            pos += len(chunk)
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("utf-8", "replace").rstrip("\r")
                lines.append(line)
                if "RELATORIO" in line:
                    seen_report = True
                if line.startswith("[status]"):
                    status_seen += 1
                if "ISR0" in line and done_at is None:
                    if (stop == "report" and seen_report) or (
                            isinstance(stop, tuple) and status_seen >= stop[1]):
                        done_at = time.time()
    finally:
        proc.kill()
        proc.wait()
    log.write_text("\n".join(header + lines) + "\n")
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--runs", type=int, default=None)
    args = ap.parse_args()
    exps = experiments()
    if args.list:
        print("\n".join(exps))
        return
    LOGS.mkdir(exist_ok=True)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    selected = [n for n in exps if any(n == a or n.startswith(a) for a in args.names)]
    for name in selected:
        app, defs, gpio, stop, runs, *shift = exps[name]
        t = time.time()
        bdir = build(name, app, defs)
        if name in ("exp4_polling", "exp4_irq_thread", "exp4_workqueue"):
            memory_reports(name, bdir)
        for i in range(1, (args.runs or runs) + 1):
            run(name, i, bdir, defs, gpio, stop, trace=name.startswith(("exp1-3_", "exp4_")),
                shift=shift[0] if shift else ICOUNT_SHIFT)
        print(f"[{name}] ok em {time.time() - t:.0f} s", flush=True)


if __name__ == "__main__":
    main()
