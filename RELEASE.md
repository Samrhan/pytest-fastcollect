# Release and PyPI Publishing Guide

This guide explains how to configure PyPI publishing and create releases for pytest-fastcollect.

## Table of Contents
- [PyPI Configuration](#pypi-configuration)
- [GitHub Secrets Setup](#github-secrets-setup)
- [Creating a Release](#creating-a-release)
- [Testing with TestPyPI](#testing-with-testpypi)
- [Troubleshooting](#troubleshooting)

---

## PyPI Configuration

### 1. Create a PyPI Account

1. Go to [https://pypi.org/account/register/](https://pypi.org/account/register/)
2. Register a new account
3. **Verify your email address** (important!)

### 2. Create a TestPyPI Account (Optional but Recommended)

1. Go to [https://test.pypi.org/account/register/](https://test.pypi.org/account/register/)
2. Register a new account (can use the same email as PyPI)
3. **Verify your email address**

> **Note**: TestPyPI is a separate instance of PyPI for testing. It's useful for validating your package before publishing to the real PyPI.

### 3. Generate API Tokens

#### For PyPI (Production):

1. Log in to [https://pypi.org/](https://pypi.org/)
2. Go to Account Settings → API tokens
3. Click "Add API token"
4. **Token name**: `github-actions-pytest-fastcollect`
5. **Scope**: Choose one of the following:
   - **Recommended**: "Project: pytest-fastcollect" (after first manual upload)
   - **Alternative**: "Entire account" (if project doesn't exist yet)
6. Click "Add token"
7. **COPY THE TOKEN IMMEDIATELY** - it will only be shown once!
   - Format: `pypi-AgEIcHlwaS5vcmcC...` (starts with `pypi-`)

#### For TestPyPI (Testing):

1. Log in to [https://test.pypi.org/](https://test.pypi.org/)
2. Go to Account Settings → API tokens
3. Click "Add API token"
4. **Token name**: `github-actions-test`
5. **Scope**: "Entire account" (TestPyPI doesn't matter)
6. Click "Add token"
7. **COPY THE TOKEN IMMEDIATELY**
   - Format: `pypi-AgEIcHlwaS5vcmcC...` (starts with `pypi-`)

### 4. First Manual Upload (Optional)

If you want to use a project-scoped token, you need to create the project first:

```bash
# Build the package locally
maturin build --release

# Upload to PyPI manually (first time only)
pip install twine
twine upload target/wheels/*

# Or upload to TestPyPI for testing
twine upload --repository testpypi target/wheels/*
```

After this first upload, you can create a project-scoped API token.

---

## GitHub Secrets Setup

### 1. Navigate to GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

### 2. Add PyPI Token

- **Name**: `PYPI_API_TOKEN`
- **Value**: Paste the PyPI API token you copied earlier (starts with `pypi-`)
- Click **Add secret**

### 3. Add TestPyPI Token (Optional)

- **Name**: `TEST_PYPI_API_TOKEN`
- **Value**: Paste the TestPyPI API token
- Click **Add secret**

---

## Creating a Release

The GitHub Actions workflow is configured to automatically publish to PyPI when you create a git tag.

### Method 1: Using Git Tags (Recommended)

```bash
# Make sure you're on the main branch and up to date
git checkout main
git pull

# Update version in pyproject.toml if needed
# version = "0.4.1"

# Commit version bump
git add pyproject.toml
git commit -m "Bump version to 0.4.1"

# Create and push the tag
git tag v0.4.1
git push origin main
git push origin v0.4.1
```

### Method 2: Using GitHub Releases UI

1. Go to your repository on GitHub
2. Click **Releases** → **Create a new release**
3. Click **Choose a tag**
4. Type a new tag name (e.g., `v0.4.1`)
5. Click **Create new tag on publish**
6. Fill in release title and description
7. Click **Publish release**

### What Happens Next

When you push a tag:

1. ✅ **CI builds** wheels for all platforms:
   - Linux (x86_64, x86, aarch64, armv7, s390x, ppc64le)
   - Linux musllinux (x86_64, x86, aarch64, armv7)
   - Windows (x64, x86)
   - macOS (x86_64, aarch64/Apple Silicon)

2. ✅ **Tests run** on Ubuntu, Windows, macOS with Python 3.8-3.12

3. ✅ **Artifacts are generated**:
   - Build attestations for supply chain security
   - Wheel files for each platform
   - Source distribution (sdist)

4. ✅ **Automatic PyPI upload** if all tests pass

---

## Testing with TestPyPI

Before creating a production release, you can test the publishing process with TestPyPI:

### 1. Manual TestPyPI Publish

1. Go to your repository on GitHub
2. Click **Actions** → **Publish to TestPyPI**
3. Click **Run workflow**
4. Fill in the reason (e.g., "Testing v0.4.1 release")
5. Click **Run workflow**

### 2. Test Installation from TestPyPI

After the workflow completes:

```bash
# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    pytest-fastcollect

# Verify it works
pytest --version
pytest tests/ --collect-only
```

> **Note**: We need `--extra-index-url` because TestPyPI doesn't have all dependencies (like pytest).

---

## Workflow Overview

### CI.yml (Main Workflow)

**Triggers:**
- Push to `main` or `master` branches
- Pull requests
- Git tags (e.g., `v0.4.1`)
- Manual workflow dispatch

**Jobs:**
1. **linux/musllinux**: Build wheels for Linux platforms
2. **windows**: Build wheels for Windows
3. **macos**: Build wheels for macOS (Intel + Apple Silicon)
4. **sdist**: Build source distribution
5. **test**: Run tests on multiple OS and Python versions
6. **release**: Publish to PyPI (only on git tags)

### publish-testpypi.yml (Testing Workflow)

**Triggers:**
- Manual workflow dispatch only

**Purpose:**
- Test the publishing process without affecting production PyPI
- Validate wheels can be built and uploaded successfully

---

## Version Management

Update version in [pyproject.toml](pyproject.toml):

```toml
[project]
name = "pytest-fastcollect"
version = "0.4.1"  # <-- Update this
```

**Version Numbering:**
- Follow [Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH
  - **MAJOR**: Breaking changes
  - **MINOR**: New features, backward compatible
  - **PATCH**: Bug fixes, backward compatible
- Tag format: `v0.4.1` (with `v` prefix)

---

## Troubleshooting

### Error: "Package already exists"

**Cause**: You're trying to upload a version that already exists on PyPI.

**Solution**:
1. Bump the version in `pyproject.toml`
2. Create a new tag with the new version

### Error: "Invalid token"

**Cause**: The API token is incorrect or has expired.

**Solution**:
1. Generate a new API token on PyPI
2. Update the `PYPI_API_TOKEN` secret in GitHub

### Error: "403 Forbidden"

**Cause**: Token doesn't have permission to upload to the project.

**Solution**:
1. If using a project-scoped token, make sure the project exists on PyPI
2. Or use an account-wide token instead
3. Re-generate the token with correct permissions

### Error: "Build failed on platform X"

**Cause**: Platform-specific compilation issue.

**Solution**:
1. Check the build logs in GitHub Actions
2. May need to add platform-specific dependencies or conditionals
3. Can exclude problematic platforms from the build matrix if necessary

### Testing Locally Before Release

```bash
# Build wheels for your current platform
maturin build --release

# Check the built wheel
ls -lh target/wheels/

# Install locally and test
pip install target/wheels/pytest_fastcollect-*.whl
pytest tests/ -v

# Clean up
pip uninstall pytest-fastcollect
```

---

## Security Best Practices

1. ✅ **Use API tokens, not passwords**
2. ✅ **Use project-scoped tokens** when possible
3. ✅ **Rotate tokens periodically** (every 6-12 months)
4. ✅ **Never commit tokens** to git
5. ✅ **Use TestPyPI** for testing before production release
6. ✅ **Enable 2FA** on your PyPI account

---

## Quick Checklist for Releases

- [ ] All tests passing locally
- [ ] Version bumped in `pyproject.toml`
- [ ] CHANGELOG updated (if you have one)
- [ ] README updated with new features/changes
- [ ] Committed and pushed to main
- [ ] Created and pushed git tag
- [ ] Verified GitHub Actions workflow succeeded
- [ ] Checked package on PyPI
- [ ] Tested installation: `pip install pytest-fastcollect`

---

## Additional Resources

- [PyPI Help](https://pypi.org/help/)
- [Maturin Documentation](https://www.maturin.rs/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [PyPA Packaging Guide](https://packaging.python.org/)
