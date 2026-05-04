# Security policy

Umber is a desktop theme suite — no executable code beyond installer/render scripts that run locally with the user's own privileges. The realistic security surface is small but not zero:

- `install.sh` performs `sudo` operations (SDDM theme install, `/etc/sddm.conf.d/` rewrites). A malicious modification to the script could escalate.
- Browser themes are pure WebExtension manifests (`theme.colors` only — no scripts, no permissions). Mozilla and Google review these on submission.
- The Plasma LookAndFeel package includes a QML splash + lockscreen. QML can call into native KDE APIs.

## Reporting a vulnerability

Please **do not** open a public issue for security reports.

Use GitHub's [private vulnerability reporting](https://github.com/viscous-values/umber/security/advisories/new) instead. That sends the report directly to the maintainer without exposing it publicly.

If GitHub Security Advisories is unavailable, you can also reach out via the contact path linked from the maintainer's GitHub profile at [github.com/viscous-values](https://github.com/viscous-values).

### What to include

- The component affected (Plasma package / Firefox theme / install.sh / a specific script)
- A reproducer or proof-of-concept
- The impact you've assessed
- Your disclosure timeline preference (default: 90 days from acknowledgement)

### What to expect

- **Acknowledgement** within 7 days
- **Initial assessment** (severity, scope, fix complexity) within 14 days
- **Fix + advisory publication** before the disclosure deadline you set, or coordinated with you if more time is needed

This is a solo-maintained project, so response times reflect that — please be patient if a report lands during a busy week.

## Scope

In scope:
- Privilege escalation via `install.sh` (e.g., a path the script writes that an unprivileged attacker could pre-create as a symlink to overwrite a system file)
- Code execution via the QML splash / lockscreen
- Supply-chain concerns in the renderer / build pipeline
- Browser theme manifests doing something a theme manifest shouldn't (theme.colors injection, etc.)

Out of scope:
- Color contrast / accessibility issues — open a regular issue for those, they're design feedback rather than security
- Reports about an upstream dependency (Plasma, Firefox, Mozilla AMO) — please report those upstream
- "I don't like this color" — design feedback, regular issue
