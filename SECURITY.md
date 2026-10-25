# Security policy

## Supported versions

This is a **pre-alpha research release**. No version is approved for production deployment, security isolation, privileged execution of untrusted programs or installation on a primary machine. Security reporting is welcome for every public revision.

## Reporting vulnerabilities

Do **not** publish exploitable details, credentials, sensitive logs or private data in GitHub issues. Prefer GitHub's *Report a vulnerability* / Private Vulnerability Reporting feature once the repository owner enables it under **Settings → Security & analysis**. Until then, open a public issue requesting a private contact channel **without exploit details**; do not transmit secrets in the issue.

Include affected commit, environment, reproduction steps, impact, and whether sensitive data could have been exposed. Maintainers should acknowledge promptly, preserve confidentiality and coordinate a fix and advisory. No arbitrary response-time SLA is promised while the project is volunteer-maintained.

## Boundary reality

The Stage 0 kernel does **not** implement MMU-owned user-space isolation, capabilities, sandboxing, IOMMU, drivers or a native arbitrary-program executor. The hosted C observer uses the host OS, binds locally and offers only authenticated, read-only measurements; it is not sandboxed and runs with the user's normal privileges. Browser UI permission labels are not kernel authorization.

Do not bypass operating-system protections, disable antivirus/Secure Boot, run downloaded binaries as administrator or publish a bridge's private session URL. Keep evidence imported into the browser local. Workspace exports are plaintext. External contributions to executable parsers, system services, privileged code and remote protocol handling require extra review and adversarial tests.
