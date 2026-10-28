# Quran recitation videos (Arabic + Malayalam)

Makes 1920×1080 recitation videos in the style of Nermozhi's "അതിമനോഹരമായ ഖുർആൻ പാരായണം":
calm background, each verse shown while it's recited. Arabic (gold) on top, **Malayalam translation
larger underneath**, verse number, channel watermark top-right, and a source line bottom-left.

You supply the **recitation audio**. The script downloads the Arabic text and the Malayalam translation,
finds the verse timings from the pauses in your audio, and renders the MP4.

## The 3 commands

```bash
python3 quran.py new ar-rahman-1-40 --surah 55 --from 1 --to 40   # 1. create project + download verses
#   → copy your audio (mp3/m4a/wav) into videos/ar-rahman-1-40/
python3 quran.py time ar-rahman-1-40                               # 2. auto-detect verse timings
python3 quran.py render ar-rahman-1-40                             # 3. make the MP4
```

Output: `videos/<name>/<name>.mp4`. Use `--preview 30` on `render` to check just the first 30 seconds.

## What goes in a project folder (`videos/<name>/`)

| File | What it is |
|---|---|
| your audio (any `.mp3/.m4a/.wav`) | **required**: the recitation |
| `project.json` | settings (see below) |
| `verses.json` | Arabic + translation (downloaded; you can edit wording) |
| `timings.json` | when each verse starts (made by `time`, editable) |
| `background.mp4` or `background.jpg` | optional: your own background footage/photo |
| `backgrounds/` folder | optional: several clips/photos (sea, sand, mountains…). They play one after another, like the reference |
| `logo.png` | optional: round channel logo for the watermark |

## Backgrounds

Three animated backgrounds are built in (no footage needed). Set `"background"` in `project.json`,
or pass `--background` to `render`:

| Name | Look |
|---|---|
| `night-sky` | calm dark-blue sky with soft drifting light and stars (default) |
| `gold-smoke` | golden fire-smoke swirling in a band across a black screen (like MercifulServant's *Az-Zumar*) |
| `sea-parting` | two towering walls of water, light pouring through the gap, wet path to the horizon (like *Taha*) |

```bash
python3 quran.py render ar-rahman-1-40 --background gold-smoke
```

The first time you use one, it renders a 12–16 s seamless loop (about 3–4 minutes; saved in `.cache/`, so it's
instant after that). To change how they look, edit `templates/backgrounds/<name>.html`.
Your own `background.mp4` / `backgrounds/` folder is used instead when `"background"` is left empty.

## Settings in `project.json`

- `channel`: watermark text (top-right)
- `surah_name_ml`: surah name in Malayalam for the title card (e.g. `"അർറഹ്മാൻ"`)
- `intro_segments`: what the reciter says **before verse 1**: `1` = Bismillah (default), `2` = Ta'awwudh + Bismillah, `0` = nothing
- `intro_hold`: seconds the title card shows before the recitation starts (default 2.5)
- `background`: see above
- `dim`: how much to darken the background (0–1; default 0.45, or less for gold-smoke / sea-parting). `blur`: e.g. 6 to soften busy footage
- `translation`: `mal-abdulhameedmada` (default), `mal-muhammadkarakun` (simpler modern Malayalam), `mal-cheriyamundamab`
  (re-run `new` after changing it)

## If the timings are off

`time` looks for pauses between verses. It prints every verse start time. If something's wrong:

- Reciter pauses inside long verses → it already merges the shortest pauses; usually fine.
- Too few pauses found (fast reciter / background music) → `python3 quran.py time <name> --min-silence 0.3 --silence-db -30`
- Still off → open `timings.json` and fix the `start` of the wrong verse (seconds), then `render` again.

## Running it in Google Colab (from your phone)

```bash
!git clone https://github.com/abbizainul03-commits/project-fitrah-reels.git
%cd project-fitrah-reels/quran-video
!npm install puppeteer
!python3 quran.py new ar-rahman-1-40 --surah 55 --from 1 --to 40
```

Upload your audio into `project-fitrah-reels/quran-video/videos/ar-rahman-1-40/` with the folder icon on the left, then:

```bash
!python3 quran.py time ar-rahman-1-40
!python3 quran.py render ar-rahman-1-40
```

```python
from google.colab import files
files.download('videos/ar-rahman-1-40/ar-rahman-1-40.mp4')
```

(If the repo is private, clone with a GitHub token or upload the `quran-video` folder as a zip and `!unzip` it.)

Speed: about 1 minute of rendering per minute of video on a 4-core machine (Colab free tier is ~2× slower).

## Files

- `quran.py`: the tool (fetch → time → render)
- `render_cards.js`: renders text cards with Puppeteer or Playwright
- `templates/card.html`: the design (fonts, colours, layout). Edit this to restyle
- `templates/backgrounds/`: the generated backgrounds (WebGL shaders)
- `fonts/`: Amiri Quran (Arabic), Noto Sans Malayalam (verses), Baloo Chettan 2 (titles), all SIL OFL

Text source: [fawazahmed0/quran-api](https://github.com/fawazahmed0/quran-api) (Uthmani Hafs Arabic + Malayalam translations).
