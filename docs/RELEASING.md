# Releasing

The pipeline builds everything; uploading to `repo.redwizard.xyz` stays manual
(the hosting is not managed from this repo).

## For contributors: cutting a release

1. Bump the `version` in each changed addon's `addon.xml` (per-addon versions
   are independent; Kodi only offers updates when the version grows).
2. Make sure CI is green on the commit you want to ship.
3. Tag it with a **bundle version** and push the tag:

   ```
   git tag v1.7.6
   git push origin v1.7.6
   ```

   Tags containing a hyphen (e.g. `v1.7.6-rc1`) publish as **prereleases**.
   The Release workflow re-runs the blocking validation, builds the channel
   bundles with `tools/build_repo.py --bundle <tag>`, and publishes a GitHub
   Release with the assets. (`workflow_dispatch` can rebuild a release for an
   existing tag.)

Which addon ships to which channel is `channels.json`; the build fails if an
addon directory isn't mapped there. One-time setup note: pushing anything
under `.github/workflows/` requires your GitHub token to have the `workflow`
scope (`gh auth refresh -s workflow`).

## For the site maintainer: publishing to repo.redwizard.xyz

Each release carries one zip per channel — `redwizard-repo-<channel>-<tag>.zip`
— plus `merge_addons.py`. Only channels whose addons changed need touching.
The zips contain **only this repo's addons**; everything else on the server
(third-party zips and their index entries) is yours and is never modified.

1. Download the changed channel zip(s) and `merge_addons.py` from the release.
2. Unpack each zip over the matching server channel directory
   (`…/redwizardrepo/main/`, `…/21omega/`, `…/22piers/`). This drops in the
   per-addon folders (zips + artwork) and a partial index named
   `addons.repo-owned.xml` — your `addons.xml` is not overwritten.
3. In each touched channel directory, run:

   ```
   python3 merge_addons.py addons.xml addons.repo-owned.xml
   ```

   This replaces/inserts the repo-owned `<addon>` entries by id, leaves all
   third-party entries untouched, and rewrites `addons.xml.md5`. The
   `addons.repo-owned.xml` file can be deleted afterwards.
4. Upload the changed files.

If you'd ever like the upload automated (SSH/rsync from CI) or the hosting
moved to GitHub Pages behind the domain, open an issue — the pipeline was
built to make that step pluggable.
