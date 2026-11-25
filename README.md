# Civic Revision

[Open Civic Revision](https://coolcode.ca/civicrevision/) — a dated, accumulating watch of Wikipedia edits about Canadian institutions and public policy.

<!-- coolcode:guide -->
Choose a topic, revision month or citation/reversion filter, then expand a revision to compare removed and added text. Original Wikipedia diff links retain the full context. Subscribe to all edits or one topic using the RSS links, including in Feed Harbour. The starter watchlist includes Canadian institutions, privacy/copyright/access-to-information policy, economic services, BC, Nova Scotia and Halifax. Revision date means when Wikipedia changed; first captured and source checked mean when this collector observed it. A changed citation can appear as one removal and one addition. Reversion signals are not judgments about intent, accuracy or vandalism.
<!-- /coolcode:guide -->

## Collection and retention

The keyless Wikimedia Action API is queried every six hours (`37 */6 * * *`, UTC). Each configured article supplies its latest 12 revisions; the oldest supplies a parent baseline. New observed revision IDs are merged into `web/data/history/YYYY-MM.json` permanently. First-observed values and topic IDs remain intact. Recent UI results include the latest 200 retained records; monthly browsing exposes older records. RSS has 50 latest records per topic. No editor IPs, names or affiliation inference are collected.

Requests use an identifying User-Agent, maxlag, bounded 45-second timeout and 12 MB response limit. All configured articles must load successfully before any published data is replaced. A stage-and-swap protects existing captures on collection failure. GitHub Actions validates data, application and browser behavior before committing captures and deploying. Existing captures are validated before merging; corrupted history fails the job. Pages workflow concurrency serializes collections and uses current main when a queued job starts. PRs build offline and cannot collect or push.

Coverage is explicitly bounded, not a full historical archive. If an article gains more revisions between collections than the requested window, intermediate edits may be missed; non-overlap with prior observed revisions is flagged. Hidden/deleted content and missing parent revisions are marked unavailable. Source outages leave the previous published capture; the UI warns after 18 hours. Initial windows can include old revisions from quiet articles.

## Expand or customize

Edit `sources.json`: add an article title to a topic, add a topic with a unique slug and label, or change `language`. Articles can be arbitrary existing Wikipedia titles, not just the starter list. Set `revisions_per_article` from 2 to 50. The collector permits up to 100 unique titles per run to bound load. Then run:

```sh
python3 scripts/collect.py
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py
```

Inspect the output and coverage, then commit `sources.json` and `web/data/` together. The current topic list determines active feeds; archived records keep their original topic IDs, even if configuration changes. Every historical month remains browsable. To collect immediately in GitHub, run **Browser tool · Check and publish** manually on `main`. No keys are required. Never edit `checked_at` to simulate freshness.

## Interpretation and attribution

Readable diffs simplify wiki links, emphasis and ref markup but preserve changed text. Large blocks are truncated and linked to the original diff. Citation comparison uses complete `<ref>…</ref>` bodies; a rewritten reference appears as removal/addition, and self-closing named reuses are excluded. Unchanged citation content is deduplicated. Reversion signals derive from Wikimedia undo/rollback/manual-revert tags or exact content hashes observed within the returned window; neither proves misconduct.

Wikipedia contributors own the article/summary content, licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Each record links its original diff and exact revision for attribution; these links identify the original contributor history. Source: [MediaWiki API:Revisions](https://www.mediawiki.org/wiki/API:Revisions). The app does not claim Wikipedia is an official government source.

## Operations

- Collector: `.github/workflows/pages.yml`; cron `37 */6 * * *` UTC; `workflow_dispatch` enabled.
- Freshness probe: `https://coolcode.ca/civicrevision/data/status.json`, field `checked_at`; expected every six hours, stale after 18 hours.
- Guard: `.github/workflows/schedule-guard.yml`, allowlists collector and itself.
- Healthchecks: optional GitHub Actions secret `HEALTHCHECKS_URL`; start/fail/success signals surround collection and checks. No secret is needed to build or collect.
- All browser assets remain project-relative; deploy only generated `dist/` via Pages. Hub catalogue record is `tool.json`.
