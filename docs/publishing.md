# GitHub publishing and HACS

Scope: Solarman Azzurro 0.1.6. Development uses Forgejo; public GitHub distribution and inclusion in HACS's default catalog are separate activities. The [public GitHub repository](https://github.com/ctz23/solarman-azzurro) has independent history and the owner/name `ctz23/solarman-azzurro`. Publishing requires an explicit mandate and the checks below.

## Integration metadata

HACS downloads and updates component files. Configure the logger connection afterward in Home Assistant; see [Installation and configuration](installation.md) for fields and network requirements.

`hacs.json` declares the name and minimum `homeassistant: 2026.9.0`. The component lives under `custom_components/solarman_azzurro/`; neither `content_in_root` nor `zip_release` is required. Device addresses, serials and polling intervals belong to config entries, not HACS metadata or the manifest.

The manifest declares `config_flow: true`, `iot_class: local_polling`, no extra Python dependencies, public GitHub documentation/issue URLs and `codeowners: ["@ctz23"]`. Verify these before publication and run the validators. Default-catalog submission requires a complete GitHub release. Custom-repository installation can also use the default branch; see [HACS integration requirements](https://hacs.xyz/docs/publish/integration/).

Repository prose, source comments, default labels, issue templates and release notes use English. Other UI languages belong in `translations/`. Legacy identifiers remain stable for existing entities and history.

## Public and private files

HACS installs the component directory. The public repository also includes documentation and tests for users and reviewers.

| Path or material | Public GitHub | Installed by HACS | Rule |
| --- | --- | --- | --- |
| `custom_components/solarman_azzurro/` | Yes | Yes | Component code, translations, manifest and icons. |
| `hacs.json`, `README.md`, `LICENSE`, `.gitignore`, `pyproject.toml` | Yes | No | Metadata, presentation, license and shared repository rules. |
| `docs/` | Yes | No | Product guides, event catalog, publishing guide and icon source. |
| `tests/` | Yes | No | Synthetic tests and fixtures; no real household dumps. |
| `tools/` | Yes | No | Reusable development tools, currently the icon generator. |
| `.github/workflows/`, `.github/ISSUE_TEMPLATE/` | Yes | No | Tests, Hassfest, HACS validation and issue forms. |
| `.env*`, `secrets.yaml`, private keys/certificates | No | No | Ignored; `.env.example` is permitted only with synthetic values. |
| Real HA configuration, `.storage/`, Recorder databases | No | No | Keep in operational storage and private backups. |
| `local/`, `private/`, backups, logs and real evidence | No | No | Ignored; retain useful reports in operational storage. |
| Caches, virtual environments and build outputs | No | No | Ignored. |

`.gitignore` applies to both remotes and only to untracked files. It neither removes files from existing commits nor filters a push by destination. Do not force-add private material.

HACS already selects the component, so documentation and tests need no `export-ignore`. Git export attributes affect generated archives, not remote visibility or history. Keep development and public repositories separate; synchronize reviewed public files while preserving independent public history. A second remote on the same branch would receive the same reachable commits.

### Checks before each publication

```sh
git status --short
git ls-files
git ls-files --cached --ignored --exclude-standard
git diff --check
```

The third command must produce no output. This alone does not prove content or history contains no secrets; inspect both. Check exclusion rules without creating private files:

```sh
git check-ignore -v --no-index local/logger.json .env ha-config/.storage/core.config_entries home-assistant_v2.db
```

Private development history includes local infrastructure references. Never import its `.git`, commits, tags or refs into the public repository. Keep that history in Forgejo. See [Git ignore rules](https://git-scm.com/docs/gitignore) and [Git attributes](https://git-scm.com/docs/gitattributes).

## Initialize independent public history

These steps apply only to the initial publication. Update the existing public checkout for subsequent releases.

1. Create a new publishing directory and explicitly copy only `.gitignore`, `LICENSE`, `README.md`, `hacs.json`, `pyproject.toml`, the component, `docs/`, `tests/`, `tools/` and `.github/`. Exclude caches, private/ignored files, symlinks and the original `.git`.
2. Verify the manifest's public HTTPS URLs and actual maintainer. Keep the domain, register profile and supported behavior intact.
3. Review all copied files for tokens, private HA configuration, household addresses/serials, Recorder dumps and registries. Test fixtures must be synthetic.
4. Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`, local-link checks and `git diff --check`. Run Ruff and `pytest tests/ha -q` using the Python 3.14 environment described in [Development](development.md). Hardware verification and actual HACS installation remain separate checks.
5. Initialize with `git init --initial-branch=main --template=`, configure the author and a `noreply` address locally, then commit reviewed files. Do not clone, fetch or merge the private repository to initialize this history.

Check the initial state:

```sh
git rev-list --all --count
git rev-list --max-parents=0 --all
git for-each-ref --format='%(refname)'
git fsck --full
git status --short
```

At first initialization, expect one commit, one root and only `refs/heads/main`; object checks must pass and the working tree must be clean. Subsequent updates add independently created public commits without importing private history.

## Publish to GitHub

From the independent public checkout, using authenticated GitHub CLI and a verified owner:

```sh
GITHUB_OWNER="ctz23"
# Initial publication only; skip creation if the repository already exists.
gh repo create "$GITHUB_OWNER/solarman-azzurro" --public --description "Local read-only Solarman V5 telemetry for supported ZCS Azzurro HYD HP inverters"
# Add this remote only if it is absent.
git remote add github "https://github.com/$GITHUB_OWNER/solarman-azzurro.git"
git push github main:main
```

Verify `git remote -v` before pushing. Only the public checkout uses the GitHub remote; Forgejo remains in the development repository. Push the selected branch; avoid mirror, all-branch or force pushes.

## Validation and releases

The repository's `tests.yml` and `validate.yml` workflows run Python tests, Ruff, Hassfest and HACS Action. All jobs must pass without exclusions before a release. Standalone unittest exercises synthetic TCP/UDP; the HA pytest job retains the framework's network blocking.

Set an English description, enable Issues and add relevant topics (`home-assistant`, `hacs`, `solarman`, `azzurro`, `solar`). Match the manifest version and tag. Create a complete GitHub release with the supported profile, changes, limitations and update instructions. Identify experimental releases as such.

For the current version, after checks and publication authorization:

```sh
git tag -a v0.1.6 -m "Solarman Azzurro 0.1.6"
git push github v0.1.6
gh release create v0.1.6 --repo "$GITHUB_OWNER/solarman-azzurro" --title "Solarman Azzurro 0.1.6" --generate-notes
```

If the tag or release exists, verify it instead of overwriting it. HACS uses the repository layout; a separately prepared ZIP is unnecessary.

## HACS installation and default catalog

For custom-repository installation, add the GitHub URL under HACS → **Custom repositories**, category **Integration**, download, restart Home Assistant and add **Solarman Azzurro** under **Settings → Devices & services**. HACS does not install directly from Forgejo. Verify download location and that updates retain config entries and entity IDs.

For default-catalog inclusion, first verify a complete release and custom-repository installation, then follow the current [HACS inclusion procedure](https://hacs.xyz/docs/publish/include/): a personal fork of `hacs/default`, a branch from the required base, the repository name in alphabetical order in `integration`, and a PR from the owner or major contributor. Complete its template, allow maintainer edits and pass all checks. Inclusion requires HACS review and is not automatic.

## Local icon

`docs/icon.svg` is the original source. `python3 tools/generate_brand.py` uses ImageMagick, a development-only dependency, to generate the component's `brand/icon.png` and `brand/icon@2x.png`. HA supports local custom-integration brand assets from 2026.3; this project requires at least 2026.9. A PR to the old brands repository is unnecessary for these assets.

## Official references

- [HACS integration requirements](https://hacs.xyz/docs/publish/integration/)
- [HACS inclusion procedure](https://hacs.xyz/docs/publish/include/)
- [HACS Action](https://hacs.xyz/docs/publish/action/)
- [HACS custom repositories](https://hacs.xyz/docs/faq/custom_repositories/)
- [Home Assistant local brand assets](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/)
- [Home Assistant entity naming and translations](https://developers.home-assistant.io/docs/core/entity/#entity-naming)

Publishing rules can change; recheck official references when preparing a release.
