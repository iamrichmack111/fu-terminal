#!/usr/bin/env python3
import os
import sys
import time
import shutil
import threading

TTY = sys.stdout.isatty() and not os.getenv("NO_COLOR")

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
PURPLE = "\033[95m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"

def c(text, color):
    text = str(text)
    return f"{color}{text}{RESET}" if TTY else text

def term_width():
    return max(60, min(shutil.get_terminal_size((80, 24)).columns, 100))

def line(char="─"):
    return char * term_width()

def logo():
    print()
    print(c("  ███████╗██╗   ██╗", CYAN))
    print(c("  ██╔════╝██║   ██║", CYAN))
    print(c("  █████╗  ██║   ██║", CYAN))
    print(c("  ██╔══╝  ██║   ██║", CYAN))
    print(c("  ██║     ╚██████╔╝", CYAN))
    print(c("  ╚═╝      ╚═════╝ ", CYAN))
    print(c("  Retrieval-first terminal intelligence", GRAY))
    print()

def header(title):
    print(c(line(), GRAY))
    print(c(f"◆ {title}", BOLD))
    print(c(line(), GRAY))

def badge(label, value, color=CYAN):
    print(f"  {c(label.upper().ljust(10), GRAY)} {c('●', color)} {c(value, color)}")

def step(text, elapsed=None):
    suffix = ""
    if elapsed is not None:
        suffix = c(f"  {elapsed:.2f}s", GRAY)
    print(f"  {c('✓', GREEN)} {text}{suffix}")

def warn(text):
    print(f"  {c('!', YELLOW)} {c(text, YELLOW)}")

def fail(text):
    print(f"  {c('✗', RED)} {c(text, RED)}")

def blocked(text):
    print()
    print(c("╭─ BLOCKED " + "─" * max(1, term_width() - 12) + "╮", RED))
    print(c("│ ", RED) + text)
    print(c("╰" + "─" * (term_width() - 2) + "╯", RED))

def command_box(command):
    w = term_width()
    title = " COMMAND "
    print()
    print(c("╭─" + title + "─" * max(1, w - len(title) - 3) + "╮", CYAN))

    for raw in command.splitlines():
        # Don't try complicated wrapping: shell commands are clearer intact.
        print(c("│ ", CYAN) + raw)

    print(c("╰" + "─" * (w - 2) + "╯", CYAN))

def approval():
    print()
    return input(
        f"{c('[y]',GREEN)} approve  "
        f"{c('[n]',RED)} cancel  "
        f"{c('[e]',YELLOW)} edit  "
        f"{c('[r]',CYAN)} regenerate  "
        f"{c('›',PURPLE)} "
    ).lower().strip()

def auto():
    print()
    print(f"  {c('⚡',YELLOW)} {c('AUTO APPROVED',GREEN)} {c('deterministic read-only command',GRAY)}")

class Spinner:
    def __init__(self, label):
        self.label = label
        self.frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.stop_event = threading.Event()
        self.thread = None
        self.started = None

    def _spin(self):
        i = 0
        while not self.stop_event.is_set():
            elapsed = time.perf_counter() - self.started
            msg = (
                f"\r  {c(self.frames[i % len(self.frames)], CYAN)} "
                f"{self.label} {c(f'{elapsed:.1f}s',GRAY)}"
            )
            print(msg, end="", flush=True)
            i += 1
            time.sleep(.08)

    def start(self):
        self.started = time.perf_counter()
        if TTY:
            self.thread = threading.Thread(target=self._spin, daemon=True)
            self.thread.start()
        else:
            print(f"  > {self.label}")
        return self

    def stop(self, success=True):
        self.stop_event.set()

        if self.thread:
            self.thread.join(timeout=.2)

        elapsed = time.perf_counter() - self.started

        if TTY:
            print("\r" + " " * term_width() + "\r", end="")

        icon = c("✓", GREEN) if success else c("✗", RED)
        print(f"  {icon} {self.label} {c(f'{elapsed:.2f}s',GRAY)}")
        return elapsed

def result(returncode, elapsed, log):
    print()
    print(c(line(), GRAY))

    if returncode == 0:
        print(
            f"{c('✓ COMPLETED',GREEN)}"
            f"  {c(f'{elapsed:.2f}s',GRAY)}"
            f"  {c('exit 0',GRAY)}"
        )
    else:
        print(
            f"{c('✗ FAILED',RED)}"
            f"  {c(f'{elapsed:.2f}s',GRAY)}"
            f"  {c(f'exit {returncode}',RED)}"
        )

    print(c(f"Log: {log}", GRAY))
