from os import EX_UNAVAILABLE

from surfraw_tools.opensearch2elvis import main


def test_bad_url(caplog_cli_error, placeholder_elvis_name, placeholder_url):
    exit_code = main(
        [
            placeholder_elvis_name,
            placeholder_url,
        ]
    )

    assert (
        exit_code == EX_UNAVAILABLE
        and caplog_cli_error.records[0].getMessage()
        == "an error occurred while retrieving data from the network: [Errno -2] Name or service not known"
    )


# TODO: test bad OpenSearch descriptions
