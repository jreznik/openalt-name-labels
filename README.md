# openalt-name-labels

Prints name labels for OpenAlt conference badges on a **Bixolon XD5-40d** label printer, from **macOS or Linux**.

- **Names from anywhere:** the command line, a text file, a CSV, a Pretalx export, or the Pretalx API.
- **Same look as the original badges:** **Open Sans Bold 29.89 pt**, first name on line 1 and surname on line 2. A name only shrinks if it's too wide for the label.
- **Any language:** accents and other non-English letters (Řezník, Ødegård, Łukasiewicz) always print correctly. The font is bundled, so labels look the same on every computer.

---

## Hardware

| | |
|---|---|
| **Printer** | Bixolon **XD5-40d**: desktop direct thermal label printer, 203 dpi (8 dots/mm), 104 mm print head, USB. Supports ZPL II, EPL and SLCS. Shows up in CUPS as `usb://BIXOLON/XD5-40d?serial=…`. |
| **Labels** | **70 × 30 mm** white **direct thermal** labels on a roll, separated by a gap. No ribbon is needed: the "d" model has no ribbon, and the heat darkens the label paper itself. |
| **Connection** | USB cable to a Mac or Linux PC. No Bixolon driver is needed. |

**Other models:** the XD5-40**t** (thermal transfer, needs a ribbon) works the same way. The 300 dpi XD5-43d/t also works with `--dpi 300`.

**Other label sizes:** set `--width`/`--height`. The tool centres the label on the 104 mm head because label rolls sit centred between the printer's guides.

**Paper:** direct thermal labels fade over months and with heat or sunlight. That's fine for a conference, but not for archival use.

---

## Installation

### 1. Prerequisites

| | macOS | Linux |
|---|---|---|
| Python 3.10+ | `brew install python` (if `python3 -V` is too old) | `sudo apt install python3 python3-venv` or `sudo dnf install python3` |
| CUPS (printing system) | built in | `sudo apt install cups` or `sudo dnf install cups`, then `sudo systemctl enable --now cups` |

### 2. Plug in the printer and run setup

Connect the printer over USB, switch it on, load the labels, then run:

```sh
git clone <this repo> openalt-name-labels   # or copy the folder
cd openalt-name-labels
./setup.sh
```

`setup.sh` does two things:
1. Creates a private Python environment in `.venv/` and installs the tool there.
2. Finds the printer on USB and adds it to CUPS as a printer named **`XD5`**.

It asks for your password (sudo) only if it has to. That's usually on Linux; on macOS an admin account doesn't need it.

| setup option | meaning |
|---|---|
| `--no-printer` | only install the tool, e.g. to make previews without a printer |
| `--queue NAME` | name the printer something other than `XD5` |
| `--uri usb://…` | use this printer address instead of auto-detecting it (`lpinfo -v` lists addresses) |

**Optional:** to run the tool as plain `openalt-name-labels` from anywhere:
```sh
ln -s "$PWD/.venv/bin/openalt-name-labels" ~/.local/bin/        # Linux (~/.local/bin should be on PATH)
ln -s "$PWD/.venv/bin/openalt-name-labels" /opt/homebrew/bin/   # macOS with Homebrew
```
The examples below use `.venv/bin/openalt-name-labels`.

### 3. Calibrate the labels (once per roll type)

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

Before printing, the tool lists the names and asks for confirmation. Add `-y` to skip the question.

```sh
L=.venv/bin/openalt-name-labels

# Names on the command line
$L "Jaroslav Řezník" "Anna Jungmannová"

# A file: .txt (one name per line, # for comments), .csv or .json
$L -f names.txt
$L -f openalt-2026_speakers.csv          # finds a "Name" / "Jméno" column automatically
$L -f speakers.csv --column "Full name"  # or name the column yourself
some-command | $L -f -                   # read names from stdin

# Pretalx exports: speakers CSV/JSON, or the public schedule.json
$L -f schedule.json

# Pretalx API: speakers of confirmed and accepted talks (not rejected or withdrawn ones),
# using the URL, event and token from openalt-name-labels.toml (see "Pretalx configuration")
$L --pretalx --preview out/
$L --pretalx
$L --pretalx --pretalx-state confirmed     # confirmed talks only
$L --pretalx-event other-event             # a different event than the config's
```

You can combine sources: `$L -f speakers.csv "Extra Guest"`.

**Before anything is sent, the tool checks:**
- **Duplicates:** repeated names (ignoring upper/lower case) are printed once, and the skipped ones are listed. Use `--keep-duplicates` to print every repeat, e.g. three "Bezejmenný přednášející" placeholder badges.
- **Missing characters:** if the font can't draw a character, such as Chinese, Arabic or emoji, the tool refuses to print that name rather than print it with the character silently missing. Fix the name, use `--font` with a font that has the characters, or pass `--force`.
- **Printer state:** if the `XD5` printer is missing, disabled or rejecting jobs, the tool stops and tells you how to fix it.

**Text clean-up:** accents that arrive as separate characters are joined back to their letters (Unicode NFC), so "Jiří" never prints as "Jiř̌", and invisible characters are removed. CSV/TXT files that aren't UTF-8 are read as Windows-1250, the usual encoding of Czech Excel exports, with a warning.

**After sending,** the tool waits until CUPS has passed every label to the printer and shows printer messages such as "Waiting for printer to become available". Skip the wait with `--no-wait`.

### On the conference day

- **Install beforehand:** run `./setup.sh` before the event, because it needs internet access to install the dependencies. Printing itself works offline, except `--pretalx-event`.
- **Preview first:** run once with `--preview out/` and look through the PNGs.
- **Printed labels are numbered** in the listing. If the printer jams or runs out of labels partway through, fix it, then resume with `--start N`, where N is the first label that didn't print. To reprint single badges, just give the names: `$L "Jiří Rak"`.
- **Extra copies:** use `--copies N`.

### Pretalx configuration

The Pretalx URL, event and **API token** live in **`openalt-name-labels.toml`** in the project folder. `setup.sh` creates it from [`openalt-name-labels.example.toml`](openalt-name-labels.example.toml):

```toml
[pretalx]
url = "https://pretalx.com"      # your Pretalx instance
event = "openalt-2026"           # event slug from the URL
token = "…"                      # Pretalx → your user menu → API → token
states = ["confirmed", "accepted"]
```

**Keeping the token private:**
- **Git-ignored:** the file is never added to git, so it isn't pushed to GitHub.
- **Pre-commit hook:** `setup.sh` turns on `.githooks/pre-commit`, which blocks a commit that adds this file (even with `git add -f`) or anything that looks like a token in another file. On a fresh clone, run `./setup.sh` before committing.
- **Readable only by you:** the file is created with `chmod 600`, and the tool warns if other users can read it.
- **Not on the command line:** the token is never taken as a command-line option, which would put it in shell history and the process list. It's also never printed.
- **Without a token:** only public data is available, meaning confirmed talks in the published schedule.

The tool looks for the config file in this order:
1. `--config FILE`
2. the `$OPENALT_LABELS_CONFIG` environment variable
3. `./openalt-name-labels.toml` in the current folder
4. `openalt-name-labels.toml` next to `setup.sh`
5. `~/.config/openalt-name-labels/config.toml`

The environment variables `PRETALX_URL` and `PRETALX_TOKEN`, and the options `--pretalx-url`, `--pretalx-event` and `--pretalx-state`, override the file. That's handy for a one-off run.

### Check before printing

```sh
$L -f speakers.csv --preview out/        # one PNG per label, nothing printed
$L -f speakers.csv --output out/all.zpl  # save the printer data to a file instead of printing
```

### Options

| option | default | description |
|---|---|---|
| `--width`, `--height` | 70, 30 mm | label size (env `BADGE_WIDTH_MM`, `BADGE_HEIGHT_MM`) |
| `--offset-x` | centred on the 104 mm head | label's left edge from the head's left edge, in mm (env `BADGE_OFFSET_X_MM`) |
| `--margin` | 3 mm | blank border; a name shrinks if it would cross it |
| `--font-size` | 29.8879 pt | type size from the original badges |
| `--line-spacing` | 36.851 pt | distance from the first-name line to the surname line |
| `--fit` | off | ignore `--font-size` and make every name as large as fits |
| `--max-font` | none | with `--fit`, cap the text height in mm |
| `--font` | Open Sans Bold (bundled) | any TTF/OTF file |
| `--dpi` | 203 | use 300 for the XD5-43 |
| `-P`, `--printer` | `XD5` | printer name in CUPS (env `BADGE_PRINTER`) |
| `--copies` | 1 | labels per name |
| `--darkness` | printer setting | 0–30 |
| `--speed` | printer setting | inches per second |
| `--list-printers` | | show the printers set up in CUPS |
| `--grid` | | print the mm ruler grid |
| `--start N` | 1 | start at the N-th name, e.g. to resume after a jam |
| `--keep-duplicates` | off | print repeated names every time |
| `--pretalx` | | fetch speakers from Pretalx using the config file |
| `--pretalx-event`, `--pretalx-url` | config file | override the config's event or URL |
| `--pretalx-state` | config, else `confirmed,accepted` | which talk states get speaker labels |
| `--config FILE` | see above | use this config file |
| `--force` | off | print names even if the font lacks some of their characters |
| `--no-wait` | off | don't wait for CUPS to finish the job |
| `-y`, `--yes` | | print without asking |

---

## Troubleshooting

| problem | fix |
|---|---|
| `setup.sh`: no `usb://BIXOLON` device found | Check the cable and power. Run `lpinfo -v` (on Linux maybe `sudo lpinfo -v`) and pass the address with `--uri`. |
| macOS: "Raw queues are no longer supported" | Expected. `setup.sh` avoids it by using the bundled `cups/xd5-raw.ppd` instead. The warning "Printer drivers are deprecated" is harmless. |
| Linux: `lpadmin: Forbidden` | Run with sudo, or join the admin group: `sudo usermod -aG lpadmin $USER` (Debian/Ubuntu) or `sudo usermod -aG sys $USER` (Fedora). |
| Text cut off or off-centre | Print `--grid` and check the label edges. Then adjust `--width`, `--height` or `--offset-x`. |
| Print runs over two labels, or the printer feeds without stopping | Calibrate (step 3 above). |
| Too faint | Use `--darkness 20` or higher. |
| "job … is still queued" | The printer is off, unplugged or out of labels. Fix it and the job continues by itself: `setup.sh` sets the queue to retry instead of stopping. `lpstat -p XD5` shows the state, and `cancel -a XD5` drops all jobs. |
| "queue 'XD5' is disabled" | Run `cupsenable XD5 && cupsaccept XD5`. This happens with queues created without `setup.sh`, which stop after any error. |
| Linux: `setup.sh` finds no printer, but `lsusb` shows it | Unplug and replug the printer. If `ipp-usb` is installed and has claimed the device, stop it: `sudo systemctl stop ipp-usb`. |

## How it works

1. Each name is drawn as a black-and-white image (Pillow), using the bundled Open Sans Bold.
2. The image is converted to the printer's ZPL language (`^GFA`).
3. It is sent to CUPS with `lp -o raw`, and the printer's own ZPL interpreter prints it.

The print-area width is always set to the full 104 mm head, and the label's position is set explicitly. The XD5 centres any narrower print area on the head, which would shift the label sideways.

Main files: `openalt_name_labels/` (`sources.py` input, `config.py`, `render.py` layout, `zpl.py`, `printer.py`), `cups/xd5-raw.ppd`, `setup.sh`, `.githooks/pre-commit`.

Run the tests with `.venv/bin/pip install -e '.[dev]' && .venv/bin/pytest`.

## License

[MIT](LICENSE) © 2026 Jaroslav Řezník <jaroslav.reznik@openalt.org>, OpenAlt.

The bundled Open Sans font is © The Open Sans Project Authors, under the SIL Open Font License 1.1 (`openalt_name_labels/fonts/OFL.txt`).
