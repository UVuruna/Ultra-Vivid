# Updates

**Script:** [Updates (script)](updates.py)

## Purpose
Monorepo auto-update standard (root CLAUDE.md): the LAST released version
on GitHub is the source of truth, and the running app offers an UPDATE
when it is behind. `check(repo, enabled)` compares the latest release tag
of the project's repo against the running version (`app_version()`) and
returns an `Update(version, installer_url, page_url)`, or `None`.

`None` is the documented result for: up to date, check disabled, a dev
checkout (version has no numbers), a repo with no releases yet, or any
network failure — logged at info, never raised (the app starts fine
offline).

## Pseudocode

```
check(repo, enabled):
    IF disabled OR running version has no numbers -> None
    GET api.github.com/repos/<repo>/releases/latest  (10 s timeout)
    ON any failure -> log info, None
    latest = numbers from tag_name ("v0.1.23" -> 0,1,23)
    IF latest <= current -> None
    installer_url = first release asset ending in .exe (or None)
    RETURN Update(latest, installer_url, release page URL)
```

## Config
`config.json → update`: `{ "repo": "UVuruna/Ultra-Vivid", "check": true }`
(defaults apply when the section is absent).

## Connections
### Used by
- [Main Window](../gui/__index.md) — startup check → in-window Update
  button (download installer → launch → quit so files can be replaced)
