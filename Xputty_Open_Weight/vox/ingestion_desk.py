"""User-operated local ingestion desk. Files stay in place; no renaming required."""

import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from .upod import import_folder
from .intake import SUPPORTED
from .media_processing import CANCEL

ROOT = Path(__file__).resolve().parents[1]


class Desk:
    def __init__(self, window):
        self.window = window
        self.events = queue.Queue()
        self.sources = []
        self.running = False
        window.title("VOX · Ingestion desk")
        window.geometry("850x620")
        window.minsize(720, 500)
        window.configure(bg="#0c1220")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0c1220")
        style.configure(
            "TLabel", background="#0c1220", foreground="#dbe9fa", font=("Segoe UI", 11)
        )
        style.configure("TButton", padding=12, font=("Segoe UI", 11))
        style.configure("Accent.TButton", background="#8cf9df", foreground="#10231f")
        shell = ttk.Frame(window, padding=24)
        shell.pack(fill="both", expand=True)
        ttk.Label(
            shell,
            text="VOX / INGESTION",
            font=("Segoe UI", 22, "bold"),
            foreground="#8cf9df",
        ).pack(anchor="w")
        ttk.Label(
            shell, text="Text, documents, sound and scenes. Keep the originals."
        ).pack(anchor="w", pady=(5, 18))
        controls = ttk.Frame(shell)
        controls.pack(fill="x")
        self.add = ttk.Button(controls, text="Add files", command=self.pick_files)
        self.add.pack(side="left", padx=(0, 8))
        self.folder = ttk.Button(controls, text="Add folder", command=self.pick_folder)
        self.folder.pack(side="left", padx=(0, 8))
        self.clear = ttk.Button(
            controls, text="Clear selection", command=self.clear_sources
        )
        self.clear.pack(side="left")
        self.list = tk.Listbox(
            shell,
            bg="#172438",
            fg="#e7efff",
            selectbackground="#426278",
            font=("Segoe UI", 10),
            height=7,
            borderwidth=0,
            highlightthickness=0,
        )
        self.list.pack(fill="x", pady=12)
        self.status = tk.StringVar(
            value="Add files or a folder. No format changes needed."
        )
        ttk.Label(shell, textvariable=self.status, wraplength=780).pack(
            anchor="w", pady=(0, 10)
        )
        action = ttk.Frame(shell)
        action.pack(fill="x")
        self.start = ttk.Button(
            action,
            text="Process selected files",
            style="Accent.TButton",
            command=self.begin,
        )
        self.start.pack(side="left")
        self.stop = ttk.Button(action, text="Stop", command=self.cancel)
        self.stop.pack(side="left", padx=8)
        self.stop.state(["disabled"])
        ttk.Button(action, text="Open results", command=self.open_results).pack(
            side="right"
        )
        self.log = tk.Text(
            shell,
            bg="#111b2c",
            fg="#b9ccdf",
            font=("Consolas", 10),
            height=12,
            borderwidth=0,
            wrap="word",
            state="disabled",
        )
        self.log.pack(fill="both", expand=True, pady=(16, 0))
        self.output = ROOT / "work/intake"
        self.log_offsets = {}
        window.protocol("WM_DELETE_WINDOW", self.close)
        window.after(200, self.pump)
        threading.Thread(target=self.preflight, daemon=True).start()

    def preflight(self):
        from .ingestion_doctor import check

        result = check()
        self.events.put(
            "Ready: local speech, OCR, vision and document tools available."
            if result["ready"]
            else "Dependency check: " + json.dumps(result["checks"])
        )

    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Select source files",
            filetypes=[
                ("Supported sources", " ".join("*" + s for s in sorted(SUPPORTED))),
                ("All files", "*.*"),
            ],
        )
        self.add_sources(paths)

    def pick_folder(self):
        folder = filedialog.askdirectory(title="Select capture folder")
        if folder:
            self.add_sources([folder])

    def add_sources(self, paths):
        for value in paths:
            path = Path(value).resolve()
            if path not in self.sources:
                self.sources.append(path)
                self.list.insert("end", str(path))

    def clear_sources(self):
        if not self.running:
            self.sources = []
            self.list.delete(0, "end")

    def begin(self):
        if self.running or not self.sources:
            return
        self.running = True
        CANCEL.clear()
        self.stop.state(["!disabled"])
        for button in (self.start, self.add, self.folder, self.clear):
            button.state(["disabled"])
        self.status.set(
            "Processing locally. Originals are unchanged. Detailed progress appears below."
        )
        threading.Thread(
            target=self.run, args=(tuple(self.sources),), daemon=False
        ).start()

    def run(self, sources):
        totals = {"imported": 0, "unchanged": 0, "errors": 0}
        reports = []
        try:
            for source in sources:
                try:
                    report = import_folder(
                        source if source.is_dir() else source.parent,
                        self.output,
                        selected_paths=None if source.is_dir() else [source],
                        on_progress=self.events.put,
                    )
                    reports.append(report)
                    for key in totals:
                        totals[key] += report[key]
                except Exception as error:
                    totals["errors"] += 1
                    self.events.put(str(error))
            self.output.mkdir(parents=True, exist_ok=True)
            (self.output / "desk-last-run.json").write_text(
                json.dumps({"totals": totals, "reports": reports}, indent=2),
                encoding="utf-8",
            )
            self.events.put(("done", totals))
        except Exception as error:
            self.events.put(("done", {"error": str(error)}))

    def pump(self):
        try:
            while True:
                item = self.events.get_nowait()
                if isinstance(item, tuple):
                    self.running = False
                    self.stop.state(["disabled"])
                    for button in (self.start, self.add, self.folder, self.clear):
                        button.state(["!disabled"])
                    self.status.set("Finished: " + json.dumps(item[1]))
                else:
                    self.status.set(item)
                    self.log.configure(state="normal")
                    self.log.insert("end", item + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
        except queue.Empty:
            pass
        if self.running and self.output.exists():
            for path in self.output.glob(".processing-*/worker.log"):
                try:
                    with path.open(encoding="utf-8", errors="replace") as stream:
                        stream.seek(self.log_offsets.get(str(path), 0))
                        chunk = stream.read()
                        self.log_offsets[str(path)] = stream.tell()
                    if chunk:
                        self.log.configure(state="normal")
                        self.log.insert("end", chunk)
                        self.log.see("end")
                        self.log.configure(state="disabled")
                except OSError:
                    pass
        self.window.after(200, self.pump)

    def open_results(self):
        self.output.mkdir(parents=True, exist_ok=True)
        os.startfile(self.output)

    def cancel(self):
        CANCEL.set()
        self.stop.state(["disabled"])
        self.status.set("Stopping the current worker. Completed imports remain saved.")

    def close(self):
        CANCEL.set()
        self.window.destroy()


def main():
    window = tk.Tk()
    Desk(window)
    window.mainloop()


if __name__ == "__main__":
    main()
