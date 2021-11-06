# SPDX-FileCopyrightText: 2021 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

from os import EX_USAGE

from surfraw_tools.mkelvis import main


def test_different_url_schemes(
    caplog_cli_error, placeholder_elvis_name, placeholder_domain
):
    exit_code = main(
        [
            placeholder_elvis_name,
            f"https://{placeholder_domain}",
            f"http://{placeholder_domain}",
        ]
    )

    assert (
        exit_code == EX_USAGE
        and caplog_cli_error.records[0].getMessage()
        == "the schemes of both URLs must be the same"
    )


# TODO: test option resolution errors... maybe for the library itself?
