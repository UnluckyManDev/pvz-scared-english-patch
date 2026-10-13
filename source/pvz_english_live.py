"""PvZ Horror Edition - Live English launcher.

Starts the game and attaches a live translator (Frida) that turns the remaining hardcoded Chinese
text into English as it appears. Unknown text is machine-translated once and cached.

  PvZ_English_Live.exe              start the game (looks next to this program / its parent folder)
  PvZ_English_Live.exe --attach     attach to an already running game
  PvZ_English_Live.exe --offline    no machine translation (only built-in translations)
"""
import ctypes, json, os, re, subprocess, sys, threading, time, urllib.parse, urllib.request

APP = "PvZ Horror English (Live)"
EXE = "PVZ-Scared.exe"


def res(name):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), name)


HOME = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
CACHE = os.path.join(HOME, "live_translation_cache.json")
LOG = os.path.join(HOME, "live_translator.log")


def log(*a):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")


def msgbox(text):
    try:
        ctypes.windll.user32.MessageBoxW(0, text, APP, 0x40)
    except Exception:
        print(text)


def find_game():
    for d in (HOME, os.path.dirname(HOME), os.getcwd()):
        if os.path.isfile(os.path.join(d, EXE)):
            return os.path.join(d, EXE)
    return None


# ---------------- machine translation (only for text not in the built-in dictionary) ----------------
def google_translate(text):
    url = ("https://translate.googleapis.com/translate_a/single?client=gtx&sl=zh-CN&tl=en&dt=t&q="
           + urllib.parse.quote(text))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=4) as r:
        data = json.loads(r.read().decode("utf-8"))
    return "".join(seg[0] for seg in data[0] if seg and seg[0])


def mt(tpl, cache):
    if tpl in cache:
        return cache[tpl]
    try:
        out = google_translate(tpl)
        # placeholders {1},{2}.. must survive; otherwise give up on this one
        if sorted(re.findall(r"\{\d+\}", out)) != sorted(re.findall(r"\{\d+\}", tpl)):
            return None
        cache[tpl] = out
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
        log("MT", json.dumps(tpl, ensure_ascii=False), "->", json.dumps(out, ensure_ascii=False))
        return out
    except Exception as e:
        log("MT failed:", repr(e))
        return None


def main():
    import frida

    args = sys.argv[1:]
    use_mt = "--offline" not in args
    dct = json.load(open(res("dict_code.json"), encoding="utf-8"))
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    dct["templates"] = {**cache, **dct.get("templates", {})}
    fp = json.load(open(res("fingerprint.json"), encoding="utf-8"))
    js = ("const DICT = %s;\nconst FP = %s;\nconst OPTS = %s;\n" % (
        json.dumps(dct, ensure_ascii=False), json.dumps(fp), json.dumps({"mt": use_mt, "debug": "--debug" in args, "skip": [a[7:] for a in args if a.startswith("--skip=")]}))
        + open(res("translator.js"), encoding="utf-8").read())

    if "--attach" in args:
        pid = int(subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", f"(Get-Process '{EXE[:-4]}' | Select-Object -First 1).Id"]).strip())
    else:
        game = find_game()
        if not game:
            msgbox("Put this program in the game folder (next to PVZ-Scared.exe) and run it again.")
            return
        pid = subprocess.Popen([game], cwd=os.path.dirname(game)).pid
    log("attaching to pid", pid)

    session = None
    for _ in range(100):
        try:
            session = frida.attach(pid)
            break
        except Exception:
            time.sleep(0.1)
    if session is None:
        msgbox("Could not attach to the game. Try running this program as administrator.")
        return
    script = session.create_script(js)
    seen_log = open(os.path.join(HOME, "live_seen_chinese.log"), "a", encoding="utf-8")

    def on_message(m, data):
        if m["type"] != "send":
            log("JS error:", m.get("description", m))
            return
        p = m["payload"]
        t = p.get("type")
        if t == "mt":
            out = mt(p["text"], cache) if use_mt else None
            script.post({"type": "mt", "text": out})
        elif t == "seen":
            seen_log.write(json.dumps(p["text"], ensure_ascii=False) + "\n"); seen_log.flush()
        elif t == "fatal":
            log("FATAL", p["msg"]); msgbox(p["msg"] + "\nThe game will run without live translation.")
        else:
            log(json.dumps(p, ensure_ascii=False))

    script.on("message", on_message)
    script.load()
    done = threading.Event()
    session.on("detached", lambda *a: done.set())
    done.wait()
    log("game closed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("crash:", repr(e))
        msgbox(f"Live translator error:\n{e!r}")
