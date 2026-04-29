# Contributing

## Plugin requirements

- `plugin.json` at zip root, valid against the SDK schema
- `LICENSE` file inside the zip (any OSI-approved license)
- Reverse-DNS `id` (e.g. `com.your-org.tool-name`)
- Semver version (`1.0.0`)
- Path: `plugins/{id}/{version}/{id}.zip`

## Submission

1. Fork the repo
2. Add your zip under `plugins/{your-id}/{version}/{your-id}.zip`
3. Open a PR

## CI gates

- Schema validation
- Hash & size computation
- Permission risk classification
- VirusTotal scan (if `VT_API_KEY` repo secret set)
- License presence check

## Auto-merge

Green CI + `permissionRiskLevel != "high"` -> auto-merge. High-risk plugins
(those requesting `ProcessExec u FileSystemUser u Network`) are labelled
`needs-human-review` and require maintainer approval.
