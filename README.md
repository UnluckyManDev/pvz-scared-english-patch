# Plants vs. Zombies: Scared – English Translation Patch

A fan-made English translation for the free Chinese fan game **植物大战僵尸恐怖版**, also called
*Plants vs. Zombies: Scared* or *PvZ Horror Edition* (the game's file is `PVZ-Scared.exe`), version 1.0.1.

**This does not include the game.** Get the game from its creators first (see [Credits](#credits)).

## Download

Get the **.zip** from the [Releases page](../../releases/latest) (under *Assets*).

## Install (1 minute)

1. Unzip it and put **PvZ Horror English.exe** in your game folder (the folder with `PVZ-Scared.exe`).
2. Double-click it and press **Play in English**.
   If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**
   (the program isn't signed with a paid certificate).

The first time, it installs the translation (about 30 seconds) and puts a **PvZ Horror (English)** shortcut on
your desktop. After that, just use the shortcut to play.

## What the buttons do

| Button | What it does |
|---|---|
| Play in English | Installs the translation if needed, then starts the game in English |
| Go to level... | Jumps to a story level (1-41). Use it if a level never ends after the final wave (an Executioner walked off-screen). Your save is backed up first. |
| Change game folder | If you moved the game |
| Uninstall English | Restores the original Chinese game files |

While you play, the app waits in your taskbar: it translates popups and story text live. If you started from the
desktop shortcut, it closes by itself when you quit the game.

## What's translated

Menus and buttons, the store, the almanac (every plant and zombie, with their stories), all 40 story diaries, radio
broadcasts, chapter text, popups, banners (Ready... Set... PLANT!, FINAL WAVE...), difficulty and level labels, level
modifiers, and 53 redrawn images with English text.

Most text is translated by hand. Text that isn't in the translation yet is machine-translated once (needs internet;
only the game's own text is sent) and remembered after that. You can turn this off in the app.

Not translated: the game logo, and the developers' names in the credits.

## Your save

Your save is never changed, except by **Go to level...**, which backs it up first. Saves and backups are in:

```
%USERPROFILE%\AppData\LocalLow\TaoYuan\植物大战僵尸恐怖版\Save
```

Each backup has the date and time added, e.g. `YourName.json.20261008-175300.bak` (8 Oct 2026, 17:53:00).
To undo a level jump:

1. Close the game.
2. Delete or rename your current `YourName.json`.
3. Rename the backup you want back to `YourName.json` (remove the date and `.bak`).

You can delete old `.bak` files whenever you like; the game never uses them.

## Requirements

- Windows 10 or 11 (64-bit)
- The game at version 1.0.1 (shown at the bottom left of the main menu). If the game updates, the live
  translator turns itself off safely until the patch is updated.

## Troubleshooting

- **Antivirus warning:** the app is built with Python/PyInstaller and attaches to the game to translate it, which
  some antivirus programs flag by mistake. All the source code is in [`source/`](source).
- **"Translator could not attach":** right-click the app and choose **Run as administrator**.
- **Something wrong?** Open an issue and attach `live_translator.log` from your game folder.
- **Game updated and things broke?** Press **Uninstall English**, then **Play in English** again.

## How it works (for the curious)

- `source/pvz_english_patch.py` patches the game's text files and images with [UnityPy](https://github.com/K0lb3/UnityPy)
  (the original file is backed up and restored by Uninstall).
- `source/pvz_english_live.py` + `source/translator.js` use [Frida](https://frida.re) to translate text the game builds
  at runtime (popups, story text).
- `source/data/` holds the translations and the redrawn textures.
- `source/pvz_english_app.py` is the one-window app that ties it together.

### Build it yourself

With Python 3.10 (64-bit) on Windows, run `source/build.bat`. It installs the packages from
`source/requirements.txt` and builds `source/dist/PvZ Horror English.exe`. (Builds aren't byte-for-byte identical to
the release, because PyInstaller adds timestamps, but the code is the same.)

## Credits

- Original game: **植物大战僵尸恐怖版** by Bilibili creator **对不起贱笑了** and the TaoYuan team. The game is free and is
  only officially released through the creator's Bilibili posts (the game's own patch notes point to
  [this post](https://www.bilibili.com/opus/1064911049174548518)). Please download it there and support them.
- Based on *Plants vs. Zombies* by PopCap Games.
- English translation: **UnluckyManDev**.

This is an unofficial fan translation, not affiliated with the game's creators or with PopCap/EA. It contains no
game files.

**To the game's creators:** if you'd like this taken down, please open an issue and I'll remove it.

## License

The code is [MIT licensed](LICENSE). The story, characters, names and artwork belong to the game's creators and to
PopCap/EA; the translations and redrawn images are fan work shared so the game can be played in English.
