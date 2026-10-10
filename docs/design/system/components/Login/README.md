Sign-in, MFA challenge and lock-out screens, with SSO buttons for v0.5.2.

**Template:** `auth/login.html`, `auth/mfa_challenge.html`, `auth/mfa_settings.html`.

- A centred `.ha-login` card (`ha-radius-xl`) on `ha-surface-base`, with the mark (or the host's logo), "Sign in to {site_title}" in `ha-h2` and a one-line hint.
- SSO buttons first when configured, as secondary full-width buttons "Continue with {provider}" (provider's name as text; a provider logo only if the host supplies it). Then an "or" divider and the email/password form. With SSO only, hide the form.
- Error: a danger alert above the fields, deliberately not saying which field was wrong; the password gets `aria-invalid`.
- MFA: six single-digit inputs in `.ha-otp` (always LTR), `autocomplete="one-time-code"` on the first, paste fills all; "Use a recovery code" link below.
- Locked out: a warning alert with the wait time and who to contact; no form.
- Uses `autocomplete="username"` and `"current-password"` so password managers work.

**Test ids:** `data-testid="login-form"`, `"mfa-form"`, `"locked-out"`, `"sso-<provider>"`.
