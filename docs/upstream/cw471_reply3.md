All three read `elevenlabs_provider` directly, as the fixture parameter. None calls a module-level function. Before the commit (parent 0a675b2), `tests/test_elevenlabs_provider.py`:

```python
class TestElevenLabsProviderResolveVoice:
    def test_resolve_case_insensitive(
        self, elevenlabs_provider: ElevenLabsProvider
    ) -> None:
        assert elevenlabs_provider.resolve_voice("Rachel") == "rachel"   # ASSERT_SUBSTITUTED 1
        assert elevenlabs_provider.resolve_voice("RACHEL") == "rachel"   # ASSERT_SUBSTITUTED 2

class TestElevenLabsProviderLanguageSupport:
    def test_infer_language_returns_none(
        self, elevenlabs_provider: ElevenLabsProvider
    ) -> None:
        assert elevenlabs_provider.infer_language_from_voice("rachel") is None   # SUBJECT_INPUT_CHANGED
```

The commit rewrites the two `resolve_voice` lines to `"Matilda"`/`"MATILDA"` `== "matilda"` and the `infer_language_from_voice` argument to `"matilda"`; the receiver stays `elevenlabs_provider` on both sides. The fixture is the one you read:

```python
@pytest.fixture
def elevenlabs_provider(mock_elevenlabs_client: MagicMock) -> ElevenLabsProvider:
    return ElevenLabsProvider(client=mock_elevenlabs_client)
```

For completeness, the same file has two tests that bind a local name instead: `test_resolve_from_api` and `test_resolve_short_name_from_api_with_descriptions` build `provider = ElevenLabsProvider(client=...)` inside a `with` block and assert on `provider.resolve_voice(...)`. Those are the two `warn` `EXPECTED_VALUE_HARDCODED` findings in the 0.8.0 output, not among the high ones, so they do not affect the verdict either way.

So by the ruled rule, all nine high findings on this commit (six `EXPECTED_VALUE_HARDCODED`, the two `ASSERT_SUBSTITUTED`, the one `SUBJECT_INPUT_CHANGED`) read the fixture's value directly, and the commit would pass at the default settings. Thanks for the correction about #425; understood that the fixture-data part stays a known gap.
