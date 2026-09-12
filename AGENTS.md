# AGENTS.md — Smart Solutions course repo

This repo belongs to a 3-student team working through the "Smart Solutions"
(Nutikad Lahendused) programming labs. One repo covers the whole course;
each lab gets its own folder under `smart-solutions/labN/`.

## What this course is building toward

Same team, same MG400 robot, same AtomS3 (ESP32) as the other two courses
running in parallel (Data Acquisition & 3D Printing/CAD) — one shared demo
across all three: **press a key on the AtomS3, the robot draws that
letter.** This course's contribution is the "station" (the laptop running
Python): it drives the MG400 over its TCP/IP API (ports 29999/30003/30004),
serves a Flask web UI for jogging/teaching positions and pump control, and
receives the letter chosen on the AtomS3 to turn it into a drawn path. The
Atom firmware itself (image display, captive portal, settings/test page)
also lives here.

- Data Acquisition course repo builds the pressure-sensing/pump-control
  logic and the Atom button → letter selection. See `data-acquisition-course`.
- 3D Printing/CAD course repo builds the pen holder that mounts on the
  robot's flange. See `3d-printing-course`.

## Repo layout

```
smart-solutions/
  lab1/
    README.md    <- official Estonian assignment, copied verbatim, filled in as work happens (KAARDISTA ISE sections)
    src/         <- station code: MG400 base-package setup/overrides, letter channel, letter->path logic
    firmware/    <- AtomS3 PlatformIO project (ESP32-Image-Server based: WiFi AP, captive portal, settings/test page)
    data/        <- positions.json (taught robot positions), latency/pick-test CSV logs
    docs/        <- atom_page.md, letters.md, letter_channel.md, bom.md, pick_test.csv, latency.csv, photos, draw.io diagram
study-ru/
  lab1-translation.md   <- personal Russian translation, NOT part of the graded submission
```

Each later lab under `smart-solutions/labN/` follows the same pattern.

## Conventions

- **Language:** assignments are issued in Estonian. `README.md` in each lab
  folder stays in Estonian (official template, `KAARDISTA ISE` = "map it
  yourself" fill-in-the-blank sections) — filled in as the student measures
  things. Personal Russian translations live only under `study-ru/`, never
  touching the graded files.
- **Nothing gets deleted.** A wrong measurement stays in the doc with its
  date; the correction goes underneath it, not over it.
- **Devlog entries** live inside each lab's `README.md` under
  "Arenduspäevik" — one entry per work session, appended (not edited later).
- Diagrams/simulations go into the doc as an image + a link to the live,
  editable file (draw.io link).
- Git tag per lab on submission, e.g. `smart-solutions-lab1`.

## Tools in play

- Laptop with Ethernet port/adapter; Python 3.11+, venv, pip, Flask.
- MG400 base package: https://github.com/KKallas/mg400-base
- AtomS3 (ESP32), USB-C cable; VS Code + PlatformIO extension; M5Unified.
- ESP32-Image-Server as the firmware starting point:
  https://github.com/KKallas/ESP32-Image-Server
- Phone (to join the Atom's WiFi network and test the captive portal).
- draw.io (system diagrams).

## Safety notes (for anyone, human or agent, drafting instructions)

- MG400 reach is 440 mm; nobody's hands in that area while a command is
  pending. Someone says "moving" before every run.
- The only trusted stop is the physical e-stop on the robot base; the
  on-page stop button is a convenience only.
- First run of any new sequence goes at 20% speed, pen/suction cup 20 mm
  above the surface, no test piece.
- Only one program sends motion commands to the robot at a time.
- Pump box is 24V; DO lines get connected only with the robot disabled and
  the box unpowered.
- Change the Atom's WiFi password away from the default before it leaves
  the lab.

## For an AI agent picking up work here

- Check the current lab's `README.md` first — live goals, checklist, and
  devlog are there; don't duplicate what's already answered.
- This is coursework: the student does the actual measurements/design work
  themselves. Help with translation, explaining concepts, repo/tool setup —
  don't produce the graded numbers, address plans, or devlog entries for
  them.
- If asked to translate assignment text, translate faithfully; don't
  editorialize instructor requirements.
