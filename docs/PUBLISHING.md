# Publication handoff — connected account esmoai

## Step 1: create one empty public repository

Open https://github.com/new while signed in to `esmoai`.
Choose owner `esmoai`, repository name **living-universe**, visibility **Public**.
**Do not** pre-create a README, .gitignore or license; this source tree contains all three. Create the repository.

The GitHub connector available during this preparation can write files and commits to an existing repository, but it did not expose the ability to create a new repository. The repository and GitHub Pages site were **not created** during this handoff.

## Step 2: publish this curated source

From the extracted public-source directory:

```sh
# Recommended: use an authenticated GitHub CLI; login happens in your own terminal.
gh auth login
git init -b main
git add .
git commit -m "chore: initial Living Universe v0.3 public pre-alpha"
git remote add origin https://github.com/esmoai/living-universe.git
git push -u origin main
```

If you use GitHub CLI and have not created the repository in the browser, you can create and push in one operation **after** initializing/committing the source:

```sh
gh repo create esmoai/living-universe --public --source=. --remote=origin --push
```

Do not do both creation methods: the CLI create command expects the repo not to exist. Use your own authenticated GitHub session; never insert tokens into the source tree or chat.

Alternatively, once the empty repository is created, return to the ChatGPT conversation and provide its exact repository link. The connected GitHub tools can then upload the reviewed source files, subject to connector permissions. Do not upload the original private 14 MiB backup or `kernel/build/*.img` to the source repository.

If the destination is not empty, inspect its history before pushing. Never force-push or replace another repository's work.

## Step 3: enable static demo

In the repository **Settings → Pages**, select **Deploy from a branch**, choose **main** and **/docs**. GitHub Pages will then serve `docs/index.html` at:

https://esmoai.github.io/living-universe/

**This URL is a prospective address, not a live verified deployment.** The static page has no native control endpoint and requires no public backend. GitHub Pages publication depends on the repository being public and Pages configured. Keep the loopback bridge local; never forward or expose its private session URL.

## Step 4: harden the repo

- Review **Settings → Actions → General**. Use least-privilege tokens and approval for outside pull requests; default workflows specify read-only tokens.
- Enable Dependabot alerts, dependency review/code scanning where available, and **private vulnerability reporting**.
- Configure branch protection/rulesets for `main`: required CI, review before merge, no force pushes or branch deletion.
- Enable Discussions for design questions and keep security reports private.
- Run the manual `Manual dual-architecture firmware boot gate` workflow when its QEMU dependencies are available; record both logs and do not mark boot as verified until they pass.
- Run a Windows observer smoke test and WebGL/WebXR browser regression before broad promotion beyond pre-alpha.

## Ownership and licenses

The project-authored code uses Apache-2.0, with original third-party terms retained. Make sure contributors acknowledge rights before merging external materials. A public repository can be forked and copied; do not publish secrets assuming future deletion removes them.
