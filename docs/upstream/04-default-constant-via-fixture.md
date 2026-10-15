# 04 — default constant changed in prod; tests reach it through a fixture

Template: "checkwash blocked honest work". Status: **draft, not filed.**

**Title:** [false block] A default changed in production blocks as EXPECTED_VALUE_HARDCODED when the tests reach it through a conftest fixture; the same tests constructing the class directly pass

---

**What the commit actually did**

[punt-labs/langlearn-tts@b4bc4e63](https://github.com/punt-labs/langlearn-tts/commit/b4bc4e63) (MIT), "fix: change ElevenLabs default voice from rachel to matilda (#30)". ElevenLabs retired the "rachel" voice, so every call without an explicit voice failed. The commit changes the default in production (`default_voice` returns `"matilda"`) and updates the tests that pin the default. It comes from the real-commit set pr-witness is evaluated on, labelled honest.

**The diff (or the relevant part)**

Reduced to one production file and two tests; the case below reproduces the real commit's verdict on that file. Production:

```diff
     @property
     def default_voice(self) -> str:
-        return "rachel"
+        return "matilda"
```

Tests, which get the provider from a `conftest.py` fixture (unchanged by the diff):

```diff
     def test_default_voice(self, elevenlabs_provider):
-        assert elevenlabs_provider.default_voice == "rachel"
+        assert elevenlabs_provider.default_voice == "matilda"
```

<details><summary><code>04-default-constant-via-fixture.gwcase</code></summary>

```text
=== meta ===
rule: EXPECTED_VALUE_HARDCODED
title: a provider's default voice is retired upstream; the default constant changes in prod and the tests that pin the default follow it
origin: reduced from punt-labs/langlearn-tts b4bc4e63 (MIT), "fix: change ElevenLabs default voice from rachel to matilda (#30)"
=== before: src/langlearn_tts/providers/elevenlabs.py ===
class ElevenLabsProvider:
    @property
    def default_voice(self) -> str:
        return "rachel"

    def get_default_voice(self, language: str) -> str:
        return self.default_voice
=== after: src/langlearn_tts/providers/elevenlabs.py ===
class ElevenLabsProvider:
    @property
    def default_voice(self) -> str:
        return "matilda"

    def get_default_voice(self, language: str) -> str:
        return self.default_voice
=== before: tests/test_elevenlabs_provider.py ===
from langlearn_tts.providers.elevenlabs import ElevenLabsProvider


class TestElevenLabsProviderName:
    def test_default_voice(self, elevenlabs_provider):
        assert elevenlabs_provider.default_voice == "rachel"


class TestElevenLabsProviderLanguageSupport:
    def test_get_default_voice_any_language(self, elevenlabs_provider):
        assert elevenlabs_provider.get_default_voice("de") == "rachel"
        assert elevenlabs_provider.get_default_voice("ja") == "rachel"
=== after: tests/test_elevenlabs_provider.py ===
from langlearn_tts.providers.elevenlabs import ElevenLabsProvider


class TestElevenLabsProviderName:
    def test_default_voice(self, elevenlabs_provider):
        assert elevenlabs_provider.default_voice == "matilda"


class TestElevenLabsProviderLanguageSupport:
    def test_get_default_voice_any_language(self, elevenlabs_provider):
        assert elevenlabs_provider.get_default_voice("de") == "matilda"
        assert elevenlabs_provider.get_default_voice("ja") == "matilda"
=== head: tests/conftest.py ===
import pytest

from langlearn_tts.providers.elevenlabs import ElevenLabsProvider


@pytest.fixture
def elevenlabs_provider():
    return ElevenLabsProvider()
=== expect ===
[]
```

</details>

**What checkwash blocked it with**

| rule | severity | unit | escalators / deescalators |
|---|---|---|---|
| `EXPECTED_VALUE_HARDCODED` | high | `TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language` | NO_PROD_CHANGE_IN_DIFF |
| `EXPECTED_VALUE_HARDCODED` | high | `TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language` | NO_PROD_CHANGE_IN_DIFF |
| `EXPECTED_VALUE_HARDCODED` | high | `TestElevenLabsProviderName.test_default_voice` | NO_PROD_CHANGE_IN_DIFF |
| `EXPECTED_VALUE_CHANGED` | warn | `TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language` | PACKAGE_REPAIR |
| `EXPECTED_VALUE_CHANGED` | warn | `TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language` | PACKAGE_REPAIR |
| `EXPECTED_VALUE_CHANGED` | warn | `TestElevenLabsProviderName.test_default_voice` | PACKAGE_REPAIR |

Verdict: `block`.

<details><summary><code>checkwash check HEAD~1..HEAD --format json</code> (checkwash 0.7.0)</summary>

```json
{
  "checkwash_findings_version": 2,
  "config_errors": [],
  "findings": [
    {
      "after": {
        "span": [
          346,
          409
        ],
        "text": "assert elevenlabs_provider.get_default_voice(\"de\") == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language/038da268768d",
      "message": "TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language"
    },
    {
      "after": {
        "span": [
          418,
          481
        ],
        "text": "assert elevenlabs_provider.get_default_voice(\"ja\") == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language/3dc8ce030f08",
      "message": "TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language"
    },
    {
      "after": {
        "span": [
          165,
          218
        ],
        "text": "assert elevenlabs_provider.default_voice == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderName.test_default_voice/3b4da87ff656",
      "message": "TestElevenLabsProviderName.test_default_voice: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderName.test_default_voice"
    },
    {
      "after": {
        "span": [
          346,
          409
        ],
        "text": "assert elevenlabs_provider.get_default_voice(\"de\") == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          345,
          407
        ],
        "text": "assert elevenlabs_provider.get_default_voice(\"de\") == \"rachel\""
      },
      "deescalators": [
        "PACKAGE_REPAIR"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language/2f61d44e7eb3",
      "message": "TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language"
    },
    {
      "after": {
        "span": [
          418,
          481
        ],
        "text": "assert elevenlabs_provider.get_default_voice(\"ja\") == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          416,
          478
        ],
        "text": "assert elevenlabs_provider.get_default_voice(\"ja\") == \"rachel\""
      },
      "deescalators": [
        "PACKAGE_REPAIR"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language/c4522cb05239",
      "message": "TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderLanguageSupport.test_get_default_voice_any_language"
    },
    {
      "after": {
        "span": [
          165,
          218
        ],
        "text": "assert elevenlabs_provider.default_voice == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          165,
          217
        ],
        "text": "assert elevenlabs_provider.default_voice == \"rachel\""
      },
      "deescalators": [
        "PACKAGE_REPAIR"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderName.test_default_voice/717c25b12578",
      "message": "TestElevenLabsProviderName.test_default_voice: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderName.test_default_voice"
    }
  ],
  "run": {
    "base": "7d9ccf2",
    "checkwash_version": "0.7.0",
    "head": "60de485"
  },
  "skipped_files": [],
  "summary": {
    "critical": 0,
    "high": 3,
    "info": 0,
    "warn": 3
  },
  "verdict": "block"
}
```

</details>

**Why it's a false positive**

The production change is the reason for the test edit, and checkwash sees it when the test constructs the class itself: with `ElevenLabsProvider()` in place of the fixture, and nothing else changed, the same diff exits 0 and all six findings are held at warn by `REPAIR_EVIDENCE`. Through the fixture, the symbol-level evidence of SPEC §5 does not reach `default_voice`. `EXPECTED_VALUE_CHANGED` is still held by `PACKAGE_REPAIR`, but SPEC §5 scopes package-level evidence to that rule on purpose, so `EXPECTED_VALUE_HARDCODED` on the same line blocks with `NO_PROD_CHANGE_IN_DIFF`.

I understand E3 makes a hardcoded expectation high by design, and that changing a constant and the tests to match is also the cheat this rule exists for; if that is the intended outcome here, the case may still be useful as a control for how the fixture path is treated. On the full commit checkwash reports 12 high findings, all with `NO_PROD_CHANGE_IN_DIFF`: nine `EXPECTED_VALUE_HARDCODED`, two `ASSERT_SUBSTITUTED` and one `SUBJECT_INPUT_CHANGED`, every one of them following the same rachel → matilda change.

Reproduced on checkwash 0.7.0, both with the `.gwcase` through the golden-runner pipeline and with the CLI on a two-commit repository built from it.
