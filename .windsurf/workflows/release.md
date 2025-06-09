---
description: Create a new release with version bump
---

# Release Workflow

Perform these actions in sequence to create a new release:

## 0a Check git status & stage & add necessary files

## 0b Update CHANGELOG.md

## 1. Run Quality Checks

```bash
poetry run pre-commit run --all-files
```

## 2. Update Version

// Prerequisites: use git commands to find out exactly what will be new in this release. Changelogs i mean. Also decide whether it will path, minor or major.

```bash
# Choose one:
poetry version patch  # for bug fixes (0.7.1 -> 0.7.2)
poetry version minor  # for new features (0.7.1 -> 0.8.0)
poetry version major  # for breaking changes (0.7.1 -> 1.0.0)
```


## 3. Create a Git Tag

```bash
git add pyproject.toml
git commit -m "chore: bump version to v$(poetry version -s)"
git tag -a v$(poetry version -s) -m "Release v$(poetry version -s)"
```

## 4. Push Changes and Tag

```bash
git push
git push origin v$(poetry version -s)
```
