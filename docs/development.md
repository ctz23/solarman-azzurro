# Development and verification

Scope: the experimental 0.1.6 integration and standalone transport/profile tests.

## Local checks

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` from the repository. These tests need only the Python standard library; the public suite contains synthetic register fixtures and mock TCP servers, not household addresses, serials or measurements.

Protocol tests cover persistent session reuse across snapshots, ordered concurrent calls, idle heartbeat acknowledgements without polling, late reply rejection, peer close/reconnect, explicit close and cancellation, fragmented TCP replies, short valid V5 control packets between register windows, bounded heartbeat floods, invalid control-packet checksums/identities, identity/checksum/CRC corruption, exceptions, incomplete transactions, transient retry on a new connection, rejection of partial attempts, persistent timeouts, cancellation and recovery. Profile tests cover energy word order, signed import/export and battery directions, day reset, invalid/sentinel values, alarm bits and derived values.

Run the Home Assistant suite with Python 3.14 after installing `tests/requirements-ha.txt` in an isolated environment:

```sh
python -m pip install -r tests/requirements-ha.txt
ruff check --no-cache custom_components tests
pytest tests/ha -q
```

The pinned framework uses Home Assistant 2026.9.4. The suite checks real config flows, discovery selection, duplicate protection, reconfiguration, options reload, English/Italian names, preservation of all 53 existing entity identities and custom names, unload, unavailable/recovery behavior, diagnostics redaction and separate fast/full polling and the 1-second minimum. Keep the mock TCP/UDP suite in the separate unittest job: Home Assistant's pytest framework blocks network sockets by default. Live cadence and hardware behavior still require a compatible installation; runtime checks and private migration evidence belong outside this public repository.

## Translations (i18n)

English is the source language in `custom_components/solarman_azzurro/strings.json`; `translations/en.json` mirrors it. `translations/it.json` supplies Italian setup, options, error/abort messages, logger selection and all 53 entity labels. Home Assistant handles localization through translation keys; do not hardcode translated labels in Python. Entity names use the backend language rather than an individual user's frontend language. Existing entity IDs and user-assigned names remain stable.

Translation improvements and additional languages are welcome through GitHub pull requests:

1. Copy `custom_components/solarman_azzurro/translations/en.json` to `translations/<language-code>.json`, or improve an existing language file.
2. Translate text values while retaining the same keys, structure, placeholders and stable identifiers. Include configuration, options, selector labels and every entity name. Keep `strings.json` and the English translation aligned when changing source text.
3. Validate the JSON and run the checks described above. Review forms in Home Assistant with the new UI language and entity labels with the corresponding backend language, preferably using a separate test instance. Translation changes must preserve entity identities and custom names; the Home Assistant suite covers these invariants for English and Italian.
4. Open a pull request describing the language and the checks you performed. Keep repository documentation and the PR description in English.

Raw measurement keys and legacy flow states are compatibility identifiers; keep them unchanged. Free-text event descriptions currently come from the English event catalog, independently of localized entity labels.

## Boundaries

Only FC03 reads exist in the client. No service, button, switch, number or code path writes registers or logger settings. No cloud fallback is used. Add other models through explicit tested profiles instead of widening this profile speculatively.

Never commit real HA registries, configuration, tokens, private serials or device addresses. The MIT license covers this independent implementation. Do not claim official ZCS/Sofar affiliation or general compatibility beyond the tested profile.
