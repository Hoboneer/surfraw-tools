from contextlib import redirect_stdout
from io import StringIO

from surfraw_tools.mkelvis import main


def test_preserve_open_query_string(
    caplog_cli_error, placeholder_elvis_name, placeholder_domain
):
    base_url = f"http://{placeholder_domain}"
    search_url = base_url + "?"

    buf = StringIO()
    with redirect_stdout(buf):
        main([placeholder_elvis_name, "--output", "-", base_url, search_url])

    buf.seek(0)
    preserved_open_query_string = False
    for line in buf:
        if line.strip() == f'search_url="{search_url}"':
            preserved_open_query_string = True
            break
    assert preserved_open_query_string
