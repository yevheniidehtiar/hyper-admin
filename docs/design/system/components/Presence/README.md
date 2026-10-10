Shows who else is on a record and the state of the realtime connection.

**Template:** `components/presence.html`, `components/connection_status.html`, fed by the existing realtime script.

- **Avatars:** `.ha-avatars` group with an `aria-label` that lists everyone and their status in words; initials on `ha-color-accent-soft`; a status dot: online (filled success), idle (hollow warning ring). Max three, then "+N".
- **Field lock hint:** when someone is editing a field, an accent pill "Bram is editing" next to its label and an accent outline on the input; editing is still allowed (the conflict dialog handles collisions).
- **Live indicator** (`.ha-live`) in the navbar: Live (filled dot), Reconnecting… (hollow ring, warning), Offline (square, danger). Shape and word differ, not just colour. `role="status"`.
- **Connection lost banner:** `.ha-banner` across the top of the content after 10s offline, with "Retry now"; removed on reconnect with a "Back online" toast.

**Test ids:** `data-testid="presence"`, `"connection-status"`, `"connection-lost"`.
