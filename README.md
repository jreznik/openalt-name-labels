# openalt-name-labels

Prints name labels for **OpenAlt** conference badges on a **Bixolon XD5-40d** label printer, from **macOS or Linux**.

- **Names straight from Pretalx:** speakers of confirmed and accepted talks, and booth staff (track **Stánek**). Speaker and booth labels are printed in separate runs, so each goes on the right badges.
- **Other sources:** names typed on the command line, or a TXT, CSV or JSON file.
- **Same look as the original badges:** **Open Sans Bold 29.89 pt**, first name on line 1 and surname on line 2. A name only shrinks if it's too wide for the label.
- **Any language:** accents and other non-English letters (Řezník, Ødegård, Łukasiewicz) always print correctly. The font is bundled, so labels look the same on every computer.
- **Safe by default:** the tool shows the full list of labels and asks before printing.

## Quick start (conference day)

Do the setup (below) a day or two before the event: it needs internet access to install the dependencies.

```sh
cd openalt-name-labels
L=.venv/bin/openalt-name-labels

$L --pretalx --list                        # 1. check who gets a label; prints nothing
$L --pretalx --category speaker            # 2. speaker badges: shows the list, asks, prints
$L --pretalx --category booth              # 3. booth badges (load the booth badge stock first)

$L "Jana Nováková"                         # a late registration (name only)
$L --pretalx --category booth --only 9     # reprint label 9 from the list, with its booth name
$L --pretalx --category speaker --start 37 # resume after a paper jam at label 37
```

---

## Hardware

| | |
|---|---|
| **Printer** | Bixolon **XD5-40d**: desktop direct thermal label printer, 203 dpi (8 dots/mm), 104 mm print head, USB. Supports ZPL II, EPL and SLCS. Shows up in CUPS as `usb://BIXOLON/XD5-40d?serial=…`. |
| **Labels** | **70 × 30 mm** white **direct thermal** labels on a roll, separated by a gap. No ribbon is needed: the "d" model has no ribbon, and the heat darkens the label paper itself. |
| **Connection** | USB cable to a Mac or Linux PC. No Bixolon driver is needed. |

- **Other models:** the XD5-40**t** (thermal transfer, needs a ribbon) works the same way. The 300 dpi XD5-43d/t also works with `--dpi 300`.
- **Other label sizes:** set `--width`/`--height`. The tool centres the label on the 104 mm head, because label rolls sit centred between the printer's guides.
- **Paper:** direct thermal labels fade over months and with heat or sunlight. That's fine for a conference, but not for archival use.

---

## Installation

### 1. Prerequisites

| | macOS | Linux |
|---|---|---|
| Python 3.10+ | `brew install python` (if `python3 -V` is too old) | `sudo apt install python3 python3-venv` or `sudo dnf install python3`. RHEL/Alma/Rocky 9: `sudo dnf install python3.11`, then run `PYTHON=python3.11 ./setup.sh` |
| CUPS (printing system) | built in | `sudo apt install cups` or `sudo dnf install cups`, then `sudo systemctl enable --now cups` |
| git | `xcode-select --install` | `sudo apt install git` or `sudo dnf install git` |

### 2. Plug in the printer and run setup

Connect the printer over USB, switch it on, load the labels, then run:

```sh
git clone git@github.com:jreznik/openalt-name-labels.git
cd openalt-name-labels
./setup.sh
```

`setup.sh` does four things:
1. Creates a private Python environment in `.venv/` and installs the tool there.
2. Creates the private config file `openalt-name-labels.toml` from the example (see [Pretalx configuration](#pretalx-configuration)).
3. Turns on the git hook that stops the token from being committed.
4. Finds the printer on USB and adds it to CUPS as a printer named **`XD5`**. The printer is set to retry after errors instead of stopping.

It asks for your password (sudo) only if it has to. That's usually on Linux; on macOS an admin account doesn't need it. Running it again is safe.

| setup option | meaning |
|---|---|
| `--no-printer` | skip the printer step, e.g. to make previews without a printer |
| `--queue NAME` | name the printer something other than `XD5` |
| `--uri usb://…` | use this printer address instead of auto-detecting it (`lpinfo -v` lists addresses) |

**Optional:** to run the tool as plain `openalt-name-labels` from anywhere:
```sh
ln -s "$PWD/.venv/bin/openalt-name-labels" ~/.local/bin/        # Linux (~/.local/bin should be on PATH)
ln -s "$PWD/.venv/bin/openalt-name-labels" /opt/homebrew/bin/   # macOS with Homebrew
```

### 3. Add the Pretalx token

Open `openalt-name-labels.toml` and put your Pretalx API token in `token = "…"`. Get it in Pretalx from your user menu → API. URL and event are already set for OpenAlt 2026. Check it works:

```sh
.venv/bin/openalt-name-labels --pretalx --list
```

### 4. Calibrate the labels (once per roll type)

The printer has to learn where each label starts:

1. With the printer ready, press **Feed** once. On a new roll it feeds 3–5 labels and detects the label length by itself.
2. If labels still don't stop in the right place, run gap calibration:
   1. Hold **Pause** for about 2 s, until both lights turn orange, then release.
   2. The lights now cycle through combinations. Press **Feed** when **light 1 is solid orange and light 2 blinks green**.

To check the position, print a mm ruler grid:
```sh
.venv/bin/openalt-name-labels --grid
```
Each grid cell is labelled with its position in mm as `x,y`. The values at the label's edges show its real size and where it sits under the print head. With the 70 × 30 mm roll, the label runs from about x = 17 to x = 87 mm, centred on the 104 mm print head.

---

## Usage

The examples use `L=.venv/bin/openalt-name-labels`.

### Confirmation before printing

By default the tool shows the **full numbered list** of labels it is about to print and asks:

```
  -- stánek --
    1. Base48
    2. Base48
    3. KREYREN  —  INDUSTRA
    …
17 label(s) -> printer 'XD5' (70x30 mm @ 203 dpi, offset 17 mm)
Print these 17 label(s)? [y/N]
```

Only `y` (or `ano`) prints; anything else, Enter or Ctrl-C prints nothing.

| to… | use |
|---|---|
| only see the list | `--list` |
| see the labels themselves | `--preview out/` (one PNG per label, nothing printed) |
| skip the question, e.g. in a script | `--yes`, or `confirm = false` under `[print]` in the config |

### From Pretalx

```sh
$L --pretalx --list                         # all labels, grouped by category
$L --pretalx --category speaker             # print speaker badges
$L --pretalx --category booth               # print booth badges
$L --pretalx --category booth --preview out/
$L --pretalx --pretalx-state confirmed --category speaker   # confirmed talks only
```

Only **confirmed and accepted** submissions are used; rejected, withdrawn and draft ones are ignored. The data is split into two categories, which go on different badges. The tool therefore refuses to print both in one run and asks for `--category`.

| category | who | label |
|---|---|---|
| `speaker` (přednášející) | speakers of every talk or workshop | the name |
| `booth` (stánek) | people on submissions in track **Stánek** (`booth_track`) | the name, with the booth name in a smaller line below |

- **Speaker and booth staff:** a person who does both gets **both** badges.
- **Several talks:** a speaker with several talks gets **one** speaker badge; the skipped repeats are reported. Two different people with the same name each get a badge, because the tool tells them apart by their Pretalx speaker ID.
- **Booths without real people:** a booth that lists only the placeholder "Bezejmenný přednášející", or nobody, gets labels with just the booth name. There are 2 per booth by default (`unnamed_booth_copies` in the config, or `--booth-copies N`).
- **Sorting:** labels are sorted alphabetically within each category, so badges are easy to find at registration.

### From the command line or a file

```sh
$L "Jaroslav Řezník" "Anna Jungmannová"
$L -f names.txt                         # one name per line, # for comments
$L -f speakers.csv                      # finds a "Name" / "Jméno" column automatically
$L -f speakers.csv --column "Full name" # or name the column yourself
$L -f schedule.json                     # Pretalx schedule export or speakers JSON
some-command | $L -f -                  # read names from stdin
$L -f speakers.csv "Extra Guest"        # combine sources
```

Names from files and the command line have no category. They print in the order given, as name-only labels. Repeated names are printed once; use `--keep-duplicates` to print every repeat, or `--copies N` for several copies of each label.

### What the tool checks

- **Missing characters:** if the font can't draw a character, such as Chinese, Arabic or emoji, the tool refuses to print that name rather than print it with the character silently missing. Fix the name, use `--font` with a font that has the characters, or pass `--force`.
- **Text clean-up:** accents that arrive as separate characters are joined back to their letters (Unicode NFC), so "Jiří" never prints as "Jiř̌", and invisible characters are removed.
- **File encoding:** CSV/TXT files that aren't UTF-8 are read as Windows-1250, the usual encoding of Czech Excel exports, with a warning.
- **Fit:** text never reaches the label edge. A name that is too wide, or whose accents and descenders wouldn't fit, shrinks just enough. All other names keep the original size.
- **Printer state:** if the `XD5` printer is missing, disabled or rejecting jobs, the tool stops before sending and tells you how to fix it.
- **Job progress:** after sending, the tool waits until CUPS has passed every label to the printer, and shows printer messages such as "Waiting for printer to become available". `--no-wait` skips this.

### On the conference day

- **Online vs. offline:** printing works offline; only `--pretalx` needs internet access. If the venue Wi-Fi is unreliable, export a backup the evening before, e.g. `$L --pretalx --category speaker --output speakers.zpl`. Print it later with `lp -d XD5 -o raw speakers.zpl`.
- **Preview first:** run `$L --pretalx --list`, then `--preview out/` for each category, and look through the PNGs.
- **Two runs:** print `--category speaker` on the speaker badges, then `--category booth` on the booth badges.
- **Resuming:** labels are numbered in the list. If the printer jams or runs out of labels partway through, fix it, then resume with `--start N`, where N is the first label that didn't print.
- **Reprinting a badge:** find its number with `--list`, then use `--only N`. Several work too, e.g. `--only 3,9,12-14`. This keeps the booth name on booth labels. A plain name also works for speaker badges: `$L "Jiří Rak"`.

---

## Pretalx configuration

The Pretalx settings, including the secret **API token**, live in **`openalt-name-labels.toml`** in the project folder. `setup.sh` creates it from [`openalt-name-labels.example.toml`](openalt-name-labels.example.toml):

```toml
[pretalx]
url = "https://talks.openalt.cz" # Pretalx instance
event = "openalt-2026"           # event slug from the URL
token = "…"                      # Pretalx → your user menu → API → token
states = ["confirmed", "accepted"]
booth_track = "Stánek"           # track whose submissions are booths (any language)
placeholder_names = ["Bezejmenný přednášející"]  # Pretalx accounts that aren't real people
unnamed_booth_copies = 2         # labels per booth without real people

[print]
confirm = true                   # show the list and ask before printing
```

**Keeping the token private:**
- **Git-ignored:** the file is never added to git, so it isn't pushed to GitHub.
- **Pre-commit hook:** `.githooks/pre-commit`, turned on by `setup.sh`, blocks a commit that adds this file (even with `git add -f`) or anything that looks like a token in another file. On a fresh clone, run `./setup.sh` before committing.
- **Readable only by you:** the file is created with `chmod 600`, and the tool warns if other users can read it.
- **Not on the command line:** the token is never taken as a command-line option, which would put it in shell history and the process list. It's also never printed.
- **Without a token:** only public data is available, meaning confirmed talks in the published schedule.

**Where the tool looks** for the config file, in this order:
1. `--config FILE`
2. `$OPENALT_LABELS_CONFIG`
3. `./openalt-name-labels.toml` in the current folder
4. `openalt-name-labels.toml` next to `setup.sh`
5. `~/.config/openalt-name-labels/config.toml`

The environment variables `PRETALX_URL` and `PRETALX_TOKEN`, and the options `--pretalx-url`, `--pretalx-event` and `--pretalx-state`, override the file for a one-off run.

---

## Options

**Names**

| option | default | description |
|---|---|---|
| `NAME …` | | names given directly |
| `-f`, `--file FILE` | | TXT, CSV or JSON file, or `-` for stdin; repeatable |
| `--column NAME` | auto | CSV column with the names |
| `--pretalx` | | fetch from Pretalx using the config file |
| `--category` | | `speaker` or `booth`; required when Pretalx data contains both |
| `--pretalx-event`, `--pretalx-url` | config | override the config's event or URL |
| `--pretalx-state` | config, else `confirmed,accepted` | submission states to include |
| `--booth-copies N` | config, else 2 | labels per booth without real people |
| `--keep-duplicates` | off | print repeated labels every time |
| `--config FILE` | see above | use this config file |

**Printing**

| option | default | description |
|---|---|---|
| `--list` | | show the numbered list, print nothing |
| `--preview DIR` | | save a PNG per label, print nothing |
| `--output FILE` | | save the printer data (ZPL) to a file, print nothing |
| `-y`, `--yes` | | print without showing the list and asking |
| `--start N` | 1 | start at the N-th label, e.g. to resume after a jam |
| `--only LIST` | | print only these label numbers from the list, e.g. `9`, `3,9` or `12-14` |
| `--copies N` | 1 | copies of each label |
| `--cut` | off | cut after each label; needs the optional cutter. Without it, labels print in tear-off mode. **On a printer without a cutter this causes an "auto cutter jam" error, and you must switch the printer off and on again** (see [Troubleshooting](#troubleshooting)) |
| `--force` | off | print even if the font lacks some characters |
| `--no-wait` | off | don't wait for CUPS to finish the job |
| `-P`, `--printer` | `XD5` | CUPS printer name (env `BADGE_PRINTER`) |
| `--list-printers` | | show the printers set up in CUPS |
| `--grid` | | print the mm ruler grid |

**Layout**

| option | default | description |
|---|---|---|
| `--width`, `--height` | 70, 30 mm | label size (env `BADGE_WIDTH_MM`, `BADGE_HEIGHT_MM`) |
| `--offset-x` | centred on the 104 mm head | label's left edge from the head's left edge, in mm (env `BADGE_OFFSET_X_MM`) |
| `--margin` | 3 mm | blank border at the sides |
| `--font-size` | 29.8879 pt | type size from the original badges |
| `--line-spacing` | 36.851 pt | distance from the first-name line to the surname line |
| `--fit` | off | ignore `--font-size` and make every name as large as fits |
| `--max-font` | none | with `--fit`, cap the text height in mm |
| `--font` | Open Sans Bold (bundled) | any TTF/OTF file |
| `--dpi` | 203 | use 300 for the XD5-43 |
| `--darkness` | printer setting | 0–30 |
| `--speed` | printer setting | inches per second |

---

## Troubleshooting

| problem | fix |
|---|---|
| `setup.sh`: no `usb://BIXOLON` device found | Check the cable and power. Run `lpinfo -v` (on Linux maybe `sudo lpinfo -v`) and pass the address with `--uri`. |
| Linux: `setup.sh` finds no printer, but `lsusb` shows it | Unplug and replug the printer. If `ipp-usb` is installed and has claimed the device, stop it: `sudo systemctl stop ipp-usb`. |
| macOS: "Raw queues are no longer supported" | Expected. `setup.sh` avoids it by using the bundled `cups/xd5-raw.ppd` instead. The warning "Printer drivers are deprecated" is harmless. |
| Linux: `lpadmin: Forbidden` | Run with sudo, or join the admin group: `sudo usermod -aG lpadmin $USER` (Debian/Ubuntu) or `sudo usermod -aG sys $USER` (Fedora). |
| "Pretalx refused access (401/403)" | The token is missing, wrong or expired. Generate a new one in Pretalx and put it in `openalt-name-labels.toml`. |
| "Pretalx event … not found" | Check `url` and `event` in the config. Without a token the event must have a public schedule. |
| "the data has N speaker and M booth label(s)" | Add `--category speaker` or `--category booth`. |
| "characters the font cannot draw" | Correct the name in Pretalx, print that one with `--font` pointing to a font that has the characters, or use `--force`. |
| Text cut off or off-centre | Print `--grid` and check the label edges, then adjust `--width`, `--height` or `--offset-x`. |
| Print runs over two labels, or the printer feeds without stopping | Calibrate (installation step 4). |
| Too faint | Use `--darkness 20` or higher. |
| "auto cutter jam" after using `--cut` | The printer has no cutter. Restarting alone may not clear the error, so: 1. Run `printf '^XA^MMT^XZ\n' \| lp -d XD5 -o raw` to switch back to tear-off mode; nothing prints. 2. If `lpstat -p XD5` shows the queue as disabled, run `cupsenable XD5`. 3. Switch the printer off and on again. 4. If labels now print across the gap, calibrate (installation step 4). |
| "job … is still queued" | The printer is off, unplugged or out of labels. Fix it and the job continues by itself. `lpstat -p XD5` shows the state, and `cancel -a XD5` drops all jobs. |
| "queue 'XD5' is disabled" | Run `cupsenable XD5 && cupsaccept XD5`. This happens with queues not created by `setup.sh`, which stop after any error. |

---

## How it works

1. Names come from Pretalx (`/api/events/<event>/submissions/?state=…&expand=speakers,track`) or from files, and are sorted into speaker and booth labels.
2. Each label is drawn as a black-and-white image (Pillow), using the bundled Open Sans Bold.
3. The image is converted to the printer's ZPL language (`^GFA`).
4. It is sent to CUPS with `lp -o raw`, and the printer's own ZPL interpreter prints it.

The print-area width is always set to the full 104 mm head, and the label's position is set explicitly. The XD5 centres any narrower print area on the head, which would shift the label sideways.

| file | purpose |
|---|---|
| `openalt_name_labels/sources.py` | reading names, Pretalx, speaker/booth categories |
| `openalt_name_labels/config.py` | config file |
| `openalt_name_labels/render.py` | label layout |
| `openalt_name_labels/zpl.py` | image → ZPL |
| `openalt_name_labels/printer.py` | CUPS: checks, sending, waiting |
| `cups/xd5-raw.ppd` | passthrough printer description for CUPS |
| `setup.sh`, `.githooks/pre-commit` | installation, token guard |

Run the tests with `.venv/bin/pip install -e '.[dev]' && .venv/bin/pytest`.

## License

[MIT](LICENSE) © 2026 Jaroslav Řezník <jaroslav.reznik@openalt.org>, OpenAlt.

The bundled Open Sans font is © The Open Sans Project Authors, under the SIL Open Font License 1.1 (`openalt_name_labels/fonts/OFL.txt`).
