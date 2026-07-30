# Site Capacity Upgrade Decision Engine

Automates the three manual checks a telecom operator runs before approving a
mobile site capacity upgrade. Takes a site's data, returns `APPROVED`,
`REJECTED`, or `NEEDS_REVIEW` — with the reasoning behind every check.

The design goal is **reuse**: thresholds, which checks run per site type, and
whether a failure halts the process all live in `config/rules.yaml`. A
different operator ships a different rules file, not different code.

---

## Run it

```bash
pip install -e ".[dev]"

capacity-engine examples/site_1042.json     # evaluate a site
pytest                                      # 33 tests
```

Other options: `--rules PATH` for a different policy file, `--compact` for
single-line JSON, `-` or no argument to read stdin.

Exit codes: `0` approved · `1` needs review · `2` rejected · `3` usage error.

### Example output

```json
{
  "site_id": "SITE-1042",
  "decision": "NEEDS_REVIEW",
  "prerequisites": ["BACKHAUL_UPGRADE"],
  "checks": [
    { "name": "rnp",          "status": "PASS",         "reason": "Load 92.0% meets the 80.0% upgrade threshold" },
    { "name": "transmission", "status": "FAIL",         "reason": "Backhaul 450 Mbps is below the 720 Mbps target (600 Mbps + 20% spare)" },
    { "name": "power",        "status": "NEEDS_REVIEW", "reason": "Power headroom 3.20 kW is marginally short of the 3.30 kW target - borderline" },
    { "name": "civil_works",  "status": "PASS",         "reason": "Floor space is available for new cabinets" }
  ]
}
```

The transmission failure is *advisory*, so it flagged a prerequisite instead
of halting. Power landed in its borderline band, which is what drove the
overall `NEEDS_REVIEW`.

When a **blocking** check fails, everything after it is marked `SKIPPED` —
reported, not omitted, so a reader can see the absence was deliberate.

---

## How it works

```
rules.yaml ──┐
             ├──> DecisionEngine ──> DecisionResult
site.json ───┘         │
                       │  resolve checks for site_type
                       │  run in order, stop on blocking FAIL
                       │  aggregate: REJECTED > NEEDS_REVIEW > APPROVED
                       │
                       └──> CHECK_REGISTRY
                              rnp · transmission · power · civil_works
```

Each check is a plug-in class registered by decorator. It knows one domain
rule and nothing else — not the other checks, not the ordering, not its own
severity. The engine knows the orchestration and no telecom at all; the
string `"rnp"` never appears in `engine.py`.

### Configuration

```yaml
site_types:
  rooftop:    [rnp, transmission, power, civil_works]
  greenfield: [rnp, transmission, power]      # no civil works

checks:
  rnp:
    severity: blocking          # a failure halts the process
    min_load_pct: 80
    borderline_band_pct: 3
  transmission:
    severity: advisory          # a failure flags a prerequisite, continues
    spare_capacity_pct: 20
    on_fail_prerequisite: BACKHAUL_UPGRADE
```

`severity` is how the brief's "the checks aren't independent" requirement is
expressed — as config, not control flow. An operator who wants transmission
to be blocking edits one line. A test asserts this, so it can't regress.

Adding a check: write a class with `@register`, import it in
`checks/__init__.py`, add its name to the YAML. Nothing else changes.

---

## Assumptions

- **Thresholds are placeholders.** No numbers were given, so the shipped
  values (80% load, 20% backhaul spare, 0.5 kW power margin) are ones a
  domain expert would tune in YAML.
- **"Borderline" was undefined**, so each numeric check has a
  `borderline_band`. Falling short but landing inside it gives
  `NEEDS_REVIEW`. The lower edge is inclusive.
- **Civil works had no input field.** I added one optional boolean,
  `floor_space_available`, rather than invent domain rules. Assumed rooftop
  and indoor sites need the check; greenfield and monopole don't.
- **Measurements are optional; identity isn't.** Missing data yields
  `NEEDS_REVIEW` from the check that needed it — that's the brief's
  behaviour, and a required field would have crashed instead.
- **Everything unknown fails toward a human.** Unrecognised site type,
  missing data, even a check that throws: all degrade to `NEEDS_REVIEW`.
  A silent crash or a false approve is worse than a false review.
- **Bad config is different from bad data.** A malformed rules file raises at
  load time. A typo in `site_types` must never become a silently skipped
  safety check, so it fails at deploy rather than at decision time.

---

## With more time

- **Structured logging with a decision ID** and the rules-file hash, so a
  decision can be reconstructed months later — `evaluated_at` is currently
  the only audit metadata.
- **Fetch inputs instead of receiving them.** The three data sources are
  three different systems; I'd add adapters with staleness metadata so a
  check can downgrade on "this figure is nine days old" alone.
- **A FastAPI layer** — about ten lines over `evaluate_site`, since the core
  has no I/O. The real design work is batching and timeouts.
- **Property-based tests** around the thresholds. That would have caught my
  inclusive-boundary ambiguity before I wrote a test with the wrong
  expectation.
- **Richer rule expressions**, carefully. Real policy will want conditions
  like "20% spare, or 15% if fibre is scheduled." I'd add named, tested rule
  strategies rather than an expression language — that turns config into
  untested code.
- **CI** running `ruff` and `mypy --strict` alongside the tests, plus a
  dry-run mode that diffs a proposed rules file's outcomes against current
  policy.