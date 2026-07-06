# Kodi Repository Artifact Format — Research Notes

Researched 2026-07-06 against primary sources: Kodi source (`xbmc/xbmc` master), the
official wiki ([Add-on repositories](https://kodi.wiki/view/Add-on_repositories), "Page
updated for v19"), and the checker source (`xbmc/addon-check`, v0.0.36, last commit
2025-08-24). Kodi source paths below are repo paths in github.com/xbmc/xbmc.

## 1. addons.xml format

- Root element must be `<addons>` (case-insensitive match); Kodi iterates every child
  `<addon>` element and feeds each to the same `addon.xml` parser used for installed
  addons. Source: `CAddonMgr::AddonsFromRepoXML`,
  [xbmc/addons/AddonManager.cpp](https://github.com/xbmc/xbmc/blob/master/xbmc/addons/AddonManager.cpp)
  (~line 1350): rejects the document unless `RootElement()->Value()` equals `"addons"`,
  then walks `FirstChildElement("addon")` / `NextSiblingElement("addon")`.
- Each entry is parsed by `CAddonInfoBuilder::Generate` →
  [xbmc/addons/addoninfo/AddonInfoBuilder.cpp](https://github.com/xbmc/xbmc/blob/master/xbmc/addons/addoninfo/AddonInfoBuilder.cpp);
  element must be `<addon>` with non-empty `id` and `version` attributes, so copying each
  addon's `addon.xml` verbatim (minus the `<?xml?>` declaration) inside `<addons>` is
  exactly right — the wiki says the file "merely encapsulates the other addon.xml files
  in an `<addons>` tag" ([wiki](https://kodi.wiki/view/Add-on_repositories) §Addons.xml).
- Addon ids may only contain `a-zA-Z0-9.-_@!$` (`VALID_ADDON_IDENTIFIER_CHARACTERS`,
  AddonInfoBuilder.cpp:35); entries with other characters are dropped with an error.
- `<info>` may be served gzipped: Kodi decompresses if the URL ends `.gz` or the MIME
  type is gzip (`CRepository::FetchIndex`,
  [xbmc/addons/Repository.cpp](https://github.com/xbmc/xbmc/blob/master/xbmc/addons/Repository.cpp):231-243).
- Orchestration lives in `CRepositoryUpdateJob::DoWork`
  ([xbmc/addons/RepositoryUpdater.cpp](https://github.com/xbmc/xbmc/blob/master/xbmc/addons/RepositoryUpdater.cpp)),
  which calls `CRepository::FetchIfChanged`.

## 2. Checksum conventions

- `<checksum>` is a URL to a small text file used as a **change marker** for the
  `<info>` file. `CRepository::FetchChecksum` (Repository.cpp:159-206) reads the body and
  truncates at the first space or newline (`checksum.find_first_of(" \n")`), so both a
  bare hash and md5sum-style `hash  filename` are accepted — only the first token is used.
- By default the value is **not cryptographically verified** — the wiki states "it is not
  verified and not required to be a checksum as long as it is changed whenever addons.xml
  has changed". Verification happens only if the `<checksum verify="sha256">` attribute is
  set: then `FetchIndex` computes the digest of the fetched addons.xml bytes and compares
  case-insensitively (Repository.cpp:300-305, 221-229). Comparison is against the raw HTTP
  response, i.e. against the `.gz` bytes if you serve a pre-gzipped info file.
- If any `<dir>` lacks a `<checksum>`, the NOT_MODIFIED short-circuit is disabled and
  every check re-downloads all indexes (`FetchIfChanged`, Repository.cpp:277-285 — the
  per-dir checksums are concatenated and compared to the stored value only when *all*
  dirs have one).
- **Per-zip hashes** are controlled by the optional `<hashes>` element inside `<dir>`
  (`md5|sha1|sha256|sha512|false`; `true` is a deprecated alias for md5 —
  `ParseDirConfiguration`, Repository.cpp:314-329). If absent/false, no per-zip hash
  files are needed and downloads are not hash-verified. If set,
  `CRepository::ResolvePathAndHash` (Repository.cpp:44-100) first looks for a
  `content-<hashtype>` HTTP response header (base64), then falls back to fetching
  `<zip-url>.<hashtype>` (e.g. `plugin.foo-1.0.0.zip.sha256`) as a separate file, again
  tolerating `hash filename` format. There is **no** `<hash>` attribute inside addons.xml
  entries. Downloaded packages are verified against that digest before extraction
  ([xbmc/addons/AddonInstaller.cpp](https://github.com/xbmc/xbmc/blob/master/xbmc/addons/AddonInstaller.cpp):788-803).

## 3. Zip layout and naming

- Download URL is constructed, not discovered: for repo-sourced addons the path is
  `datadir/<id>/<id>-<version>.zip` — `URIUtils::AddFileToFolder(repo.datadir,
  addon->m_id, StringUtils::Format("{}-{}.zip", addon->m_id, addon->m_version.asString()))`
  (AddonInfoBuilder.cpp:384). The version string is the exact `version` attribute text, and
  URLs are matched byte-for-byte, so id and version casing/spelling must match addons.xml
  exactly (case-sensitive on any case-sensitive web host). An optional `<path>` element
  inside `kodi.addon.metadata` overrides this with `datadir/<path-text>`
  (AddonInfoBuilder.cpp:407-412).
- The zip **must contain exactly one top-level entry, and it must be a folder** containing
  a parseable `addon.xml`: `archivedFiles.Size() != 1 || !archivedFiles[0]->IsFolder() ||
  !...LoadAddonDescription(...)` fails the install (AddonInstaller.cpp:806-819; the same
  single-root-folder rule applies to manual "install from zip",
  AddonInstaller.cpp:489-514). Any stray root-level file (`.DS_Store`, `__MACOSX/`, a
  loose README) breaks installation.
- The extraction target is `special://home/addons/<addonId>` where `addonId` comes from
  the addon metadata, not from the folder name inside the zip
  ([xbmc/addons/FilesystemInstaller.cpp](https://github.com/xbmc/xbmc/blob/master/xbmc/addons/FilesystemInstaller.cpp):24-47,56-59
  — the single root folder's *contents* are copied). So Kodi itself tolerates a mismatched
  folder name, but the convention (and kodi-addon-checker's folder-id check) is that the
  folder equals the addon id. Use `<id>/` exactly.
- Symlinks: build zips with dereferencing (Python `zipfile.write()` follows symlinks and
  stores file content by default — safe). Exclude VCS/hidden files (`.git`, `.github`,
  `.gitignore`, editor droppings); they bloat zips and hidden *top-level* entries would
  violate the single-folder rule. kodi-addon-checker also flags blacklisted file types.

## 4. Datadir asset placement (icons/fanart before install)

- Modern Kodi (v17+) resolves art for not-yet-installed addons from the `<assets>` block
  inside each addons.xml entry, relative to `artdir/<addon.id>/` — and `artdir` defaults
  to `datadir` when not declared (Repository.cpp:308-312; AddonInfoBuilder.cpp:383
  `assetBasePath = URIUtils::AddFileToFolder(repo.artdir, addon->m_id)`, then
  icon/fanart/screenshot/banner/clearlogo/thumb are `assetBasePath + <element text>`,
  AddonInfoBuilder.cpp:432-471). So with `<assets><icon>icon.png</icon>
  <fanart>fanart.jpg</fanart></assets>`, the files must exist at
  `datadir/<addon.id>/icon.png` and `datadir/<addon.id>/fanart.jpg`. Asset text may
  contain subpaths (`resources/icon.png` → `datadir/<id>/resources/icon.png`).
- There is **no fallback** to implicit `icon.png`/`fanart.jpg` names for repo-sourced
  entries in current master — only `<assets>` paths are read (AddonInfoBuilder.cpp has no
  such default for repo content). Addons without `<assets>` simply show no art.
- The wiki's directory-structure section agrees: "each add-on directory should contain
  icon.png, fanart.jpg, changelog-x.y.z.txt and all files from the addon.xml `<assets>`
  element" ([wiki](https://kodi.wiki/view/Add-on_repositories) §Directory Structure).
- A copy of `addon.xml` in `datadir/<id>/` is conventional (many generators emit it) but
  nothing in Kodi fetches it — all metadata comes from addons.xml.

## 5. Multi-channel `<dir>` blocks

- Nothing channel-specific is needed beyond one `<dir>` per channel, each with its own
  `<info>`, `<checksum>`, `<datadir zip="true">` (the `zip` attribute is ignored since
  v17 — zips are assumed; [wiki](https://kodi.wiki/view/Add-on_repositories) §datadir) and
  optionally `<hashes>`.
- `minversion`/`maxversion` are attributes on `<dir>`, both optional, both **inclusive**,
  and are compared against the running Kodi's `xbmc.addon` API version (which tracks the
  major Kodi version, e.g. 21.x on Omega): `(minversion.empty() || version >= minversion)
  && (maxversion.empty() || version <= maxversion)` (Repository.cpp:102-117). Non-matching
  dirs are dropped at repo-addon load time, so each Kodi install only ever sees its own
  channel. `maxversion` exists since v19 (wiki §dir).
- Since v20 the `<dir>`-less flat form of the extension point is an error
  (Repository.cpp:119-128), so always use `<dir>` blocks.
- Because dir checksums are concatenated into one stored value, a change in any channel
  causes all matching dirs to be re-fetched — harmless, but give **every** dir a checksum
  or caching is disabled entirely (Repository.cpp:277-285).

## 6. kodi-addon-checker

Source: [github.com/xbmc/addon-check](https://github.com/xbmc/addon-check) (PyPI package
`kodi-addon-checker`, GPL-3.0-only, v0.0.36, last commit 2025-08-24 — maintained).

- Install: `pip install kodi-addon-checker`. Invoke: `kodi-addon-checker [dir ...]
  --branch <name>` (`kodi_addon_checker/__main__.py`).
- `--branch` is **required**; valid values (`ValidKodiVersions`,
  `kodi_addon_checker/__init__.py`): `gotham helix isengard jarvis krypton leia matrix
  nexus omega piers`.
- Many addons at once: there is **no `--all-repo-addons` flag**. If a given (or the
  current) directory has no top-level `addon.xml`, it is treated as a repo and every
  non-hidden top-level folder is checked (`check_repo.py`); you can also pass multiple
  addon dirs as positional args. (`get_all_repo_addons()` is an internal function that
  downloads `http://mirrors.kodi.tv/addons/{branch}/addons.xml.gz` for every branch at
  startup — the tool needs network even with `--skip-dependency-checks`.)
- Other flags: `--allow-folder-id-mismatch`, `--PR` (stricter news/changelog checks),
  `--skip-dependency-checks`, `--enable-debug-log` (writes `kodi-addon-checker.log`),
  `--reporter` (repeatable; built-ins: `console`, `array`, `log` —
  `kodi_addon_checker/plugins/`). No JSON-file output; the "array" reporter is in-process
  only, so CI should parse the console/log output or just rely on exit status.
- Exit codes: `1` if any PROBLEM records, `0` for warnings-only or clean
  (`__main__.py`). Per-repo config via `.tests-config.json` in the checked path can
  pre-set flags (`config.py`).
- Noise on legacy addons: artwork existence/size checks, blacklisted-string and
  blacklisted-filetype checks, complexity warnings on entrypoints, "addon already exists
  in official repo" branch checks (needs the mirrors download), invalid-PO checks. There
  is **no check for `[COLOR]` tags in the addon `name` attribute** (grep of the source
  finds no such rule), so that specific worry is unfounded. Folder/id mismatch is a
  PROBLEM unless `--allow-folder-id-mismatch`.

## 7. Prior art

- [xbmc/action-kodi-addon-checker](https://github.com/xbmc/action-kodi-addon-checker) —
  official Docker GitHub Action wrapping the checker. GPL-2.0, but last pushed 2020-04;
  its `action.yml` documents branches only up to matrix. Prefer `pip install
  kodi-addon-checker` directly in the workflow.
- [xbmc/action-kodi-addon-submitter](https://github.com/xbmc/action-kodi-addon-submitter)
  — Team Kodi action that opens PRs against the *official* repo-plugins/repo-scripts on
  tag; not a repository generator. Not applicable to a self-hosted repo.
- [chadparry/kodi-repository.chad.parry.org `tools/create_repository.py`](https://github.com/chadparry/kodi-repository.chad.parry.org/blob/master/tools/create_repository.py)
  — the script the wiki links; single file, stdlib except optional GitPython for git
  URLs; repo still pushed 2025-12 but has no declared license and emits a flat (single
  channel) layout.
- [drinfernoo/repository.example `_repo_generator.py`](https://github.com/drinfernoo/repository.example)
  — the widely-forked GitHub-Pages pattern: stdlib-only (`hashlib os shutil sys zipfile
  xml.etree`), per-Kodi-version subdirectories each with `addons.xml`, `addons.xml.md5`,
  and `zips/`. No license declared; last push 2024-07. Good structural reference, not
  reusable as a dependency.
- [jurialmunkey/repository.jurialmunkey](https://github.com/jurialmunkey/repository.jurialmunkey)
  (active 2026, `_repo_generator.py` + git submodules + `nexusrepo`/`omega` dirs, CI
  workflow `update_modules.yml`) and
  [CastagnaIT/repository.castagnait](https://github.com/CastagnaIT/repository.castagnait)
  (GPL-2.0, own `generator.py`, `kodi18`/`kodi19` dirs) both roll their own small
  generator scripts committed in-repo — nobody in this space consumes a shared
  marketplace action for generation.
- Conclusion: no maintained, licensed, reusable GitHub Action for datadir-style repo
  generation exists; the ecosystem norm (and our best fit) is a small stdlib-only script
  in-repo, invoked identically locally and from CI.

## Implications for our pipeline

1. Per channel dir (`main`, `21omega`, `22piers`), emit `addons.xml` (root `<addons>`,
   each addon's `addon.xml` body copied verbatim, UTF-8) and `addons.xml.md5` containing
   the bare lowercase hex MD5 of the exact bytes of `addons.xml` (bare hash is safest;
   `hash  filename` also works). Give every dir a checksum file.
2. Zips at `<channel>/<addon.id>/<addon.id>-<version>.zip`, version string byte-identical
   to the `version` attribute; each zip contains exactly one root folder `<addon.id>/`,
   no other root entries, symlinks dereferenced, VCS/hidden files excluded.
3. Copy `icon.png`, `fanart.jpg` (and any other `<assets>` files, preserving subpaths)
   into `<channel>/<addon.id>/` so art shows pre-install; ensure every addon.xml has an
   `<assets>` block — there is no filename fallback. Optionally copy `addon.xml` too
   (convention only).
4. Repository addon: `<dir minversion="20.9.0" maxversion="21.8.0">` / `<dir
   minversion="21.9.0" maxversion="22.8.0">` semantics are inclusive and match our plan;
   keep a bare `<dir>` for main. Omit `<hashes>` (or set `sha256` and also publish
   `<zip>.sha256` files); never rely on a `<hash>` element in addons.xml — none exists.
5. CI: `pip install kodi-addon-checker && kodi-addon-checker <addon-dir>... --branch
   omega` (and `--branch piers` for that channel); run against the sources root (no
   top-level addon.xml → repo mode) or list dirs explicitly; gate on exit code; expect it
   to need network for the mirrors addons.xml downloads; add `--allow-folder-id-mismatch`
   only if we ever rename source folders.
6. Write our own stdlib-only generator script shared by local runs and CI — matches
   ecosystem practice; no reusable third-party action worth adopting.
