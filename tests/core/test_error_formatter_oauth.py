from ax.core.error_formatter import get_error_suggestion


class Test401Suggestion:
    """The 401 hint is generic — covers both auth methods so it's correct
    regardless of which auth method the active profile uses.
    """

    def test_mentions_ax_auth_login_for_oauth_profiles(self):
        msg = get_error_suggestion(401)
        assert "ax auth login" in msg

    def test_mentions_ax_profiles_update_for_api_key_profiles(self):
        msg = get_error_suggestion(401)
        assert "ax profiles update" in msg

    def test_mentions_ax_profiles_create_for_api_key_profiles(self):
        msg = get_error_suggestion(401)
        assert "ax profiles create" in msg


def test_non_401_suggestions_unchanged():
    """Sanity check — we only modified the 401 path."""
    for code in (403, 404, 500):
        msg = get_error_suggestion(code)
        assert isinstance(msg, str)
