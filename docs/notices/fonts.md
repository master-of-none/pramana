# Font notices

The web app bundles three typefaces so that IAST transliteration and Devanagari render the
same on every system, without fetching anything from the network. Vite copies the font
files into the built app (`src/pramana/static/assets/`), so they ship in the wheel.

| Typeface | Used for | Upstream copyright | Licence | Package |
| --- | --- | --- | --- | --- |
| Source Sans 3 | interface text | Adobe (Source type family) | SIL Open Font License 1.1 | `@fontsource-variable/source-sans-3` 5.3.1 |
| Source Serif 4 | answers, texts, headings | Adobe (Source type family) | SIL Open Font License 1.1 | `@fontsource-variable/source-serif-4` 5.3.1 |
| Noto Serif Devanagari | Devanagari (brand mark, glossary cards) | The Noto Project Authors | SIL Open Font License 1.1 | `@fontsource-variable/noto-serif-devanagari` 5.3.0 |

The full licence text is in each package's `LICENSE` file under `web/node_modules/`.
The Fontsource packages' licence files name "Google Inc." as distributor for the two
Source typefaces; their upstream copyright holder is Adobe.

Only the Latin, Latin Extended and Devanagari subsets are declared
([`web/src/styles/fonts.css`](../../web/src/styles/fonts.css)). Every IAST letter
(ā ī ū ṛ ṝ ḷ ṃ ḥ ṅ ñ ṭ ḍ ṇ ś ṣ, upper and lower case) and the older SBE circumflex
spellings (â î û ê ô) were checked glyph by glyph in the Latin subsets of both Source
faces on 1 November 2026. DM Sans and IBM Plex Sans were considered and rejected because
they lack the dot-below letters.

The app icons (`web/public/icons/`) were drawn from the Noto Serif Devanagari glyphs
प्र, rendered once in Chromium; `web/public/icon.svg` uses the reader's own Devanagari font.
