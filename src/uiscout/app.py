"""uiscout desktop app — the non-technical "type your goal" window.

A brain-agnostic shell: the user types what they want, watches progress, and gets
a "I've finished logging in ▸ Continue" button when the automation pauses for
2FA/login. The actual thinking is supplied by a pluggable brain (hosted /
bring-your-own-key / local model) wired in `_run_goal`; a no-brain demo path runs
a deterministic web audit so the app is usable and demoable today.

Built with Tkinter (stdlib) so it packages into a single .exe with PyInstaller
and has no GUI dependency to install.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import tkinter as tk
from tkinter import ttk

APP_TITLE = "uiscout — automate & test any software"
BG = "#0b0f19"
FG = "#e5e7eb"
ACCENT = "#4f8cff"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._events: queue.Queue = queue.Queue()
        self._resume = threading.Event()
        self._build()
        self.root.after(100, self._drain)

    def _build(self) -> None:
        self.root.title(APP_TITLE)
        self.root.geometry("760x560")
        self.root.configure(bg=BG)

        tk.Label(self.root, text="What do you want to do?", bg=BG, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(self.root, text="Type a goal in plain English — e.g. "
                 "\"audit every button on https://mysite.com\" or "
                 "\"log into the portal and download this month's invoices\".",
                 bg=BG, fg="#9aa4b2", font=("Segoe UI", 9),
                 wraplength=700, justify="left").pack(anchor="w", padx=20)

        self.goal = tk.Text(self.root, height=3, font=("Segoe UI", 11), wrap="word",
                            bg="#111827", fg=FG, insertbackground=FG,
                            relief="flat", padx=10, pady=8)
        self.goal.pack(fill="x", padx=20, pady=(8, 8))
        self.goal.insert("1.0", "audit every button on https://example.com")

        row = tk.Frame(self.root, bg=BG)
        row.pack(fill="x", padx=20)
        self.run_btn = tk.Button(row, text="▶  Run", command=self._on_run,
                                 bg=ACCENT, fg="white", font=("Segoe UI", 11, "bold"),
                                 relief="flat", padx=20, pady=6, cursor="hand2")
        self.run_btn.pack(side="left")
        self.continue_btn = tk.Button(
            row, text="✓  I've finished logging in — Continue", command=self._on_continue,
            bg="#16a34a", fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2")
        # shown only while paused for a human handoff
        self.show_browser = tk.BooleanVar(value=True)
        tk.Checkbutton(row, text="Show the browser", variable=self.show_browser,
                       bg=BG, fg=FG, selectcolor=BG, activebackground=BG,
                       activeforeground=FG, font=("Segoe UI", 9)).pack(side="right")

        self.status = tk.Label(self.root, text="Ready.", bg=BG, fg="#9aa4b2",
                               anchor="w", font=("Segoe UI", 9))
        self.status.pack(fill="x", padx=20, pady=(10, 0))

        self.log = tk.Text(self.root, bg="#0d1117", fg="#c9d1d9", relief="flat",
                           font=("Consolas", 10), padx=10, pady=8, state="disabled")
        self.log.pack(fill="both", expand=True, padx=20, pady=(6, 18))

    # --- UI event helpers (thread-safe via a queue) -----------------------

    def emit(self, kind: str, text: str) -> None:
        self._events.put((kind, text))

    def _drain(self) -> None:
        try:
            while True:
                kind, text = self._events.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", text + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "status":
                    self.status.configure(text=text)
                elif kind == "need_human":
                    self.status.configure(text="⏸  " + text, fg="#fbbf24")
                    self.continue_btn.pack(side="left", padx=10)
                elif kind == "resumed":
                    self.continue_btn.pack_forget()
                    self.status.configure(fg="#9aa4b2")
                elif kind == "done":
                    self.run_btn.configure(state="normal", text="▶  Run")
                    self.status.configure(text=text, fg="#34d399")
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    # --- actions ----------------------------------------------------------

    def _on_run(self) -> None:
        goal = self.goal.get("1.0", "end").strip()
        if not goal:
            return
        self.run_btn.configure(state="disabled", text="Running…")
        self.status.configure(text="Working…", fg="#9aa4b2")
        self._resume.clear()
        threading.Thread(target=self._worker, args=(goal,), daemon=True).start()

    def _on_continue(self) -> None:
        self._resume.set()
        self.emit("resumed", "")
        self.emit("log", "▸ Continuing…")

    def _worker(self, goal: str) -> None:
        try:
            asyncio.run(self._run_goal(goal))
        except Exception as e:  # surface, never crash the window
            self.emit("log", f"✗ Error: {e}")
            self.emit("done", f"Stopped: {e}")

    async def _run_goal(self, goal: str) -> None:
        """Where the brain plugs in. For now: if the goal is a plain audit of a
        URL, run the deterministic auditor (no brain needed) so the app works
        today. A hosted/BYO-key/local brain replaces this branch to handle
        arbitrary goals via uiscout.agent.run_audit."""
        import re
        from . import config
        from .runner import full_web_audit

        self.emit("log", f"Goal: {goal}")
        m = re.search(r"https?://\S+", goal)

        # Fast path: a plain URL audit needs no brain — always works.
        if m and ("audit" in goal.lower() or "test" in goal.lower()):
            url = m.group(0)
            self.emit("status", f"Auditing {url} …")
            self.emit("log", f"Opening {url} and clicking every control…")
            result = await full_web_audit(url, headless=not self.show_browser.get())
            s = result["summary"]
            out = "uiscout-report.html"
            with open(out, "w", encoding="utf-8") as f:
                f.write(result["html"])
            self.emit("log", f"Health score: {s['score']}/100")
            self.emit("log", f"  {s['tested']} controls · {s['dead_controls']} dead"
                             f" · {s['a11y_issues']} accessibility issues"
                             f" · {s['console_errors']} console errors")
            self.emit("log", f"Report saved to {out}")
            self.emit("done", f"Done — score {s['score']}/100, report: {out}")
            return

        # General goal: drive it with the configured brain.
        if not config.is_configured():
            self.emit("log", "No AI brain connected yet. Open Setup and paste a "
                             "free key (menu / run `uiscout setup`).")
            self.emit("done", "Connect a brain to run general goals.")
            return
        from .agent import provider_from_config, run_audit
        self.emit("status", "Thinking + acting with your AI brain…")
        self.emit("log", f"Brain: {config.get_brain()['model']}")
        report_text = await run_audit(provider_from_config(), goal,
                                      headless=not self.show_browser.get())
        self.emit("log", report_text)
        self.emit("done", "Goal finished — see log.")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
