import logging

import pytest


@pytest.fixture
def placeholder_elvis_name():
    return "placeholder"


@pytest.fixture
def placeholder_domain():
    return "example.com"


@pytest.fixture
def placeholder_url(placeholder_domain):
    return f"https://{placeholder_domain}"


@pytest.fixture
def caplog_cli_error(caplog):
    caplog.set_level(logging.CRITICAL)
    return caplog
