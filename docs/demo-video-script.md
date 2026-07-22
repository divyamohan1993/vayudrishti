# VayuDrishti demo video script (3 minutes)

Target length 3:00. Screen recording with voiceover. Lead with the Intervention
Ledger, because the argument is won or lost in the first 30 seconds. Every number
on screen is real or a clearly labeled modeled estimate. Fill the bracketed
figures from `receipts.json`, `interventions.json`, and `ledger.json` at
integration; never read a placeholder aloud.

Tone: calm, precise, confident. No hype. Let the receipts do the persuading.

---

## Beat 1: The Intervention Ledger (0:00 to 0:30)

**Screen**: open directly on the Ledger page for Delhi. A stage timeline runs
across the top with GRAP Stage II, III, IV marked. A ribbon shows raw PM2.5
against the weather-normalized line. A ward map is shaded by measured effect. Two
big counters read avoided exposure and avoided deaths, each with a confidence
interval.

**Voice**: "Every winter Delhi declares a pollution emergency and shuts parts of
the city down. Did it work? This is the first system that answers that, ward by
ward, with the weather stripped out. GRAP Stage III saved an estimated [N] lives
in northwest Delhi. The dotted line is what the air would have done on weather
alone, so this is the policy, not the rain."

**On action**: drag the timing slider back two days. The counters move.

**Voice**: "Acting 48 hours earlier would have saved [M] more. Modeled estimate,
confidence interval shown, every date linked to the actual government order. A
reasoning agent turns this into an action brief for the ward, every line cited
back to the measured signal behind it."

## Beat 2: Receipts (0:30 to 1:00)

**Screen**: click through to `/receipts`. Show the forecast skill table and the
GRAP effect table with a placebo pass or fail per stage.

**Voice**: "Nothing here is a vibe. The 24 hour forecast beats persistence by [X]
percent on a rolling-origin backtest, with the embargo stated. Every estimate is
four independent methods combined, and we publish where they disagree. And we
validate against a network we never trained on: the US embassy monitors, held out
completely. Each GRAP stage carries a placebo test, so a lucky week cannot pose as
a policy win, and the watchdog flags the probability the next stage crosses in 48
hours, next to what that stage was measured to save."

**On action**: hover a number to show its method note and source.

## Beat 3: Replay, offline (1:00 to 1:40)

**Screen**: open the November 2025 replay. Scrub the timeline through a severe
episode. Turn off the network in the browser dev tools; the replay keeps playing.

**Voice**: "This is the November 2025 episode, replayed from out-of-fold
predictions only, so the model is scoring days it never trained on. A judge always
asks, did you train on the replay? No. The embargo and the out-of-fold design are
in the receipts. And it runs with the network off, so a bad connection on finale
day cannot break the demo."

## Beat 4: Add a city with one file (1:40 to 2:20)

**Screen**: split view. On the left, the Bengaluru command center already live. On
the right, the editor showing `config/cities/bengaluru.yaml`.

**Voice**: "Scaling to a new city is not a rewrite. It is one config file: the
bounding box, the ward source, the station matches, the languages. The pipeline
runs, the JSON publishes, the map works. Delhi is the deep build with the full
Ledger. Bengaluru came from this single file."

**On action**: highlight the YAML fields, then the matching live city on the left.

## Beat 5: It knows where you are, and keeps it (2:20 to 2:50)

**Screen**: open the site fresh in a private window. The browser asks for location.
Accept. The nearest supported city opens. Open the network tab and show it is
clean.

**Voice**: "Open it on your phone and it finds your nearest city automatically.
The location match runs on your device. Look at the network tab: your coordinates
never leave the browser. Deny permission and the city picker is right there."

## Close (2:50 to 3:00)

**Screen**: return to the Ledger with the lives-saved counter in view. Show the
live URL.

**Voice**: "VayuDrishti. Air quality intelligence for every Indian city, on open
data, with a receipt behind every number. Try it at [live URL]."

---

## Shot list and assets

- Ledger page with real Delhi GRAP 2025-26 data (or labeled fixture until integration).
- An agent-generated action brief for a priority ward, each line showing its citation.
- `/receipts` with the forecast and GRAP effect tables, the embassy-network validation panel, the ensemble method table, and the reliability diagram populated.
- The GRAP trigger watchdog panel showing a stage-crossing probability next to its ledger effect.
- November 2025 replay cached for offline playback.
- `config/cities/bengaluru.yaml` open in an editor with syntax highlighting.
- A clean browser profile for the geolocation grant, and the dev tools network tab visible.

## Recording notes

- 1080p minimum, 60 fps for the slider and scrub moments.
- Keep the cursor deliberate; pause on each number long enough to read.
- Captions on for accessibility, matching the voiceover word for word.
- No background music under the receipts section; let the claims stand.
