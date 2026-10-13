"""English translation patch for 植物大战僵尸恐怖版 (Plants vs. Zombies: Horror Edition) v1.0.1.

Usage:
  pvz_english_patch.exe                 install (looks for the game next to this program)
  pvz_english_patch.exe <game folder>   install into that folder
  pvz_english_patch.exe --uninstall     restore the original Chinese files
"""
import io, json, os, re, shutil, struct, subprocess, sys, zipfile

PATCH_VERSION = "1.1"
KNOWN_BUILD = "c559680ae6994bdb968f0642f65d266a"  # boot.config build-guid of game v1.0.1
EXE_NAME = "PVZ-Scared.exe"
DATA_DIR = "PVZ-Scared_Data"
ASSETS = "resources.assets"
BACKUP = "resources.assets.original"

CJK = re.compile(r"[一-鿿　-〿＀-￯]")
DIARY_FONT_SIZE = 24
ZOMBIE_KEYS = {
    "蜗牛畸变体": "Woniu", "魔化戴夫": "dave_Level1", "戴夫之骨": "DaveBone",
    "戴夫之眼": "dave_eye", "戴夫之心": "dave_heart", "霸王尸": "ZombieKing",
    "纸人新娘": "Bride", "天使": "Angel", "烂肉": "RottenMeat", "小烂肉": "MiniRottenMeat",
    "神圣巨人僵尸": "Paladin_Zombie_Gargantuar", "借命人": "Jieming", "诡异清扫者": "Zombie_Clear",
}
DIARY_TITLES = {f"日记其{c}": f"Diary Entry {i}" for i, c in enumerate("一二三四五六七", 1)}


def res_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def load_json(name):
    with open(os.path.join(res_dir(), "data", name), encoding="utf-8") as f:
        return json.load(f)


def find_game(argv):
    here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
    candidates = [a for a in argv if not a.startswith("--")] + [here, os.path.dirname(here), os.getcwd()]
    for c in candidates:
        if os.path.isfile(os.path.join(c, DATA_DIR, ASSETS)):
            return c
    print("Could not find the game next to this program.")
    path = input("Drag the game folder (the one with PVZ-Scared.exe) here and press Enter: ").strip().strip('"')
    if os.path.isfile(os.path.join(path, DATA_DIR, ASSETS)):
        return path
    sys.exit("That folder doesn't contain PVZ-Scared_Data\\resources.assets.")


def game_running():
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}"], capture_output=True, text=True).stdout
    return EXE_NAME.lower() in out.lower()


def scan(raw):
    """Unity-serialized strings (int32 length + utf8, 4-byte aligned) that contain CJK."""
    res, i, n = [], 0, len(raw)
    while i + 4 <= n:
        L = struct.unpack_from("<i", raw, i)[0]
        if 1 <= L <= 20000 and i + 4 + L <= n:
            try:
                s = raw[i + 4:i + 4 + L].decode("utf-8")
                if CJK.search(s):
                    res.append((i, L, s))
                    i = (i + 4 + L + 3) & ~3
                    continue
            except UnicodeDecodeError:
                pass
        i += 4
    return res


def enc_str(s):
    b = s.encode("utf-8")
    return struct.pack("<i", len(b)) + b + b"\0" * ((-len(b)) % 4)


def to_bytes(script):
    return script if isinstance(script, bytes) else script.encode("utf-8", "surrogateescape")


def patch_level_zip(name, data, diary):
    zin = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            content = zin.read(info.filename)
            if info.filename == "level.json":
                lvl = json.loads(content.decode("utf-8"))
                m = re.fullmatch(r"序章-(\d+)", lvl.get("LevelName", ""))
                if m:
                    lvl["LevelName"] = f"Prologue-{m.group(1)}"
                if lvl.get("LevelDescription") == "无":
                    lvl["LevelDescription"] = "None"
                for comp in lvl.get("components", []):
                    tl = comp.get("data", {}).get("textLayout")
                    if comp.get("type") == "Diary" and tl and tl.get("fontSize", 0) > DIARY_FONT_SIZE:
                        tl["fontSize"] = DIARY_FONT_SIZE
                content = json.dumps(lvl, ensure_ascii=False, indent=2).encode("utf-8")
            elif info.filename == "assets/Diary/intro.json" and name in diary:
                pages = json.loads(content.decode("utf-8"))
                for k in list(pages):
                    if k.startswith("PageTitle_"):
                        pages[k] = DIARY_TITLES.get(pages[k], pages[k])
                    elif k in diary[name]:
                        pages[k] = diary[name][k]
                content = json.dumps(pages, ensure_ascii=False, indent=4).encode("utf-8")
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = zipfile.ZIP_STORED if info.filename.endswith("/") else zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr
            zout.writestr(zi, content)
    return buf.getvalue()


def build_patched(src, dst):
    import UnityPy
    from PIL import Image

    loc, ui, diary, radio = (load_json(n) for n in ("loc_en.json", "ui_en.json", "diary_en.json", "radio_en.json"))
    tex_dir = os.path.join(res_dir(), "data", "textures")
    textures = {}
    for fn in os.listdir(tex_dir):
        pid, name = fn[:-4].split("__", 1)
        textures[int(pid)] = (name, os.path.join(tex_dir, fn))

    print("Loading game data (about 30 seconds)...")
    env = UnityPy.load(src)
    sf = list(env.files.values())[0]
    st = dict(text=0, levels=0, ui=0, keys=0, images=0, skipped_images=0)
    for o in env.objects:
        t = o.type.name
        if t == "TextAsset":
            d = o.read()
            name = d.m_Name
            if name in ("en", "zh"):
                out = dict(loc)
                if name == "zh":  # keep the language id the game uses for this file
                    out["LanguageType"] = json.loads(to_bytes(d.m_Script).decode("utf-8"))["LanguageType"]
                d.m_Script = json.dumps(out, ensure_ascii=False, indent=2)
                d.save(); st["text"] += 1
            elif name == "RadioSubtitles":
                rs = json.loads(to_bytes(d.m_Script).decode("utf-8"))
                for bi, b in enumerate(rs["broadcasts"]):
                    if bi < len(radio) and len(b["subtitles"]) == len(radio[bi]):
                        for si, s in enumerate(b["subtitles"]):
                            s["text"] = radio[bi][si]
                d.m_Script = json.dumps(rs, ensure_ascii=False, indent=2)
                d.save(); st["text"] += 1
            elif re.fullmatch(r"level0-\d+", name):
                d.m_Script = patch_level_zip(name, to_bytes(d.m_Script), diary).decode("utf-8", "surrogateescape")
                d.save(); st["levels"] += 1
        elif t == "Texture2D" and o.path_id in textures:
            want, png = textures[o.path_id]
            d = o.read()
            img = Image.open(png).convert("RGBA")
            if d.m_Name != want or (d.m_Width, d.m_Height) != img.size:
                st["skipped_images"] += 1
                continue
            d.set_image(img)
            d.save(); st["images"] += 1
        elif t == "MonoBehaviour":
            raw = o.get_raw_data()
            hits = scan(raw)
            if not hits:
                continue
            mb = o.read(check_read=False)
            try:
                script = mb.m_Script.read().m_ClassName
            except Exception:
                script = None  # script registry not loadable: match by text only
            if script in ("TMP_FontAsset", "SkeletonAsset"):
                continue
            new = bytearray(raw)
            changed = False
            for off, L, s in reversed(hits):
                if script == "ZombieData_" or (script is None and s in ZOMBIE_KEYS and s not in ui):
                    repl, kind = ZOMBIE_KEYS.get(s), "keys"
                else:
                    repl, kind = ui.get(s), "ui"
                if repl is None:
                    continue
                new[off:off + 4 + L + ((-L) % 4)] = enc_str(repl)
                changed = True
                st[kind] += 1
            if changed:
                o.set_raw_data(bytes(new))
    print("Saving...")
    with open(dst, "wb") as f:
        f.write(sf.save())
    return st


def is_original(path):
    import UnityPy
    env = UnityPy.load(path)
    for o in env.objects:
        if o.type.name == "TextAsset" and o.peek_name() == "zh":
            loc = json.loads(to_bytes(o.read().m_Script).decode("utf-8"))
            return loc.get("PeaShooter") == "豌豆射手"
    return False


def main():
    print(f"=== PvZ Horror Edition - English Patch v{PATCH_VERSION} ===\n")
    game = find_game(sys.argv[1:])
    data = os.path.join(game, DATA_DIR)
    assets, backup = os.path.join(data, ASSETS), os.path.join(data, BACKUP)
    if game_running() and not os.environ.get("PVZPATCH_SKIP_RUNNING_CHECK"):
        sys.exit("Please close the game first, then run this again.")

    if "--uninstall" in sys.argv:
        if not os.path.isfile(backup):
            sys.exit("No backup found - the patch doesn't seem to be installed.")
        shutil.copy2(backup, assets)
        os.remove(backup)
        print("Original Chinese files restored.")
        return

    try:
        build = open(os.path.join(data, "boot.config"), encoding="utf-8").read()
        if KNOWN_BUILD not in build:
            print("WARNING: this is a different game version than the patch was made for (v1.0.1).")
            print("         Most text should still work; anything that doesn't match is left in Chinese.\n")
    except OSError:
        pass

    if not os.path.isfile(backup):
        print("Checking your game files...")
        if not is_original(assets):
            sys.exit("resources.assets is already modified and there is no backup.\n"
                     "Re-download the game from the official source, then run this patch.")
        shutil.copy2(assets, backup)
        print(f"Backed up the original to {DATA_DIR}\\{BACKUP}")

    tmp = assets + ".tmp"
    st = build_patched(backup, tmp)
    os.replace(tmp, assets)
    print(f"\nDone! Translated {st['text']} text files, {st['levels']} levels, {st['ui']} menu labels, "
          f"{st['keys']} zombie names, {st['images']} images.")
    if st["skipped_images"]:
        print(f"({st['skipped_images']} images skipped because they differ in this game version.)")
    print("Start the game normally. To undo, run this program with --uninstall (or use Uninstall.bat).")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code not in (None, 0):
            print(f"\n{e.code}" if isinstance(e.code, str) else "")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nERROR: {e!r}\nThe game files were not changed. Please report this error.")
    try:
        input("\nPress Enter to close...")
    except (EOFError, RuntimeError):
        pass
