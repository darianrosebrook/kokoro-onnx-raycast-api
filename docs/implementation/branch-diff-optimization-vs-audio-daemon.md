# Branch Diff: optimization-implementation vs feature/audio-daemon-integration

Generated: 2025-08-08T17:00:52Z

## origin/feature/audio-daemon-integration..optimization-implementation

### Name-Status
M	.kokoro-root
M	api/config.py
M	api/performance/stats.py
M	api/tts/core.py
M	api/tts/misaki_processing.py
M	api/tts/text_processing.py
D	api/tts/text_processing/__init__.py
D	api/tts/text_processing/config.py
D	api/tts/text_processing/core/__init__.py
D	api/tts/text_processing/core/base.py
D	api/tts/text_processing/core/exceptions.py
D	api/tts/text_processing/core/pipeline.py
D	api/tts/text_processing/normalization/__init__.py
D	api/tts/text_processing/normalization/abbreviation_normalizer.py
D	api/tts/text_processing/normalization/base_normalizer.py
D	api/tts/text_processing/normalization/number_normalizer.py
D	api/tts/text_processing/normalization/text_normalizer.py
D	api/tts/text_processing/types.py
A	docs/implementation/line-break-phonemizer-fix.md
A	docs/implementation/misaki-integration-fixes.md
A	docs/implementation/phoneme-truncation-fix.md
A	docs/implementation/ttfa-optimization-results.md
M	raycast/src/utils/tts/streaming/audio-playback-daemon.ts
A	scripts/debug_misaki_result.py
A	scripts/debug_phonemizer_mismatch.py
A	scripts/test_long_text_tts.py
A	scripts/test_misaki_fixes.py
A	scripts/test_misaki_g2p.py
A	scripts/test_misaki_simple.py
A	scripts/test_washing_instructions_tts.py
A	scripts/verify_washing_fix.py
M	start_development.sh

### Stat
 .kokoro-root                                       |   6 +-
 api/config.py                                      |   5 +
 api/performance/stats.py                           | 114 +++++-
 api/tts/core.py                                    | 168 ++++++--
 api/tts/misaki_processing.py                       | 275 ++++++++-----
 api/tts/text_processing.py                         | 291 ++++++++++---
 api/tts/text_processing/__init__.py                | 439 --------------------
 api/tts/text_processing/config.py                  | 332 ---------------
 api/tts/text_processing/core/__init__.py           |  20 -
 api/tts/text_processing/core/base.py               | 408 -------------------
 api/tts/text_processing/core/exceptions.py         |  62 ---
 api/tts/text_processing/core/pipeline.py           | 341 ----------------
 api/tts/text_processing/normalization/__init__.py  |  13 -
 .../normalization/abbreviation_normalizer.py       | 276 -------------
 .../normalization/base_normalizer.py               | 260 ------------
 .../normalization/number_normalizer.py             | 453 ---------------------
 .../normalization/text_normalizer.py               | 300 --------------
 api/tts/text_processing/types.py                   |  85 ----
 docs/implementation/line-break-phonemizer-fix.md   |  90 ++++
 docs/implementation/misaki-integration-fixes.md    | 190 +++++++++
 docs/implementation/phoneme-truncation-fix.md      |  81 ++++
 docs/implementation/ttfa-optimization-results.md   | 182 +++++++++
 .../utils/tts/streaming/audio-playback-daemon.ts   | 330 +++++++++------
 scripts/debug_misaki_result.py                     |  70 ++++
 scripts/debug_phonemizer_mismatch.py               | 211 ++++++++++
 scripts/test_long_text_tts.py                      | 105 +++++
 scripts/test_misaki_fixes.py                       | 239 +++++++++++
 scripts/test_misaki_g2p.py                         | 170 ++++++++
 scripts/test_misaki_simple.py                      | 104 +++++
 scripts/test_washing_instructions_tts.py           | 127 ++++++
 scripts/verify_washing_fix.py                      | 155 +++++++
 start_development.sh                               | 120 +-----
 32 files changed, 2604 insertions(+), 3418 deletions(-)


## optimization-implementation..origin/feature/audio-daemon-integration

### Name-Status
M	.kokoro-root
M	api/config.py
M	api/performance/stats.py
M	api/tts/core.py
M	api/tts/misaki_processing.py
M	api/tts/text_processing.py
A	api/tts/text_processing/__init__.py
A	api/tts/text_processing/config.py
A	api/tts/text_processing/core/__init__.py
A	api/tts/text_processing/core/base.py
A	api/tts/text_processing/core/exceptions.py
A	api/tts/text_processing/core/pipeline.py
A	api/tts/text_processing/normalization/__init__.py
A	api/tts/text_processing/normalization/abbreviation_normalizer.py
A	api/tts/text_processing/normalization/base_normalizer.py
A	api/tts/text_processing/normalization/number_normalizer.py
A	api/tts/text_processing/normalization/text_normalizer.py
A	api/tts/text_processing/types.py
D	docs/implementation/line-break-phonemizer-fix.md
D	docs/implementation/misaki-integration-fixes.md
D	docs/implementation/phoneme-truncation-fix.md
D	docs/implementation/ttfa-optimization-results.md
M	raycast/src/utils/tts/streaming/audio-playback-daemon.ts
D	scripts/debug_misaki_result.py
D	scripts/debug_phonemizer_mismatch.py
D	scripts/test_long_text_tts.py
D	scripts/test_misaki_fixes.py
D	scripts/test_misaki_g2p.py
D	scripts/test_misaki_simple.py
D	scripts/test_washing_instructions_tts.py
D	scripts/verify_washing_fix.py
M	start_development.sh

### Stat
 .kokoro-root                                       |   6 +-
 api/config.py                                      |   5 -
 api/performance/stats.py                           | 114 +-----
 api/tts/core.py                                    | 168 ++------
 api/tts/misaki_processing.py                       | 275 +++++--------
 api/tts/text_processing.py                         | 291 +++----------
 api/tts/text_processing/__init__.py                | 439 ++++++++++++++++++++
 api/tts/text_processing/config.py                  | 332 +++++++++++++++
 api/tts/text_processing/core/__init__.py           |  20 +
 api/tts/text_processing/core/base.py               | 408 +++++++++++++++++++
 api/tts/text_processing/core/exceptions.py         |  62 +++
 api/tts/text_processing/core/pipeline.py           | 341 ++++++++++++++++
 api/tts/text_processing/normalization/__init__.py  |  13 +
 .../normalization/abbreviation_normalizer.py       | 276 +++++++++++++
 .../normalization/base_normalizer.py               | 260 ++++++++++++
 .../normalization/number_normalizer.py             | 453 +++++++++++++++++++++
 .../normalization/text_normalizer.py               | 300 ++++++++++++++
 api/tts/text_processing/types.py                   |  85 ++++
 docs/implementation/line-break-phonemizer-fix.md   |  90 ----
 docs/implementation/misaki-integration-fixes.md    | 190 ---------
 docs/implementation/phoneme-truncation-fix.md      |  81 ----
 docs/implementation/ttfa-optimization-results.md   | 182 ---------
 .../utils/tts/streaming/audio-playback-daemon.ts   | 330 ++++++---------
 scripts/debug_misaki_result.py                     |  70 ----
 scripts/debug_phonemizer_mismatch.py               | 211 ----------
 scripts/test_long_text_tts.py                      | 105 -----
 scripts/test_misaki_fixes.py                       | 239 -----------
 scripts/test_misaki_g2p.py                         | 170 --------
 scripts/test_misaki_simple.py                      | 104 -----
 scripts/test_washing_instructions_tts.py           | 127 ------
 scripts/verify_washing_fix.py                      | 155 -------
 start_development.sh                               | 120 +++++-
 32 files changed, 3418 insertions(+), 2604 deletions(-)
