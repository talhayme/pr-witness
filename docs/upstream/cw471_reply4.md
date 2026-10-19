You are right about the count, and my "six" was wrong — thank you for checking it. The full-commit run reports twelve high findings, nine of them `EXPECTED_VALUE_HARDCODED`:

| rule | count | units |
| --- | --- | --- |
| `EXPECTED_VALUE_HARDCODED` | 9 | `test_get_default_voice_any_language` (2), `test_resolve_case_insensitive` (2), `test_list_voices_returns_short_names`, `test_resolve_voice_with_language`, `test_default_voice`, `test_resolve_cached_voice`, `test_synthesize_result_metadata` |
| `ASSERT_SUBSTITUTED` | 2 | `test_resolve_case_insensitive` |
| `SUBJECT_INPUT_CHANGED` | 1 | `test_infer_language_returns_none` |

Plus fourteen at `warn` (twelve `EXPECTED_VALUE_CHANGED`, two `EXPECTED_VALUE_HARDCODED` — the latter are `test_resolve_from_api` and `test_resolve_short_name_from_api_with_descriptions`, which build the provider inside a `with` block rather than requesting the fixture). Your split of the nine into five direct and four through a local name matches what I see.

The `--format json` output you asked for is below: checkwash 0.8.0, `0a675b2..b4bc4e6`, the full commit, default settings.

<details>
<summary><code>checkwash check 0a675b2..b4bc4e6 --format json</code> (0.8.0, full commit)</summary>

```json
{
  "checkwash_findings_version": 2,
  "config_errors": [],
  "findings": [
    {
      "after": {
        "span": [
          1050,
          1114
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"MATILDA\") == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          1045,
          1107
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"RACHEL\") == \"rachel\""
      },
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "ASSERT_SUBSTITUTED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive/5d704b0b6be2",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive: an assertion was replaced by an unrelated one of the same strength (elevenlabs_provider.resolve_voice(\"RACHEL\") -> elevenlabs_provider.resolve_voice(\"MATILDA\")); the original assertion is gone and the strength lattice cannot see it",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "ASSERT_SUBSTITUTED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive"
    },
    {
      "after": {
        "span": [
          977,
          1041
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"Matilda\") == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          974,
          1036
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"Rachel\") == \"rachel\""
      },
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "ASSERT_SUBSTITUTED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive/c7f19f871372",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive: an assertion was replaced by an unrelated one of the same strength (elevenlabs_provider.resolve_voice(\"Rachel\") -> elevenlabs_provider.resolve_voice(\"Matilda\")); the original assertion is gone and the strength lattice cannot see it",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "ASSERT_SUBSTITUTED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive"
    },
    {
      "after": {
        "span": [
          11263,
          11326
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
          11335,
          11398
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
          11606,
          11632
        ],
        "text": "assert \"matilda\" in voices"
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderLanguageSupport.test_list_voices_returns_short_names/d9d6334167fd",
      "message": "TestElevenLabsProviderLanguageSupport.test_list_voices_returns_short_names: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderLanguageSupport.test_list_voices_returns_short_names"
    },
    {
      "after": {
        "span": [
          11113,
          11139
        ],
        "text": "assert result == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderLanguageSupport.test_resolve_voice_with_language/cd2e8e167567",
      "message": "TestElevenLabsProviderLanguageSupport.test_resolve_voice_with_language: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderLanguageSupport.test_resolve_voice_with_language"
    },
    {
      "after": {
        "span": [
          561,
          614
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
          833,
          859
        ],
        "text": "assert result == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_cached_voice/31eae7aea54d",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_cached_voice: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_cached_voice"
    },
    {
      "after": {
        "span": [
          1050,
          1114
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"MATILDA\") == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive/8ac7386cee5f",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive"
    },
    {
      "after": {
        "span": [
          977,
          1041
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"Matilda\") == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive/bcb435199116",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive"
    },
    {
      "after": {
        "span": [
          1942,
          1968
        ],
        "text": "assert result == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [
        "REPAIR_EVIDENCE"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_from_api/4231b63ff772",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_from_api: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_from_api"
    },
    {
      "after": {
        "span": [
          3020,
          3046
        ],
        "text": "assert result == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [
        "REPAIR_EVIDENCE"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_short_name_from_api_with_descriptions/8ab4d65ef034",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_short_name_from_api_with_descriptions: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_short_name_from_api_with_descriptions"
    },
    {
      "after": {
        "span": [
          4564,
          4596
        ],
        "text": "assert result.voice == \"matilda\""
      },
      "allowlisted": false,
      "before": null,
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "EXPECTED_VALUE_HARDCODED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderSynthesize.test_synthesize_result_metadata/53e15893c921",
      "message": "TestElevenLabsProviderSynthesize.test_synthesize_result_metadata: expected value 'matilda' equals a constant newly introduced in prod in this same diff",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_HARDCODED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderSynthesize.test_synthesize_result_metadata"
    },
    {
      "after": {
        "span": [
          11263,
          11326
        ],
        "text": "assert elevenlabs_provider.get_default_voice(\"de\") == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          11202,
          11264
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
          11335,
          11398
        ],
        "text": "assert elevenlabs_provider.get_default_voice(\"ja\") == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          11273,
          11335
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
          11606,
          11632
        ],
        "text": "assert \"matilda\" in voices"
      },
      "allowlisted": false,
      "before": {
        "span": [
          11543,
          11568
        ],
        "text": "assert \"rachel\" in voices"
      },
      "deescalators": [
        "PACKAGE_REPAIR"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderLanguageSupport.test_list_voices_returns_short_names/525592609745",
      "message": "TestElevenLabsProviderLanguageSupport.test_list_voices_returns_short_names: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderLanguageSupport.test_list_voices_returns_short_names"
    },
    {
      "after": {
        "span": [
          11113,
          11139
        ],
        "text": "assert result == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          11053,
          11078
        ],
        "text": "assert result == \"rachel\""
      },
      "deescalators": [
        "PACKAGE_REPAIR"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderLanguageSupport.test_resolve_voice_with_language/8b973f3f2c3e",
      "message": "TestElevenLabsProviderLanguageSupport.test_resolve_voice_with_language: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderLanguageSupport.test_resolve_voice_with_language"
    },
    {
      "after": {
        "span": [
          561,
          614
        ],
        "text": "assert elevenlabs_provider.default_voice == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          561,
          613
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
    },
    {
      "after": {
        "span": [
          833,
          859
        ],
        "text": "assert result == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          831,
          856
        ],
        "text": "assert result == \"rachel\""
      },
      "deescalators": [
        "PACKAGE_REPAIR"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_cached_voice/87c302785329",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_cached_voice: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_cached_voice"
    },
    {
      "after": {
        "span": [
          1050,
          1114
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"MATILDA\") == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          1045,
          1107
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"RACHEL\") == \"rachel\""
      },
      "deescalators": [
        "PACKAGE_REPAIR"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive/7e65bc3ce204",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive"
    },
    {
      "after": {
        "span": [
          977,
          1041
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"Matilda\") == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          974,
          1036
        ],
        "text": "assert elevenlabs_provider.resolve_voice(\"Rachel\") == \"rachel\""
      },
      "deescalators": [
        "PACKAGE_REPAIR"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive/9dd2418e36da",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_case_insensitive"
    },
    {
      "after": {
        "span": [
          1942,
          1968
        ],
        "text": "assert result == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          1934,
          1959
        ],
        "text": "assert result == \"rachel\""
      },
      "deescalators": [
        "REPAIR_EVIDENCE"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_from_api/61b3781bec64",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_from_api: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_from_api"
    },
    {
      "after": {
        "span": [
          3204,
          3260
        ],
        "text": "assert result2 == \"matilda - knowledgable, professional\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          3169,
          3210
        ],
        "text": "assert result2 == \"rachel - calm, gentle\""
      },
      "deescalators": [
        "REPAIR_EVIDENCE"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_short_name_from_api_with_descriptions/b074a80601ae",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_short_name_from_api_with_descriptions: expected value rewritten 'rachel - calm, gentle' -> 'matilda - knowledgable, professional' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_short_name_from_api_with_descriptions"
    },
    {
      "after": {
        "span": [
          3020,
          3046
        ],
        "text": "assert result == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          3001,
          3026
        ],
        "text": "assert result == \"rachel\""
      },
      "deescalators": [
        "REPAIR_EVIDENCE"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderResolveVoice.test_resolve_short_name_from_api_with_descriptions/e8ad31233f11",
      "message": "TestElevenLabsProviderResolveVoice.test_resolve_short_name_from_api_with_descriptions: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderResolveVoice.test_resolve_short_name_from_api_with_descriptions"
    },
    {
      "after": {
        "span": [
          4564,
          4596
        ],
        "text": "assert result.voice == \"matilda\""
      },
      "allowlisted": false,
      "before": {
        "span": [
          4512,
          4543
        ],
        "text": "assert result.voice == \"rachel\""
      },
      "deescalators": [
        "PACKAGE_REPAIR"
      ],
      "escalators": [],
      "fingerprint": "EXPECTED_VALUE_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderSynthesize.test_synthesize_result_metadata/12f4049ebee1",
      "message": "TestElevenLabsProviderSynthesize.test_synthesize_result_metadata: expected value rewritten 'rachel' -> 'matilda' with no change in assertion strength",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "EXPECTED_VALUE_CHANGED",
      "severity": "warn",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderSynthesize.test_synthesize_result_metadata"
    },
    {
      "after": {
        "span": [
          12264,
          12335
        ],
        "text": "assert elevenlabs_provider.infer_language_from_voice(\"matilda\") is None"
      },
      "allowlisted": false,
      "before": {
        "span": [
          12200,
          12270
        ],
        "text": "assert elevenlabs_provider.infer_language_from_voice(\"rachel\") is None"
      },
      "deescalators": [],
      "escalators": [
        "NO_PROD_CHANGE_IN_DIFF"
      ],
      "fingerprint": "SUBJECT_INPUT_CHANGED/tests/test_elevenlabs_provider.py/TestElevenLabsProviderLanguageSupport.test_infer_language_returns_none/16d5357dd02b",
      "message": "TestElevenLabsProviderLanguageSupport.test_infer_language_returns_none: the subject's input changed (argument 0: 'rachel' -> 'matilda') while the expected value stayed the same",
      "path": "tests/test_elevenlabs_provider.py",
      "rule": "SUBJECT_INPUT_CHANGED",
      "severity": "high",
      "shape": null,
      "strength_after": null,
      "strength_drop": null,
      "subject_changed": null,
      "unit": "TestElevenLabsProviderLanguageSupport.test_infer_language_returns_none"
    }
  ],
  "run": {
    "base": "0a675b2",
    "checkwash_version": "0.8.0",
    "head": "b4bc4e6"
  },
  "skipped_files": [],
  "summary": {
    "critical": 0,
    "high": 12,
    "info": 0,
    "warn": 14
  },
  "verdict": "block"
}
```

</details>

Yes, please use the three tests as a fixture in #522, written your way, and thank you for the credit. Understood on the rest: #522 is a draft and not in 0.8.0, the conftest's mock data stays the known gap, and the commit would still block under `fail_on = "warn"` or `oracle_freeze`.
