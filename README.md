# mandapanda — Mandarin Tone Contrast Drills

A single-page flashcard app for training Mandarin tone perception. Each card pairs a high-frequency monosyllabic word with a tone-minimal-pair contrast (same syllable, different tone) so you train the perceptual category — not just the word.

- **Study mode** — flip through 65 base/contrast pairs, see the character + pinyin + meaning, hear two native speakers pronounce each.
- **Test mode** — audio plays a randomly chosen word, you pick which of the two pair members you heard. 2-AFC tone discrimination, score tracked.

## Usage

The app is one HTML file with no build step:

```sh
python3 -m http.server 8765
# open http://localhost:8765/index.html
```

(Audio playback is more reliable over `http://` than `file://` in some browsers, hence the local server.)

### Keyboard shortcuts

| Key | Study mode | Test mode |
|-----|------------|-----------|
| ← / → | prev / next card | — / next question |
| 1 / 2 | play speaker 1 / 2 | pick choice 1 / 2 |
| b / c | base / contrast side | — |
| r | — | replay audio |

## Adding or swapping words

The full word list lives in [50_words.md](50_words.md) and the runtime data in the `PAIRS` array in [build.py](build.py). To change the deck:

1. Edit `PAIRS` in [build.py](build.py).
2. Run `python3 build.py` — it resolves each `(syllable, tone, speaker)` to a Tone Perfect item ID, downloads any missing MP3s into `audio/`, and rewrites the `flashcardData` block in [index.html](index.html) in place.

The script is idempotent: existing audio files are skipped on re-runs.

## Attribution

All audio is sourced from MSU Libraries' **Tone Perfect** database:

> Catherine Ryu, Mandarin Tone Perception & Production Team, and Michigan State University Libraries. *Tone Perfect: Multimodal Database for Mandarin Chinese.* Accessed 7 May 2026. https://tone.lib.msu.edu/

Tone Perfect is a free, open-access corpus of 9,840 audio recordings covering all 410 standard Mandarin syllables × 4 tones × 6 native speakers (3 female, 3 male). This project uses two voices (Female Voice 1 and Male Voice 1).

The maintainers ask that users [request access via their form](https://tone.lib.msu.edu/) and cite the corpus when redistributing. If you use this project, cite Tone Perfect — not this repo.

## Project layout

```
mandapanda/
├── index.html       # the app (HTML + CSS + JS + flashcardData inline)
├── 50_words.md      # human-readable word list with pairs
├── build.py         # word list source-of-truth + audio fetcher + index.html patcher
├── audio/           # 258 MP3s (FV1 + MV1 for each of 129 unique syllable-tone combos)
└── README.md
```

## Why tone contrasts

For learners coming from a non-tonal L1 (English, French, etc.), the bottleneck isn't memorizing a word's tone — it's *hearing* the tone at all. Pairing each word with its tone-minimal partner (我 wǒ ↔ 卧 wò, 买 mǎi ↔ 卖 mài) forces the perceptual contrast that's invisible when words are studied in isolation. Two-alternative forced-choice testing on those pairs is one of the better-supported drills in L2 phonology research.
