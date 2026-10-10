# Where reality differed from the plan

The plan (`pr-witness-plan.pdf`, v1.0, 10 Oct 2026) asked for every
external fact to be checked against current documentation and every
discrepancy written down. This is that list.

## Phase 5 — signing

| Plan said | Checked on 10 Oct 2026 |
|---|---|
| "action for attestations with custom predicate; verify current name and version" | `actions/attest@v4` (latest release v4.2.2). Custom mode is selected by passing `predicate-type` + `predicate-path` (or `predicate`); `subject-path` names the file being attested. `actions/attest-build-provenance` is a different action for SLSA provenance only. |
| permissions unspecified | The action's README asks for `id-token: write`, `attestations: write`, **`artifact-metadata: write`**. The docs page "Use artifact attestations" lists `id-token: write`, `contents: read`, `attestations: write` and omits `artifact-metadata`. The README is the newer source; the example workflow grants all of them. |
| nothing about plans or visibility | **Attestations work in public repositories on every plan. Private and internal repositories need GitHub Enterprise Cloud. Not supported on Enterprise Server at all.** The plan assumed signing is universally available; it is not. The action treats a failed signing step as a warning, and the comment says "Unsigned" with the reason, so a private-repo user still gets the report. |
| "проверка — `gh attestation verify`" | Confirmed. Needs the artifact locally plus `--repo owner/name` (or `--owner`), and `--predicate-type <uri>` because the default is SLSA provenance. |

## Phase 2 — diff integrity

| Plan said | Checked |
|---|---|
| checkwash is "v0.5, weak JS/TS"; ten JS/TS detectors to write | 0.6.0 on PyPI. Seven of the ten already work (measured, see `docs/upstream/README.md`). Three real gaps remain; one is filed as [checkwash#363](https://github.com/taipei49314/checkwash/issues/363). |
| "Подключить checkwash как зависимость" | Done, with one deliberate disagreement: checkwash blocks on any added skip marker; pr-witness downgrades a skip whose reason names an issue, and the report says so rather than hiding the finding. |

## Phase 1 — counters

| Plan said | Checked |
|---|---|
| "Флаг, если collected уменьшился" | Not runner-portable. `describe.only` in vitest leaves the collected count unchanged and reports the hidden tests as `skipped`; pytest's `testpaths` narrowing shrinks the count. The denominator check compares the set of tests that *ran*, by identity, not a total. |

## Phase 0 — corpus

| Plan said | Checked |
|---|---|
| "Минимум 40 случаев на старте" | 17. The corpus stopped discriminating between phases at that size (recall 1.00 since phase 3), which says more about the corpus than the tool. Growing it — ideally with real, licence-checked cases — is the single most valuable thing left to do. |
| "Найденные ошибки checkwash оформить как issues" | One filed, two drafted and held; see `docs/upstream/`. |

## Phase 4 — Action

| Plan said | Checked |
|---|---|
| `uses: <user>/pr-witness@<SHA>` | Composite action syntax verified: every `run` step needs `shell:`; steps may `uses:` other actions with `with:`, `if:`, `env:`, `continue-on-error:`. `gh pr comment --edit-last --create-if-none` exists and is what keeps the thread to one comment. |
| "require-ack — статус «нейтральный»" | A composite action cannot set a neutral check status; that needs the Checks API and a GitHub App. `require-ack` fails the job until the label is present, which is the closest honest equivalent. |
