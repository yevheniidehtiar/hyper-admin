# SDD: i18n Top-20 Locale Expansion

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved |
| Issue | TBD (filed via gitpm push after merge) |
| Milestone | v0.5.2 — i18n top-20 |
| Created | 2026-05-05 |
| Last updated | 2026-05-05 |

---

## Problem

`docs/specs/i18n.md` (v0.4.1) shipped the i18n pipeline (Babel + gettext + RTL +
locale switcher) and seeded 7 locales — `en, es, fr, de, zh_CN, ja, uk` — with
**empty** message catalogs per the original "ship empty catalogs" decision. As a
result, every non-English deployment silently falls back to English msgids: the
infrastructure works, but no user actually sees a translated page. The product ask
is to reach the top-20 world languages with at least working draft translations,
plus add Dutch (`nl`) and the two RTL must-haves (`ar`, `he`) that were referenced
by the RTL frozenset but never seeded.

## Goals

- Expand `_DEFAULT_SUPPORTED_LOCALES` from 7 to 20 codes.
- Seed 13 new locale catalogs: `ar, he, hi, pt_BR, ru, ko, it, tr, pl, nl, vi, id, th`.
- Replace the empty `msgstr`s in the 6 existing non-English catalogs (`es, fr, de,
  ja, uk, zh_CN`) with AI-drafted translations, marked `#, fuzzy` per Babel
  convention.
- Each `.po` file ships with a correct `Plural-Forms` header sourced from CLDR.
- RTL works for `he` (already wired for `ar`).
- Test matrices cover all 20 locales.

## Non-Goals

- `User.preferred_locale` field — cookie-driven switching is sufficient. Deferred to
  a follow-up.
- `pt_PT` and `zh_TW` variants — additive, deferred.
- Professional translation review — `fuzzy` flag means production excludes drafts
  by default. Native-speaker review tracked in 19 follow-up issues tagged
  `i18n-review`.
- New extracted msgids — the source-string set (53 msgids) is unchanged.
- URL-prefix locale routing (out of scope per original SDD).
- Locale-aware date/number formatting beyond Babel defaults (out of scope per
  original SDD).
- A locale-discovery / runtime locale-list endpoint.

## BDD Scenarios

```
Scenario: every supported locale has a compiled .mo file
  Given the 20 locale codes in _DEFAULT_SUPPORTED_LOCALES
  When  the test suite runs
  Then  src/hyperadmin/locale/<code>/LC_MESSAGES/messages.mo exists for each code

Scenario: every non-English locale catalog declares a Plural-Forms header
  Given a .po file at src/hyperadmin/locale/<code>/LC_MESSAGES/messages.po
  When  the file is parsed via babel.messages.pofile.read_po
  Then  the catalog header `Plural-Forms` is present and non-empty

Scenario: Hebrew flips the document to RTL
  Given supported_locales contains "he"
  When  a request resolves to locale "he"
  Then  the rendered <html> element has dir="rtl"
  And   lang="he"

Scenario: Accept-Language pt-BR resolves to pt_BR
  Given supported_locales contains "pt_BR"
  When  a request arrives with Accept-Language: pt-BR,pt;q=0.9
  Then  request.state.locale == "pt_BR"

Scenario: locale switcher accepts a new top-20 code
  Given supported_locales contains "nl"
  When  POST /admin/locale with locale=nl
  Then  the response sets the hyperadmin_locale cookie to "nl"
  And   the response is a 302 redirect

Scenario: fuzzy entries are excluded from compiled catalogs by default
  Given a .po file with `msgstr` set and `#, fuzzy` annotation
  When  pybabel compile runs without `--use-fuzzy`
  Then  the corresponding .mo entry falls back to the msgid
  And   production deployments show English until reviewers clear the fuzzy flag
```

## Design

### Architecture

No architectural changes. This expansion adds **data** (catalog files) and a small
**configuration** edit. The flow is unchanged from the original i18n SDD:

```
HTTP request
    |
    v
LocaleMiddleware  ----------> request.state.locale = "nl"
    |                        request.state.translations = babel.support.Translations
    v
Jinja2 env (ext.i18n) ------> _, gettext, ngettext bound to request.state.translations
    v
{{ _("Save") }} -> "Opslaan"  (or msgid fallback for fuzzy entries)
```

### Data Model Changes

No data model changes.

### API / Protocol Changes

No public-API changes. `HyperAdminSettings.supported_locales` default grows from 7
to 20 entries; the type and field name are unchanged. No new exports from
`hyperadmin/__init__.py`.

### Configuration Changes

| Variable | Old default | New default |
|---|---|---|
| `HYPERADMIN_SUPPORTED_LOCALES` | `["en","es","fr","de","zh_CN","ja","uk"]` | `["en","es","fr","de","zh_CN","ja","uk","ar","he","hi","pt_BR","ru","ko","it","tr","pl","nl","vi","id","th"]` |

Order: existing 7 first (preserves diff readability), then 13 new codes grouped by
script family (`ar, he` RTL → `hi` Devanagari → `pt_BR, ru, ko, it, tr, pl, nl`
European → `vi, id, th` SE-Asian).

### Plural-Forms by locale

Sourced from Unicode CLDR / Babel's plural-rule table.

| Locale | nplurals | Formula |
|---|---|---|
| ar | 6 | `(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : n%100>=11 ? 4 : 5)` |
| he | 2 | `(n != 1)` |
| hi | 2 | `(n != 1)` |
| pt_BR | 2 | `(n > 1)` |
| ru | 3 | `(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 \|\| n%100>=20) ? 1 : 2)` |
| ko | 1 | `0` |
| it | 2 | `(n != 1)` |
| tr | 2 | `(n != 1)` |
| pl | 3 | `(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 \|\| n%100>=20) ? 1 : 2)` |
| nl | 2 | `(n != 1)` |
| vi | 1 | `0` |
| id | 1 | `0` |
| th | 1 | `0` |

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Fuzzy entry compiled without `--use-fuzzy` | `msgfmt` excludes it; runtime returns msgid (English) — already the existing fallback path |
| Cookie value not in expanded `supported_locales` | Existing `negotiate_locale()` falls back to Accept-Language → default (no change) |
| Accept-Language `pt-BR` against `supported=["pt_BR", ...]` | `_parse_accept_language` normalises hyphen to underscore; `babel.negotiate_locale` matches exactly (no change) |
| Accept-Language `pt` (no region) | Falls through to next preference. If only `pt_BR` is supported, `pt` does NOT match (Babel does not auto-broaden). Documented; revisit if real users hit it |
| Hebrew with no `_rtl.css` Hebrew-specific overrides | `_rtl.css` is locale-agnostic via `[dir="rtl"]`; no Hebrew-specific font-family rules in current CSS (verified) |
| `Plural-Forms` header missing in a `.po` | Detected by new `test_plural_forms_header_present` parametrized test |
| Malformed AI translation (e.g. unbalanced `%(...)s`) | `babel.messages.pofile.read_po` validates placeholder consistency; the new plural-forms test parametrizes through the same parser, surfacing parse errors |
| Native-speaker review unmerged | `fuzzy` flag keeps production rendering English; per-locale follow-up issues track review |

## Migration & Backward Compatibility

Backward compatible — no migration required.

- Apps overriding `HYPERADMIN_SUPPORTED_LOCALES` via env var or settings keep their
  list verbatim; only the default changes.
- Existing 6 non-English catalogs gain `msgstr` content but every entry is `fuzzy`;
  compiled `.mo` excludes fuzzy entries → existing deployments still render English.
- No public-API changes; no semver-major required.
- The original i18n SDD's "Empty catalogs" decision is superseded by the Decision
  Log row below.

## Open Questions

- [x] Translation source: AI-drafted fuzzy vs scaffold empty vs translation API? →
  **AI-drafted, marked fuzzy.** User-confirmed.
- [x] `User.preferred_locale` field in scope? → **No, deferred.** User-confirmed.
- [x] Include `pt_PT` / `zh_TW`? → **No, deferred.** User-confirmed.
- [ ] Native-speaker review path — open per-locale follow-up issues? Track post-merge.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| AI-drafted fuzzy translations for all 19 non-English locales | `fuzzy` is the canonical Babel mechanism for "needs review"; `msgfmt` excludes fuzzy entries by default → safe-by-default deployments; supersedes the original "ship empty" SDD decision because empty catalogs deliver zero user value | Scaffold empty (matches original SDD but every must-have locale stays English); use a translation API offline (adds tooling for a 53-string corpus) |
| Top-20 = existing 7 + 13 new (`ar, he, hi, pt_BR, ru, ko, it, tr, pl, nl, vi, id, th`) | Selected by global speaker count + admin-UI relevance; covers user's must-have list (`uk, en, nl, fr, de, es, ar, zh`) + extends to 20 | 21 with `zh_TW`; 19 with `pt_PT` swapped in; deferred — additive, easy follow-up |
| `pt_BR` only (not `pt_PT`) | 210M speakers, dominant on web; `pt_PT` is one-PR additive when needed | Both variants now (pushes count to 21) |
| 2 RTL locales (`ar`, `he`); defer `fa`, `ur` | Both already in `RTL_LOCALES` frozenset, but only `ar` and `he` make the top-20 shortlist by speaker count + admin-UI demand | Add all 4 RTL codes to defaults (out of top-20 framing) |
| Order in `_DEFAULT_SUPPORTED_LOCALES`: existing 7 first, then 13 new | Diff readability — reviewers see the activation as an append-only change | Alphabetical (more diff churn, no functional difference) |
| Single PR with multiple commits (SDD → catalogs → activation → tests) | Memory rule "stack tightly-coupled work as separate commits on one PR"; each commit is an independent reviewable concern | One mega-commit (loses commit-level review traceability); 4 separate PRs (rebase churn for tightly-coupled changes) |
| Fuzzy flag on every drafted entry, including the 6 existing-but-empty catalogs | Treats `es, fr, de, ja, uk, zh_CN` identically with the 13 new — uniform "needs review" path; no special-casing | Only fuzzy-flag the 13 new and leave existing 6 empty (inconsistent UX: must-have languages still empty) |
