---
type: story
id: ZrFJ781mKteh
title: "RFC: Voice control & dictation — hands-free admin navigation and data entry"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - accessibility
  - rfc
estimate: null
epic_ref:
  id: 5RQIGVbDMSTJ
github:
  issue_number: 273
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3c9c0d820bae0eb88d5c94c3d3c125b890f02e00b8c166612ee284d50f518189
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T09:03:58Z
updated_at: 2026-03-29T06:05:41Z
---

## Summary

Add opt-in voice control and text-to-speech to HyperAdmin, enabling hands-free navigation, CRUD operations, form dictation, and data reading. No Python admin panel has this — a genuine accessibility differentiator.

Parent: #270

## Motivation

- **Motor impairments** — users who cannot use mouse/keyboard effectively
- **Hands-busy scenarios** — warehouse staff, field workers managing inventory
- **Power users** — voice commands are faster than clicking through menus
- **Accessibility leadership** — combined with WCAG 2.1 AA (Phase 4), this positions HyperAdmin as the most accessible admin framework in any language

## Architecture

Layers onto the existing Alpine.js + HTMX stack as an opt-in Alpine.js plugin (`x-voice`):

```
┌─────────────────────────────────────────┐
│  Voice Controller (Alpine.js component) │
│  - SpeechRecognition lifecycle          │
│  - Microphone state & UI indicator      │
├─────────────────────────────────────────┤
│  Command Parser                         │
│  - Pattern matching on transcripts      │
│  - Parameter extraction (model, row#)   │
├─────────────────────────────────────────┤
│  Command Router                         │
│  - Maps to HTMX requests (htmx.ajax()) │
│  - Navigation (window.location)         │
│  - Form interactions                    │
├─────────────────────────────────────────┤
│  Feedback Manager                       │
│  - SpeechSynthesis for voice responses  │
│  - ARIA live region for screen readers  │
├─────────────────────────────────────────┤
│  State Machine                          │
│  - Current view context                 │
│  - Confirmation-wait state              │
│  - Ambiguity resolution                 │
└─────────────────────────────────────────┘
```

## Command Vocabulary

| Category | Commands | Parameters |
|----------|----------|------------|
| **Navigation** | "go to {model}", "open {model}", "back", "home" | model name |
| **Create** | "create new {model}", "add {model}" | model name |
| **Read** | "view row {n}", "show row {n}" | row number |
| **Update** | "edit row {n}" | row number |
| **Delete** | "delete row {n}" + "confirm"/"cancel" | row number |
| **Search** | "search {query}", "find {query}" | query text |
| **Sort** | "sort by {field}" | field name, direction |
| **Pagination** | "next page", "previous page", "page {n}" | page number |
| **Form** | "field {name}", "set {field} to {value}", "clear", "save", "cancel" | field, value |
| **Voice** | "start listening", "stop", "help", "read page", "read form" | — |

## Ambiguity Handling

- **Context-aware**: On detail view for Product #42, "delete" means that product. On list view, "delete" prompts "Which row?"
- **Stateful buffer**: Ambiguous commands enter "waiting for clarification" state with 10s timeout
- **Required identifiers for destructive actions**: "delete row {n}" required on list views, bare "delete" rejected

## Destructive Action Confirmation

```
User: "delete row 5"
TTS:  "Delete Product in row 5? Say 'confirm' or 'cancel'."
User: "confirm"
TTS:  "Product deleted."
```

Mirrors existing `hx-confirm` behavior in voice modality. Auto-cancels after 10s timeout.

## Text-to-Speech (TTS)

Uses the universally-supported `SpeechSynthesis` API:

- **List results**: "Showing 10 of 47 products"
- **Row reading**: "Row 1: Name, iPhone 15. Price, 999 dollars. Status, active."
- **Form reading**: "Name field. Current value: iPhone 15. Required."
- **Error reading**: "2 errors. Name: This field is required. Price: Must be positive."
- **Interruptible**: Any new command or "stop" cancels current speech
- **Configurable**: Rate/voice stored in localStorage

## Accessibility Synergy

Voice control and screen readers are **complementary, not competing**:

- Screen readers = output (app → user, WCAG Principle 1: Perceivable)
- Voice control = input (user → app, WCAG Principle 2: Operable)
- Shared `<div role="status" aria-live="polite" id="voice-status">` serves both
- OS-level voice tools (Dragon, macOS Voice Control) benefit automatically from good ARIA markup
- HyperAdmin's `data-testid` attributes provide hooks for command targeting (e.g., "delete row 5" → 5th `row-delete-btn`)

## Browser Compatibility

| Browser | SpeechRecognition | SpeechSynthesis |
|---------|-------------------|-----------------|
| Chrome/Edge | Full (`webkitSpeechRecognition`) | Full |
| Safari | Supported (14.1+) | Full |
| Firefox | **Not supported** | Full |
| Opera | Supported | Full |

**Fallback**: Feature-detect `SpeechRecognition`. If absent, hide voice UI entirely. App remains fully functional via keyboard/mouse. ~90-93% of users have full support.

## Existing Solutions Audit

- **No mainstream admin panel** ships voice control (Django Admin, Flask-Admin, SQLAdmin, Laravel Nova, React Admin, AdminJS)
- **annyang.js** — lightweight command library (~2KB), good pattern reference but small enough to inline
- **Artyom.js** — bidirectional STT+TTS, worth studying for architecture
- Enterprise dashboards (Salesforce, SAP) have experimented but not shipped publicly

## Implementation Phases

### Phase 1 — Foundation
Alpine.js voice controller, microphone toggle, basic navigation ("go to {model}", "back", "home"), TTS status announcements. Feature-gated behind user preference.

### Phase 2 — CRUD Commands
"create", "edit row N", "delete row N" with confirmation flow. Context-aware resolution based on current view.

### Phase 3 — Form Dictation
Field-level dictation when text input focused. "Set {field} to {value}" commands. "Read form" / "read errors" TTS.

### Phase 4 — Advanced
Search/filter by voice, sort commands, custom command registration for model-specific actions, multi-language support via `recognition.lang`.

Each phase is independently shippable. The plugin adds **zero weight** for deployments that don't enable it.

## Open Questions

- [ ] Should this be a separate package (`hyperadmin-voice`) or built-in behind a feature flag?
- [ ] Firefox fallback: accept the gap, or integrate a third-party speech service?
- [ ] Multi-language command vocabularies — how to structure translations?
- [ ] Privacy: Chrome streams audio to Google for recognition — document this clearly?
- [ ] Custom commands per model: `ModelAdmin.voice_commands = [...]`?

---
https://claude.ai/code/session_01XktRz2PFThVGgPMoUmaEjc
