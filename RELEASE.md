# Release guide

This guide covers a manual release to
[GitHub](https://github.com/qq768699531/win-depends/releases) and
[PyPI](https://pypi.org/project/win-depends/).
Run the commands in PowerShell from the project checkout.

The existing CI tests the project and builds a wheel; it does not create
GitHub Releases or publish to PyPI. A successful CI run is not proof of
publication to either service.

## Prerequisites

- The GitHub repository exists and contains the release source and CI workflow.
- You have permission to push tags and publish GitHub Releases.
- You have a PyPI account with permission to publish `win_depends`.
  Confirm that the public project name is available to you before publishing;
  an internal package index does not establish ownership on PyPI.
- Your source, package contents, and dependencies have been reviewed for public
  distribution. Do not upload private code, credentials, or internal artifacts.
- Build, test, and upload tools are available:

  ```powershell
  python -m pip install . pytest pytest-cov build twine
  ```

Use an authorized PyPI API token. For an existing project, scope the token to
that project. Never commit tokens, include them in commands, or put them in
release notes. See [PyPI API tokens](https://pypi.org/help/#apitoken).

## Prepare the release

1. Choose a new version that has not already been published. Keep the package
   version in `pyproject.toml` and the CLI version in `cli.py` identical.
2. Move the relevant entries from `Unreleased` in `CHANGELOG.md` into a section
   for that version. Keep an `Unreleased` section for future work.
3. Run `python -m pytest -q` and check the CLI help and version:

   ```powershell
   python -m win_depends.cli --help
   python -m win_depends.cli --version
   ```

4. Commit the intended release changes and make them available on GitHub through
   your normal review process. Check `git status --short` and
   `git log -1 --oneline` so that the release commit contains no unintended work.
   Wait for CI to pass for that exact commit.

## Tag the approved commit

Replace the example version with the approved version. Confirm that `HEAD` is
the release commit before creating an annotated tag:

```powershell
$version = "1.0.4"
$tag = "v$version"
git show --no-patch HEAD
git tag -a $tag -m "Release $version"
```

Inspect `git remote -v` and identify the writable GitHub remote. Do not assume
that `origin` points to GitHub. Set its existing remote name, then push only
the intended tag:

```powershell
$githubRemote = "github"
git push $githubRemote $tag
```

The remote name above is an example, not a command to add or change a remote.
If the GitHub remote is not configured, configure it separately before
continuing. Do not move or force-push an already published release tag.
Wait for the tag's CI run to succeed.

## Build and inspect distributions

Build both the wheel and source distribution from the tagged commit, using a
new output location so older distributions cannot be uploaded by mistake:

```powershell
git status --short
git describe --tags --exact-match
$releaseDir = Join-Path $env:TEMP ("win-depends-$version-" + [guid]::NewGuid().ToString("N"))
python -m build --outdir "$releaseDir"
$artifacts = @(Get-ChildItem -LiteralPath $releaseDir -File |
    Where-Object { $_.Name -match '\.(whl|tar\.gz)$' } |
    Select-Object -ExpandProperty FullName)
python -m twine check --strict @artifacts
Get-FileHash -Algorithm SHA256 -LiteralPath $artifacts
```

Verify that the tag matches `$tag`, the checkout is clean, and both files have
the expected package name and version. Inspect the archives for unintended
files and confirm that the wheel contains the CLI package. Stop if any command
fails or the artifact set is incomplete.

Install the wheel into a separate test environment and verify its version,
help, and analysis of a known Windows executable. Do not treat metadata
validation alone as a runtime smoke test.
Record the release commit and artifact checksums.

## Prepare a draft GitHub Release

1. Open [GitHub Releases](https://github.com/qq768699531/win-depends/releases)
   and select **Draft a new release**.
2. Select the existing tag, rather than creating a different tag in the UI.
   Use `v<version>` as the title and copy the matching changelog section into
   the release notes. Include compatibility changes and known limitations.
3. Attach the exact wheel and source distribution that passed the checks above.
   Mark prereleases explicitly; do not mark a prerelease as the latest stable
   release.
4. Save the draft while completing PyPI publication.

Do not rebuild the distributions between GitHub upload and PyPI upload.
Both services should receive the same files.

## Publish to PyPI

Upload the checked artifacts to the public PyPI endpoint explicitly, avoiding
an accidental upload to an internal or test index:

```powershell
python -m twine upload --repository-url https://upload.pypi.org/legacy/ --username __token__ @artifacts
```

Enter the API token at Twine's password prompt or use your organization's
approved credential mechanism. Do not put the token directly in the command.

Confirm that the expected version and both distributions appear on the
[PyPI project page](https://pypi.org/project/win-depends/). In a clean test
environment configured to use only public PyPI, install the exact version and
check the CLI version:

```powershell
python -m pip install --index-url https://pypi.org/simple/ --no-cache-dir "win_depends==$version"
win_depends --version
```

Ensure that no configured extra index supplied the package, and perform the
Windows runtime smoke test again using the installed release.

PyPI does not allow reusing a previously uploaded distribution filename.
For incorrect published content, prepare a corrected version rather than
overwriting the existing release. If an upload partially succeeds, inspect
the published files and compare checksums before retrying only the missing
files; do not hide conflicts with `--skip-existing`.

## Finalize and verify

1. Publish the draft GitHub Release after PyPI verification succeeds.
2. Confirm that its tag points to the approved commit, its notes match the
   changelog, and both attached distributions match the recorded checksums.
3. Check that the README's CI badge links to successful runs and the PyPI badge
   shows the public stable version. Badge caches can delay updates; the PyPI
   project page is the publication source of truth.

If publication fails, keep the GitHub Release as a draft and resolve the
failure before announcing completion. Do not delete or rewrite public tags
or claim success based only on a local build or tag push.

For service-specific details, see
[GitHub release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
and the [Python packaging tutorial](https://packaging.python.org/en/latest/tutorials/packaging-projects/).
