# Publishing JarvisVR to GitHub

A short checklist to take this repo public and give it the best shot at trending.

## 1. Repository path — ✅ done

Badges, links, and metadata across the repo point at the real GitHub path
**`sumitaich1998/jarvisvr`** (README badges, CHANGELOG compare/release links,
`SECURITY.md`, `CITATION.cff`, `CONTRIBUTING.md`, issue-template contact links).
If the repo is ever renamed/forked, search-and-replace that slug.

## 2. Create the repository & push

```bash
git init            # if not already a repo
git add -A
git commit -m "feat: JarvisVR — AI agentic mixed-reality OS for Meta Quest 3"
git branch -M main
git remote add origin https://github.com/sumitaich1998/jarvisvr.git
git push -u origin main
```

## 3. Set the description & topics

On the repo page → **About** (gear icon):

- **Description**: *An AI agentic operating system for mixed reality on the Meta Quest 3 — your own J.A.R.V.I.S.*
- **Topics**: `mixed-reality`, `meta-quest-3`, `ai-agent`, `llm`, `unity`,
  `openxr`, `webxr`, `jarvis`, `voice-assistant`, `multimodal`, `holographic-ui`,
  `passthrough`, `agentic-ai`
- Check **Releases**, **Packages** off if unused; enable **Discussions**.

## 4. Enable Actions & verify CI

- Settings → **Actions** → allow workflows. The `CI` workflow runs the Python +
  TypeScript test suites on push/PR; confirm the badge goes green.
- Settings → **Code security** → enable **Private vulnerability reporting** and
  (optionally) Dependabot + CodeQL.

## 5. Confirm the visuals render

The README embeds `docs/assets/banner.png`, `docs/assets/ui-mockup.png`, and
`docs/assets/architecture.png`. Open the rendered README on GitHub and confirm
all three load. Swap in real screenshots/a screen-recording GIF once you have a
device build — nothing converts like a real demo.

## 6. Cut a release

- Create an annotated tag and a **v0.1.0** GitHub Release; paste the
  `CHANGELOG.md` `0.1.0` section as the notes.

```bash
git tag -a v0.1.0 -m "JarvisVR v0.1.0"
git push origin v0.1.0
```

## 7. Launch & grow

- Add a short demo GIF/video to the top of the README.
- Pin a "good first issue" or two (see `CONTRIBUTING.md`).
- Share on r/virtualreality, r/OculusQuest, Hacker News (Show HN), X/Twitter,
  and relevant Discords — lead with the demo clip.
- Ask early users to ⭐ — social badges in the README update automatically.

## 8. Optional polish

- Add a `FUNDING.yml` entry (`.github/FUNDING.yml`) if you accept sponsorship.
- Add a project social preview image (Settings → **Social preview**) — reuse
  `docs/assets/banner.png`.
