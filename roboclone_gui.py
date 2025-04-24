"""
RoboClone - A compact Tkinter GUI that wraps Windows Robocopy
============================================================

Features
--------
* Browse for **source** and **target** folders.
* Optional *simulation* (Robocopy /L) to preview changes.
* Semi-colon list of file/folder **exclusions**.
* **Free-space check** on the target drive before copying.
* Progress bar based on Robocopy log parsing.
* **Tray notification** at the end (via `plyer`).
* Post-copy action: *none / close app / reboot / shutdown* with 5-second cancel.
"""

# --------------------------------------------------------------------------
# Built‑in & third‑party imports
# --------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import datetime
import threading
import time
import webbrowser
import shutil
from plyer import notification          # cross‑platform notifications
from PIL import ImageTk, Image          # show optional icon

# --------------------------------------------------------------------------
# Paths and constants
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)                      # make relative paths predictable
LOG_DIR = os.path.join(BASE_DIR, "logs")

# --------------------------------------------------------------------------
# Helper callbacks – folder pickers
# --------------------------------------------------------------------------
def choose_source() -> None:
    """Ask the user for a **source** directory and save it."""
    path = filedialog.askdirectory(title="Select source folder")
    if path:
        source_var.set(path)

def choose_target() -> None:
    """Ask the user for a **target** directory and save it."""
    path = filedialog.askdirectory(title="Select target folder")
    if path:
        target_var.set(path)

# --------------------------------------------------------------------------
# Main entry – validate, build command, launch worker thread
# --------------------------------------------------------------------------
def run_backup() -> None:
    """Kick-off a Robocopy job after checking inputs and free space."""
    source      = source_var.get()
    target      = target_var.get()
    dry_run     = dry_run_var.get()
    exclusions  = exclusions_var.get()

    # --- sanity check -----------------------------------------------------
    if not source or not target:
        messagebox.showwarning("Warning", "Please select both source and target folders!")
        return

    # --- free‑space pre‑flight -------------------------------------------
    try:
        free_bytes  = shutil.disk_usage(target).free
        total_bytes = 0
        excl_set    = {e.strip().lower() for e in exclusions.split(";") if e.strip()}

        for root_dir, _, files in os.walk(source):
            # skip excluded directories
            if any(excl in root_dir.lower() for excl in excl_set):
                continue
            for fname in files:
                # skip excluded files
                if any(excl in fname.lower() for excl in excl_set):
                    continue
                try:
                    total_bytes += os.path.getsize(os.path.join(root_dir, fname))
                except OSError:
                    pass  # unreadable

        if total_bytes > free_bytes:
            deficit = (total_bytes - free_bytes) / (1024**3)
            messagebox.showerror(
                "Insufficient space",
                f"Target drive is missing roughly {deficit:.1f} GB.\n"
                "Free up space or choose another destination."
            )
            return
    except Exception as err:
        # continue anyway but warn user
        messagebox.showwarning("Notice", f"Could not verify free space: {err}")

    # --- build robocopy command ------------------------------------------
    cmd = ["robocopy", source, target, "/MIR", "/R:0", "/W:0"]

    for excl in (e.strip() for e in exclusions.split(";") if e.strip()):
        cmd.extend(["/XD", excl, "/XF", excl])

    if dry_run:
        cmd.append("/L")

    # prepare log path
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path  = os.path.join(LOG_DIR, f"robocopy_log_{timestamp}.txt")
    cmd.append(f"/LOG:{log_path}")

    # reset UI
    progress_var.set(0)
    progress_label.config(text="Running…")

    # run in background
    threading.Thread(target=_worker, args=(cmd, log_path), daemon=True).start()

# --------------------------------------------------------------------------
# Background worker – executes Robocopy and updates progress
# --------------------------------------------------------------------------
def _worker(cmd: list[str], log_path: str) -> None:
    """Execute Robocopy, update progress bar, then perform post-actions."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while proc.poll() is None:
            _update_progress(log_path)
            time.sleep(1)
        _update_progress(log_path, force=True)       # final 100 %

        messagebox.showinfo("Done", f"Backup completed.\nLog: {log_path}")

        if tray_notify_var.get():
            notification.notify(
                title="Robocopy finished ✅",
                message="Backup completed successfully!",
                app_name="RoboClone",
                timeout=5
            )

        match post_action_var.get():
            case "reboot":
                _countdown("reboot",   "shutdown /r /t 0")
            case "shutdown":
                _countdown("shutdown", "shutdown /s /t 0")
            case "close":
                root.after(0, root.destroy)
    except Exception as err:
        messagebox.showerror("Error", f"Execution failed:\n{err}")

# --------------------------------------------------------------------------
# Utility – log parser for crude progress estimation
# --------------------------------------------------------------------------
def _update_progress(log_path: str, *, force: bool = False) -> None:
    """Check the log file for '100%' markers to estimate completion."""
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as fp:
            lines = fp.readlines()
        relevant = [l for l in lines if any(k in l for k in ("New File", "Newer", "100%"))]
        total = max(len(relevant), 1)
        done  = sum("100%" in l for l in relevant)
        pct   = 100 if force else int(done / total * 100)
        progress_var.set(pct)
        progress_label.config(text=f"{pct}% done")
    except FileNotFoundError:
        pass  # log not created yet
    except Exception:
        pass

# --------------------------------------------------------------------------
# Countdown window for reboot / shutdown
# --------------------------------------------------------------------------
def _countdown(action: str, os_cmd: str) -> None:
    """Show 5-second countdown so user can cancel reboot/shutdown."""
    win = tk.Toplevel(root)
    win.title(f"⚠️ Automatic {action}")
    win.geometry("300x150")
    win.resizable(False, False)

    ttk.Label(win, text=f"PC will {action} in").pack(pady=(20, 5))
    secs = tk.IntVar(value=5)
    ttk.Label(win, textvariable=secs, font=("Segoe UI", 24, "bold")).pack()
    ttk.Label(win, text="Press 'Cancel' to abort.").pack(pady=5)
    ttk.Button(win, text="Cancel", command=win.destroy).pack(pady=10)

    def _tick():
        for i in range(5, 0, -1):
            secs.set(i)
            time.sleep(1)
            if not win.winfo_exists():
                return
        win.destroy()
        os.system(os_cmd)

    threading.Thread(target=_tick, daemon=True).start()
    win.grab_set()

# --------------------------------------------------------------------------
# About dialog
# --------------------------------------------------------------------------
def show_about() -> None:
    """Minimal *About* window with logo, version and links."""
    about = tk.Toplevel(root)
    about.title("About RoboClone")
    about.geometry("400x320")
    about.resizable(False, False)
    try:
        about.iconbitmap("img/icon.ico")
    except FileNotFoundError:
        pass

    frame = ttk.Frame(about, padding=20)
    frame.pack(fill="both", expand=True)

    try:
        logo = Image.open("img/icon.ico").resize((80, 80))
        logo_tk = ImageTk.PhotoImage(logo)
        ttk.Label(frame, image=logo_tk).pack(pady=(0, 10))
        frame.image = logo_tk
    except FileNotFoundError:
        pass

    ttk.Label(frame, text="RoboClone v1.0", font=("Segoe UI", 12, "bold")).pack()
    ttk.Label(frame, text="Author: damiandrake0", font=("Segoe UI", 10)).pack()
    ttk.Label(frame,
              text='A simple tool written in Python for cloning disks\nbased on "robocopy" Windows terminal command',
              justify="center").pack(pady=(10, 10))

    def open_url(url: str) -> None:
        webbrowser.open(url)

    lbl_site = ttk.Label(frame, text="My personal GitHub page", foreground="blue", cursor="hand2")
    lbl_site.pack(); lbl_site.bind("<Button-1>", lambda _: open_url("https://github.com/damiandrake0"))
    lbl_mail = ttk.Label(frame, text="To contact me", foreground="blue", cursor="hand2")
    lbl_mail.pack(); lbl_mail.bind("<Button-1>", lambda _: open_url("mailto:damy_devivo@outlook.it"))

    ttk.Button(frame, text="Close", command=about.destroy).pack(pady=10)

# --------------------------------------------------------------------------
# GUI setup
# --------------------------------------------------------------------------
root = tk.Tk()
root.title("RoboClone")
root.geometry("720x360")
try:
    root.iconbitmap("img/icon.ico")
except FileNotFoundError:
    pass

messagebox.showwarning(
    "Notice",
    "The program will start only after you press OK.\n\n"
    "Before clicking OK, please remember that this utility was created for personal use only.\n\n"
    "I accept no responsibility for malfunctioning drives, data loss, or any other issues that may arise from its use."
)

# --------------------------- Tk variables ---------------------------------
source_var        = tk.StringVar()
target_var        = tk.StringVar()
dry_run_var       = tk.BooleanVar()
exclusions_var    = tk.StringVar()
progress_var      = tk.IntVar()
post_action_var   = tk.StringVar(value="none")   # none | close | reboot | shutdown
tray_notify_var   = tk.BooleanVar(value=True)

# ----------  TITLE  ----------
title_label = ttk.Label(
    root,
    text="RoboClone",
    foreground="#357EC7",
    font=("Segoe UI", 40, "bold")
)
title_label.grid(row=0, column=0, columnspan=3)

# ------------------------------ Layout ------------------------------------
root.columnconfigure(1, weight=1)   # let middle column stretch
row = 2

# Source
ttk.Label(root, text="Source path:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
ttk.Entry(root, textvariable=source_var, width=80).grid(row=row, column=1, padx=5, sticky="ew")
ttk.Button(root, text="Browse", command=choose_source).grid(row=row, column=2, padx=10)
row += 1

# Target
ttk.Label(root, text="Target path:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
ttk.Entry(root, textvariable=target_var, width=80).grid(row=row, column=1, padx=5, sticky="ew")
ttk.Button(root, text="Browse", command=choose_target).grid(row=row, column=2, padx=10)
row += 1

# Exclusions
ttk.Label(root, text="Exclude (separate with ';')").grid(row=row, column=0, padx=10, pady=5, sticky="e")
ttk.Entry(root, textvariable=exclusions_var, width=80).grid(row=row, column=1, padx=5, sticky="ew")
row += 1

# Post‑action
ttk.Label(root, text="Post-action:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
combo_action = ttk.Combobox(
    root, textvariable=post_action_var,
    values=("none", "close", "reboot", "shutdown"),
    state="readonly", width=15)
combo_action.grid(row=row, column=1, padx=5, sticky="w")

# Dry‑run
ttk.Checkbutton(root, text="Simulation (no changes)", variable=dry_run_var).grid(
    row=row, column=1, padx=125, sticky="w")

# Tray notification toggle
ttk.Checkbutton(root, text="Enable notification when done", variable=tray_notify_var).grid(
    row=row, column=1, sticky="e")
row += 1

# Progress bar
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
progress_bar.grid(row=row, column=1, padx=5, pady=10, sticky="ew")
progress_label = ttk.Label(root, text="Waiting…")
progress_label.grid(row=row, column=2, padx=5)
row += 1

# Buttons
btn_frame = ttk.Frame(root)
btn_frame.grid(row=row, column=0, columnspan=3, pady=20)
ttk.Button(btn_frame, text="Start Copy", command=run_backup).pack(side="left", padx=10)
ttk.Button(btn_frame, text="Exit", command=root.destroy).pack(side="left", padx=10)
row += 1
btn_frame2 = ttk.Frame(root)
btn_frame2.grid(row=row, column=0, columnspan=3)
ttk.Button(btn_frame2, text="About...", command=show_about).pack(side="left", padx=10)

# Start the event loop
root.mainloop()
