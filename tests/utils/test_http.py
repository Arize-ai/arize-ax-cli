import pytest


@pytest.mark.unit
class TestVerifiedSslContext:
    """Certificate trust has to work under a uv-managed Python too."""

    def test_still_verifies(self) -> None:
        import ssl

        from ax.utils.http import verified_ssl_context

        ctx = verified_ssl_context()
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_uses_the_platform_trust_store(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ssl

        import truststore

        from ax.utils.http import verified_ssl_context

        expected = ssl.create_default_context()
        monkeypatch.setattr(truststore, "SSLContext", lambda _: expected)

        assert verified_ssl_context() is expected

    def test_survives_certifi_being_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import builtins
        import ssl

        from ax.utils.http import verified_ssl_context

        real_import = builtins.__import__

        def _no_certifi(name: str, *args: object, **kwargs: object) -> object:
            if name == "certifi":
                raise ImportError("gone")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _no_certifi)
        ctx = verified_ssl_context()

        assert ctx.verify_mode == ssl.CERT_REQUIRED
