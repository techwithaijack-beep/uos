# Publishing μOS

> **Security first.** A GitHub personal access token was posted in the chat
> that produced this repo. **Revoke it now** before doing anything else:
>
> GitHub → Settings → Developer settings → Personal access tokens (fine-grained) →
> find the token starting with `github_pat_11B7TNSY…` → **Revoke**.
>
> Then generate a new one only if you need it — and never paste tokens into
> chat windows. Use `gh auth login` locally instead.

## Publishing to GitHub

Assumes you have the GitHub CLI (`gh`) installed and authenticated as yourself
(`gh auth login`). **Do not use a token pasted in chat.**

```bash
cd /Users/loongnianchew/Desktop/claude/sql/uos

# Initialize git
git init
git add .
git commit -m "μOS v0.1 — initial public release"

# Create the repo under your account or org (replace <owner>)
gh repo create <owner>/uos --public \
    --description "μOS — a kernel for LLM-native computing" \
    --source . --push

# Add topics for discoverability
gh repo edit <owner>/uos --add-topic llm \
                         --add-topic agents \
                         --add-topic operating-system \
                         --add-topic agent-framework \
                         --add-topic llm-agents \
                         --add-topic kernel
```

Then open the repo URL printed by `gh repo create` and:

1. **Pin the repo** on your profile.
2. **Enable Discussions** (Settings → General → Features) for the launch thread.
3. **Add a social preview image** (Settings → General → Social preview).
4. Set the **Homepage** to the WHITEPAPER link.

## Publishing to PyPI (optional)

```bash
pip install build twine
python -m build
python -m twine upload dist/*
```

Reserve the `uos` name early if possible, or pick a less contested alias
(e.g. `microos`, `uos-kernel`).

## Launch checklist

- [ ] Token revoked.
- [ ] `git log --all` has no sensitive data.
- [ ] `pytest` green locally.
- [ ] `python -m benchmarks.run --suite micro` produces numbers.
- [ ] README top-of-page quote renders (on GitHub mobile and desktop).
- [ ] At least one real-model run of `examples/01_hello_agent.py` (swap the
      driver) in a discussion post for social proof.
- [ ] Pin the repo.
- [ ] Tweet/post with the README table as the hook. Link WHITEPAPER, not the
      root — the argument does the persuading.

## After launch

- Watch for issues for the first 48h; they move fast.
- Keep the LOC budget. Resist feature PRs that don't strengthen the model.
- Ship the first benchmark number within two weeks — numbers harden the claim.
