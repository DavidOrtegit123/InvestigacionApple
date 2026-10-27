# Many-page PDF test — Verdane GH-4 manual

`verdane_gh4_manual.pdf` (63 A5 pages, invented system, no PDF outline) is a
retrieval test: chapters 4–8 describe five modules with the same six sections
and different values. Expected pages are in `answer_key.json` (found in the
generated PDF itself). Rebuild and test:

```
uv run --with reportlab==5.1.0 --with pypdf==6.21.2 python3 build_manual.py
uv run --with reportlab==5.1.0 --with pypdf==6.21.2 python3 -m unittest test_manual
```

## On the phone

1. Run the latest build from Xcode.
2. Import `verdane_gh4_manual.pdf` and time the Save (from tapping Save until the
   material appears in the library).
3. Keep the document picker on **Best match (auto)** — an explicit pick bypasses
   retrieval.
4. Ask the 7 questions below, one per message, in this order, all on the same backend.
5. Export the transcript and send it.

## Questions

| # | Question (copy exactly) | Expected answer | Section | Page |
|---|---|---|---|---|
| Q1 | What is the timeout for the ventilation module's vent actuator? | 312 seconds | 5.3 Timeout settings | 24 |
| Q2 | Which error code means the CO2 valve is stuck open? | E-C17 | 8.6 Error codes | 50 |
| Q3 | How often should the irrigation flow sensor be calibrated? | Every 23 days | 4.5 Calibration | 18 |
| Q4 | What does a blinking amber LED on the control panel mean? | A firmware update is waiting for confirmation | 3.3 Status LEDs | 10 |
| Q5 | My plants get too much light late in the evening - which setting decides when the lamps turn off? | Dusk cutoff, default 21:40 | 6.2 Schedules | 30 |
| Q6 | How many sensors can one controller support? | 64 | 12.1 Technical specifications | 61 |
| Q7 | What is the warranty period? | Not stated in the manual | — | — |

Chat history is on in normal chat, so later questions can see earlier ones.
The questions don't depend on each other; if one looks affected by history,
note it.
