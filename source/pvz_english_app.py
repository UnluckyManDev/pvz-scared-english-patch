"""PvZ Horror Edition - English (one-click app).

Double-click -> Play: finds the game, installs the English file patch the first time, then starts the game
with the live translator. Also: skip a stuck level, uninstall.  `--play` starts playing immediately.
"""
import json, os, re, shutil, subprocess, sys, threading, time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

APP = "PvZ Horror Edition - English"
VERSION = "1.3"  # file-patch marker version (unchanged by app-only updates)
EXE = "PVZ-Scared.exe"
DATA_DIR = "PVZ-Scared_Data"
ASSETS, BACKUP, MARKER = "resources.assets", "resources.assets.original", "english_patch.json"
CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PvZHorrorEnglish")
CFG = os.path.join(CFG_DIR, "config.json")
SAVE_ROOT = os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\TaoYuan\植物大战僵尸恐怖版")
HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))

os.makedirs(CFG_DIR, exist_ok=True)
if sys.stdout is None or sys.stderr is None:  # windowed build: send prints to a log
    sys.stdout = sys.stderr = open(os.path.join(CFG_DIR, "app.log"), "a", encoding="utf-8", buffering=1)

import pvz_english_patch as patch     # file patch (UnityPy)
import pvz_english_live as live       # translator script + machine translation helpers


# ---------------------------------------------------------------- game folder
def load_cfg():
    try:
        return json.load(open(CFG, encoding="utf-8"))
    except Exception:
        return {}


def save_cfg(c):
    json.dump(c, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def is_game_dir(d):
    return bool(d) and os.path.isfile(os.path.join(d, EXE)) and os.path.isfile(os.path.join(d, DATA_DIR, ASSETS))


def find_game():
    for d in (HERE, os.path.dirname(HERE), load_cfg().get("game")):
        if is_game_dir(d):
            return d
    return None


def game_running():
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE}"], capture_output=True, text=True,
                         creationflags=0x08000000).stdout
    return EXE.lower() in out.lower()


# ---------------------------------------------------------------- file patch
def patch_state(game):
    data = os.path.join(game, DATA_DIR)
    try:
        m = json.load(open(os.path.join(data, MARKER), encoding="utf-8"))
        size = os.path.getsize(os.path.join(data, ASSETS))
        if m.get("version") == VERSION and m.get("size") == size and os.path.isfile(os.path.join(data, BACKUP)):
            return "installed"
    except Exception:
        pass
    return "missing"


def install_patch(game, status):
    data = os.path.join(game, DATA_DIR)
    assets, backup = os.path.join(data, ASSETS), os.path.join(data, BACKUP)
    status("Checking game files...")
    if patch.is_original(assets):            # fresh game, or a game update replaced the file
        shutil.copy2(assets, backup)
    elif not os.path.isfile(backup):
        raise RuntimeError("Your game files are already modified and there is no backup.\n"
                           "Please re-download the game from the official source and try again.")
    status("Installing English (first time only, about 30 seconds)...")
    tmp = assets + ".tmp"
    patch.build_patched(backup, tmp)
    os.replace(tmp, assets)
    json.dump({"version": VERSION, "size": os.path.getsize(assets)},
              open(os.path.join(data, MARKER), "w", encoding="utf-8"))


def uninstall_patch(game):
    data = os.path.join(game, DATA_DIR)
    backup = os.path.join(data, BACKUP)
    if not os.path.isfile(backup):
        return False
    shutil.copy2(backup, os.path.join(data, ASSETS))
    os.remove(backup)
    try:
        os.remove(os.path.join(data, MARKER))
    except OSError:
        pass
    return True


# ---------------------------------------------------------------- live translator
def run_game_with_translator(game, use_mt, status):
    import frida
    cache_file = os.path.join(game, "live_translation_cache.json")
    logf = os.path.join(game, "live_translator.log")

    def log(*a):
        with open(logf, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")

    live.CACHE, live.LOG = cache_file, logf    # machine-translation cache lives next to the game
    dct = json.load(open(live.res("dict_code.json"), encoding="utf-8"))
    cache = json.load(open(cache_file, encoding="utf-8")) if os.path.exists(cache_file) else {}
    dct["templates"] = {**cache, **dct.get("templates", {})}
    fp = json.load(open(live.res("fingerprint.json"), encoding="utf-8"))
    js = ("const DICT = %s;\nconst FP = %s;\nconst OPTS = %s;\n" % (
        json.dumps(dct, ensure_ascii=False), json.dumps(fp), json.dumps({"mt": use_mt, "debug": False, "skip": []}))
        + open(live.res("translator.js"), encoding="utf-8").read())

    pid = subprocess.Popen([os.path.join(game, EXE)], cwd=game).pid
    log("game started, pid", pid)
    session = None
    for _ in range(150):
        try:
            session = frida.attach(pid)
            break
        except Exception:
            time.sleep(0.1)
    if session is None:
        status("Game started, but the translator could not attach (try running as administrator).")
        return
    script = session.create_script(js)
    problem = []

    def on_message(m, data):
        if m["type"] != "send":
            log("JS error:", m.get("description", m)); return
        p = m["payload"]
        if p.get("type") == "mt":
            out = live.mt(p["text"], cache) if use_mt else None
            script.post({"type": "mt", "text": out})
        elif p.get("type") == "fatal":
            problem.append(p["msg"]); log("FATAL", p["msg"])
            status("This game version isn't supported by the live translator yet (menus are still in English).")
        elif p.get("type") == "ready":
            status("Playing in English. This window translates popups and story text live - leave it in the taskbar.")
        elif p.get("type") != "seen":
            log(json.dumps(p, ensure_ascii=False))

    script.on("message", on_message)
    script.load()
    done = threading.Event()
    session.on("detached", lambda *a: done.set())
    done.wait()
    log("game closed")


# ---------------------------------------------------------------- level select
LAST_LEVEL = 41


def save_path(save_root=None):
    root = save_root or SAVE_ROOT
    settings = json.load(open(os.path.join(root, "playerSettings.json"), encoding="utf-8-sig"))
    return os.path.join(root, "Save", settings["currentSave"] + ".json")


def read_progress(save_root=None):
    d = json.load(open(save_path(save_root), encoding="utf-8-sig"))
    return d["adventureLevel"], d.get("highestUnlockedAdventureLevel", d["adventureLevel"])


def set_level(n, save_root=None):
    """Make level n the current story level (unlocking it if needed). The save is backed up first."""
    if not 1 <= n <= LAST_LEVEL:
        raise ValueError(f"Level must be between 1 and {LAST_LEVEL}.")
    subprocess.run(["taskkill", "/F", "/IM", EXE], capture_output=True, creationflags=0x08000000)
    time.sleep(2)  # hard kill above: the game can't write the old level back into the save
    save = save_path(save_root)
    bak = save + time.strftime(".%Y%m%d-%H%M%S")
    i = 0
    while os.path.exists(f"{bak}{'-' + str(i) if i else ''}.bak"):
        i += 1
    shutil.copy2(save, f"{bak}{'-' + str(i) if i else ''}.bak")
    d = json.load(open(save, encoding="utf-8-sig"))
    d["adventureLevel"] = n
    d["highestUnlockedAdventureLevel"] = max(d.get("highestUnlockedAdventureLevel", 0), n)
    d["hasInitLevelData"] = False
    with open(save, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=4)


def make_shortcut():
    if not getattr(sys, "frozen", False):
        return
    q = lambda s: "'" + s.replace("'", "''") + "'"   # PowerShell single-quoted literal
    # create the desktop shortcut, or repoint it if it belongs to another copy of the game
    ps = ("$d=[Environment]::GetFolderPath('Desktop');$p=Join-Path $d 'PvZ Horror (English).lnk';"
          "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($p);"
          "if ((Test-Path $p) -and $s.TargetPath -eq %s) { exit };"
          "$s.TargetPath=%s;$s.Arguments='--play';$s.WorkingDirectory=%s;$s.Save()"
          % (q(sys.executable), q(sys.executable), q(HERE)))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, creationflags=0x08000000)


# ---------------------------------------------------------------- window
class App:
    def __init__(self, root):
        self.root = root
        self.game = find_game()
        self.busy = False
        self.playing = False
        self.autoclose = "--play" in sys.argv     # started from the desktop shortcut
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.title(APP)
        root.geometry("520x330")
        root.resizable(False, False)
        root.configure(bg="#1d1a17")
        try:
            root.iconbitmap(default=sys.executable)
        except Exception:
            pass
        fg, accent = "#f1e7d0", "#7fbf3f"
        tk.Label(root, text="Plants vs. Zombies: Horror Edition", font=("Segoe UI", 15, "bold"),
                 bg="#1d1a17", fg=fg).pack(pady=(18, 0))
        tk.Label(root, text=f"English translation v{VERSION}", font=("Segoe UI", 10), bg="#1d1a17",
                 fg="#bfb39a").pack()
        self.play_btn = tk.Button(root, text="▶   Play in English", font=("Segoe UI", 15, "bold"), bg=accent,
                                  fg="#10200a", activebackground="#95d653", relief="flat", padx=26, pady=8,
                                  cursor="hand2", command=self.play)
        self.play_btn.pack(pady=(18, 10))
        self.status = tk.Label(root, text="", wraplength=470, font=("Segoe UI", 9), bg="#1d1a17", fg=fg,
                               justify="center")
        self.status.pack(pady=(0, 10))
        row = tk.Frame(root, bg="#1d1a17"); row.pack()
        style = dict(font=("Segoe UI", 9), bg="#3a332b", fg=fg, activebackground="#4a4136", relief="flat",
                     padx=10, pady=4, cursor="hand2")
        self.btns = [tk.Button(row, text="Go to level...", command=self.goto_level, **style),
                     tk.Button(row, text="Change game folder", command=self.choose, **style),
                     tk.Button(row, text="Uninstall English", command=self.uninstall, **style)]
        for b in self.btns:
            b.pack(side="left", padx=4)
        self.online = tk.BooleanVar(value=load_cfg().get("online", True))
        tk.Checkbutton(root, text="Translate new text online (Google Translate)", variable=self.online,
                       command=self.save_online, bg="#1d1a17", fg="#bfb39a", selectcolor="#1d1a17",
                       activebackground="#1d1a17", activeforeground=fg, font=("Segoe UI", 8)).pack(pady=(12, 0))
        tk.Label(root, text="Fan translation - not affiliated with the game's developers",
                 font=("Segoe UI", 7), bg="#1d1a17", fg="#7d735f").pack(side="bottom", pady=6)
        self.refresh()
        if "--play" in sys.argv:
            root.after(300, self.play)

    # helpers
    def set_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def set_busy(self, busy):
        self.busy = busy
        def apply():
            state = "disabled" if busy else "normal"
            self.play_btn.config(state=state)
            for b in self.btns:
                b.config(state=state)
        self.root.after(0, apply)

    def refresh(self):
        if not self.game:
            self.status.config(text="Game folder not found yet - press Play and choose the folder with PVZ-Scared.exe.")
        else:
            st = "English installed" if patch_state(self.game) == "installed" else "English not installed yet"
            self.status.config(text=f"Game: {self.game}\n{st}")

    def after_game(self):
        if self.autoclose:
            self.root.after(0, self.root.destroy)
        else:
            self.set_status("Game closed. Press Play to start again.")
            self.root.after(0, self.root.deiconify)

    def on_close(self):
        if self.playing and game_running():
            if not messagebox.askyesno(APP, "The game is still running.\n\n"
                                            "This window translates popups and story text while you play. "
                                            "If you close it, those go back to Chinese (menus stay English).\n\n"
                                            "Close it anyway?"):
                return
        self.root.destroy()

    def save_online(self):
        c = load_cfg(); c["online"] = self.online.get(); save_cfg(c)

    def choose(self):
        d = filedialog.askdirectory(title="Choose the game folder (the one with PVZ-Scared.exe)")
        if not d:
            return False
        d = os.path.normpath(d)
        if not is_game_dir(d):
            messagebox.showerror(APP, "That folder doesn't contain PVZ-Scared.exe and PVZ-Scared_Data.\n"
                                      "Pick the folder you extracted the game into.")
            return False
        self.game = d
        c = load_cfg(); c["game"] = d; save_cfg(c)
        self.refresh()
        return True

    def run_bg(self, fn):
        def wrapper():
            self.set_busy(True)
            try:
                fn()
            except Exception as e:
                self.set_status("Something went wrong.")
                self.root.after(0, lambda: messagebox.showerror(APP, f"{e}"))
            finally:
                self.set_busy(False)
        threading.Thread(target=wrapper, daemon=True).start()

    # actions
    def play(self):
        if self.busy:
            return
        if not self.game and not self.choose():
            return
        if game_running():
            messagebox.showinfo(APP, "The game is already running. Close it first, then press Play.")
            return
        game, online = self.game, self.online.get()

        def job():
            if patch_state(game) != "installed":
                install_patch(game, self.set_status)
            make_shortcut()
            self.set_status("Starting the game...")
            self.root.after(0, self.root.iconify)
            self.playing = True
            try:
                run_game_with_translator(game, online, self.set_status)
            finally:
                self.playing = False
            self.after_game()
        self.run_bg(job)

    def goto_level(self):
        try:
            cur, top = read_progress()
        except Exception:
            messagebox.showerror(APP, "Couldn't find your save. Start the game once, then try again.")
            return
        n = simpledialog.askinteger(
            APP, f"You are on level {cur} (highest unlocked: {top}).\n\n"
                 f"Type the level you want to play (1-{LAST_LEVEL}):",
            parent=self.root, minvalue=1, maxvalue=LAST_LEVEL, initialvalue=cur)
        if n is None or n == cur:
            return
        what = (f"unlock levels up to {n} and make level {n} your current level" if n > top
                else f"make level {n} your current level (nothing gets locked again)")
        running = game_running()
        if not messagebox.askyesno(APP, f"This will {what}.\n\nYour save is backed up first."
                                        + ("\nThe game will be closed and restarted." if running else "")
                                        + "\n\nContinue?"):
            return
        def job():
            set_level(n)
            if running and self.game:
                self.set_status(f"Level {n} is now your current level - restarting the game...")
                self.root.after(0, self.root.iconify)
                self.playing = True
                try:
                    run_game_with_translator(self.game, self.online.get(), self.set_status)
                finally:
                    self.playing = False
                self.after_game()
            else:
                self.set_status(f"Level {n} is now your current level. Press Play.")
        self.run_bg(job)

    def uninstall(self):
        if not self.game and not self.choose():
            return
        if game_running():
            messagebox.showinfo(APP, "Close the game first, then press Uninstall again.")
            return
        if not messagebox.askyesno(APP, "Remove the English translation and restore the original Chinese files?"):
            return
        ok = uninstall_patch(self.game)
        self.refresh()
        messagebox.showinfo(APP, "Original Chinese files restored." if ok else "The English patch isn't installed.")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
