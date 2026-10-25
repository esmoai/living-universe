# Publication: source, Pages and releases are separate

The public repository is esmoai/living-universe. Do not create another repository, initialize over it or force-push its history.

## Activate the website once

1. Open https://github.com/esmoai/living-universe/settings/pages .
2. Under Build and deployment > Source, select **GitHub Actions**.
3. Open Actions > Deploy interactive demo > Run workflow, choosing main.

The previous main /docs branch-publishing instructions are superseded by pages.yml. Repository files cannot by themselves enable an account-side Pages setting. The connected source-editing tools do not expose this administrative operation. Never paste a personal access token into source, issues or chat.

The workflow builds an explicit static allowlist into _site/, uploads it, deploys to github-pages and requests status.json to verify its exact source commit. Only a successful deployment establishes https://esmoai.github.io/living-universe/ as live.

The payload contains HTML, notices, public byte samples and build status. It never deploys a native observer, private log, workspace archive or privileged endpoint. Missing Pages configuration intentionally fails with an explanation.

## Complete releases

Git tracks source, tests, licenses, examples and standalone HTML. CI explicitly installs the compiler/linker, builds the hosted tools and all boot media, and runs both QEMU gates. A separate Windows job runs the actual EXE. Pull requests have no publishing authority.

After all gates pass on a push to main, the release job reads RELEASE_VERSION and creates a pre-alpha containing LivingUniverse-Complete-Kit.zip, standalone HTML, notes and SHA-256 checksums. The kit contains source plus generated executables and images. Existing releases are never overwritten; increment RELEASE_VERSION for another release. The earlier local seed tag was not automatically a remote release.

Read-only build jobs have no deployment secrets. Only the Pages deploy job has Pages/OIDC permissions; only the gated release job has contents write. Do not add pull_request_target execution, broad personal tokens or privileged containers to bypass a failed test.

## Owner-managed safeguards

Enable private vulnerability reporting and appropriate branch rules after initial CI succeeds. Review required checks and outside-contributor approval. Dependabot proposals need review, not automatic merging. No administrative setting is claimed enabled without API or UI evidence.
