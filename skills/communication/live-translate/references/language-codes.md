# Language Codes — BCP-47 Quick Reference

Deep-dive loaded on demand by the `live-translate` skill (and reusable by
`read-and-translate-sign` and `caption-conversation`). The `translator` and
`live_caption` widgets expect BCP-47 tags in `source_lang` / `target_lang` /
`language`.

## Common tags

| Language | Tag | Notes |
| -------- | --- | ----- |
| English | `en` (`en-US`, `en-GB`) | Default UI/captions for `en-*` locales. |
| Spanish | `es` (`es-ES`, `es-MX`) | |
| French | `fr` | |
| German | `de` | |
| Italian | `it` | |
| Portuguese | `pt` (`pt-BR`) | |
| Japanese | `ja` | No spaces; segment for caption wrapping. |
| Korean | `ko` | |
| Chinese (Simplified) | `zh-Hans` | Prefer script subtags over `zh-CN`. |
| Chinese (Traditional) | `zh-Hant` | |
| Arabic | `ar` | **RTL** — see below. |
| Hebrew | `he` | **RTL**. |
| Hindi | `hi` | |
| Russian | `ru` | |

## Conventions

- **`auto`** is accepted for `source_lang` to request detection; resolve it to a
  concrete tag once detected and update the widget so the UI can label it.
- Prefer **language + script** subtags (`zh-Hans`) over region (`zh-CN`) when the
  script matters; otherwise the bare language (`fr`) is fine.
- Match the user's `locale` from `client.hello` for the default `target_lang`.

## RTL (right-to-left)

`ar`, `he`, `fa`, `ur` render right-to-left. Set the caption/translator text
direction accordingly; keep punctuation and digits in logical order and let the
client handle bidi shaping.

## Detection confidence

- If detection confidence is low, keep `source_lang:"auto"` and hedge in speech
  ("sounds like Portuguese — translating to English").
- Numbers, proper nouns, gate/room codes, and currency should pass through
  **verbatim**, not be "translated".

## Speaker tagging (with `live_caption`)

When combining translation with captions, set `live_caption.speaker` to one of
`user | other | jarvis | unknown` (PROTOCOL.md §8.4) and `translated:true` so the
UI can distinguish original vs. translated lines.
