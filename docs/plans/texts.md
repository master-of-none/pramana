# Texts to add: candidates and priority

A working list for growing the library. **Nothing here is verified yet:** before any
import, confirm the edition's public-domain status (and where it holds), find a complete
scan or text, and record both in the [source notices](../notices/sources.md). Dates are
first publication as best known; treat them as leads, not facts.

How each entry is judged:

- **Value:** how much it adds for studying Advaita (a gap filled, a comparison enabled).
- **Route:** *HTML* (an existing adapter can read it, low effort), *text* (a single
  pinned file), *OCR* (a scan, read locally with Chandra or Tesseract: high effort,
  needs a GPU for Chandra and an accuracy check).
- **Size:** large works may crowd retrieval and become opt-in, like the Yoga Vāsiṣṭha.

## Recommended order

Checked by web search on 23 October 2026 (catalogue records and archive.org; rights still
to confirm per scan). Texts with a scan found come first, since they can be OCRed now.

| # | Text | Translation | What the search found | Route |
| ---: | --- | --- | --- | --- |
| 1 | **Śaṅkara's Upaniṣad commentaries**, vol. 1: Īśa, Kena, Muṇḍaka | S. Sitarama Sastri, Madras, 1898 (5-volume series, 1898–1901) | Two archive.org scans: [Toronto copy](https://archive.org/details/upanishadssrisan00sita) (a 1905 reprint of the Madras edition) and [Digital Library of India copy](https://archive.org/details/in.ernet.dli.2015.283832) (1898, G. A. Natesan); later volumes include Kaṭha and Praśna. A [HathiTrust record](https://catalog.hathitrust.org/Record/100580124) of the series lists the Māṇḍūkya too: check, it may close gap #2 | OCR |
| 2 | **Māṇḍūkya Upaniṣad with Gauḍapāda's Kārikā** (and Śaṅkara's commentary) | Manilal N. Dvivedi, Bombay, 1894; 2nd ed. 1909 | The editions are confirmed ([reviewed in *The Monist*, 1894](https://dc2.philarchive.org/s/Manilal%20N.%20Dvivedi)); no scan found yet. The largest gap in the library | OCR, once a scan is found |
| 3 | **Madhva's Brahma Sūtra commentary** | S. Subba Rau, Madras, Minerva Press, 1904 | [archive.org scan](https://archive.org/details/vs-mct-ssr-ao) (Community Texts) and a [NEHU repository copy](https://dspace.nehu.ac.in/handle/1/13464). A third voice beside Śaṅkara and Rāmānuja | OCR |
| 4 | **Bhagavad Gītā with Rāmānuja's commentary** | A. Govindacharya, Madras, Vaijayanti Press, 1898 | [Edition confirmed](https://relbib.de/Record/332545857); no scan found yet. Would give Śaṅkara vs Rāmānuja on the Gītā | OCR, once a scan is found |
| 5 | **Pañcadaśī** of Vidyāraṇya | M. Srinivasa Rau and K. A. Krishnaswami Aiyar, Srirangam, Sri Vani Vilas Press, 1912 (629 pp.) | [Catalogue record](https://tamildigitallibrary.in/Marc-Articles/நூல்-58716-Panchadasi%20of%20Vidyaranya-with%20English%20translation,%20Explanatory%20notes%20and%20summary%20of%20each%20chapter); no scan found yet | OCR, once a scan is found |

## Advaita prakaraṇas and manuals

| Text | Translation (to verify) | Notes |
| --- | --- | --- |
| Vedāntasāra of Sadānanda | G. A. Jacob, 1881 (*A Manual of Hindu Pantheism*) | Short standard primer; OCR |
| Upadeśasāhasrī of Śaṅkara | find a pre-1929 translation | Later translations (1940s) are likely still in copyright |
| Vedānta Paribhāṣā | Arthur Venis, 1880s (in *The Pandit*) | Advaita epistemology (*pramāṇas*): fits the app's name |
| Dṛg-Dṛśya-Viveka | find a public-domain translation | Short; seer and seen |
| Avadhūta Gītā | find a public-domain translation | Non-dual song; check edition |
| Swami Vivekananda, *Jñāna Yoga* lectures | early 1900s editions | Modern exposition; check which volumes are public domain |

## Comparative commentaries

| Text | Translation (to verify) | Notes |
| --- | --- | --- |
| Gītā with Śaṅkara's commentary (public edition) | Alladi Mahadeva Sastry, 1897 | Already importable as a private PDF; a public scan would make it shareable |
| Brahma Sūtra, Nimbārka or Vallabha | check availability | Further comparison voices; lower priority |

## The Vedas (saṃhitās)

All four exist in public-domain English, mostly by Ralph Griffith, as HTML on Sacred
Texts: the existing adapter can read them, so the route is *HTML*. Together about 5–6
million characters, so likely **opt-in** with their own scope.

| Veda | Translation (to verify) | Notes |
| --- | --- | --- |
| Ṛg Veda | Griffith, 1896 | Start here: Śaṅkara and Rāmānuja cite it ("Ri. Samh.", 9 references); Nāsadīya (X.129), Puruṣa Sūkta (X.90) |
| Sāma Veda | Griffith, 1895 | Small |
| Yajur Veda | Griffith (White), 1899; A. B. Keith (Black, *Taittirīya Saṃhitā*), 1914 | Keith's is cited by the commentaries ("Taitt. Samh.", 13 references) |
| Atharva Veda | Griffith, 1895–96 | Large |

Their value for Advaita is mostly indirect: the Upaniṣads, the Vedas' philosophical
part, are already in the library.

## Large or lower priority

| Text | Translation (to verify) | Notes |
| --- | --- | --- |
| Mahābhārata | K. M. Ganguli, 1883–96 (Sacred Texts HTML) | Very large; would need opt-in; contains the Gītā and Mokṣadharma |
| Rāmāyaṇa | Griffith, 1870–74 (verse) | Large; little Advaita content |
| Bhāgavata Purāṇa | find a complete public-domain English translation | Important devotionally; completeness uncertain |

## Not planned

- **Works still in copyright**, such as most 20th-century translations by the Ramakrishna
  Order and Ramana Maharshi's ashram: only with permission.
- **Sanskrit originals** (for example from GRETIL): wanted for a future Sanskrit layer,
  but each file's licence must be checked, and verse alignment needs printed numbers.

## Adding one

The steps for an accepted text are in the [architecture guide](../reference/architecture.md#extending-pramana):
pin the source, write or reuse an adapter, add the notice, import, index, and re-run the
benchmarks to see whether it crowds retrieval.
