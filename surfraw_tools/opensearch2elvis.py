from __future__ import annotations

import argparse
import logging
import re
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from os import EX_DATAERR, EX_OK, EX_OSERR, EX_UNAVAILABLE, EX_USAGE
from typing import (
    IO,
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)
from urllib.error import URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

if TYPE_CHECKING:
    from typing_extensions import Final

# No stubs.
from lxml import etree as et  # type: ignore

from surfraw_tools.lib.common import (
    BASE_PARSER,
    _ElvisName,
    parse_elvis_name,
    setup_cli,
)
from surfraw_tools.lib.elvis import Elvis
from surfraw_tools.lib.options import (
    SurfrawAnything,
    SurfrawEnum,
    SurfrawVarOption,
)

PROGRAM_NAME: Final = "opensearch2elvis"


def _get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        PROGRAM_NAME,
        description="generate an elvis for an OpenSearch-enabled website (v1.1, Draft 6)",
        parents=[BASE_PARSER],
    )
    parser.add_argument(
        "name", type=parse_elvis_name, help="name for the elvis"
    )
    parser.add_argument(
        "file_or_url",
        help="local OpenSearch description file or any URL on the website",
    )
    return parser


class OpenSearchContext(argparse.Namespace):
    def __init__(self) -> None:
        self.name: _ElvisName = _ElvisName("DEFAULT")
        self.file_or_url: str = ""


class OpenSearchParameter(argparse.Namespace):
    def __init__(
        self,
        name: str,
        optional: bool,
        span: Tuple[int, int],
        prefix: Optional[str] = None,
    ):
        self.name: Final = name
        self.optional: Final = optional
        self.span: Final = span
        self.prefix: Final = prefix


_TEMPLATE_PARAM_RE: Final = re.compile(
    r"{(?:(?P<prefix>):)?(?P<name>[^:&=/?]+)(?P<optional>\?)?}"
)


class OpenSearchURLTemplate(argparse.Namespace):
    def __init__(self, template: str):
        self.raw: Final = template
        # extract params from template
        # This assmumes that no duplicates exist
        # TODO: Handle empty matches
        # TODO: Check if prefix matches declared namespace
        #       DON'T handle this for now.
        matches = re.finditer(_TEMPLATE_PARAM_RE, self.raw)
        self.params: Final = [
            OpenSearchParameter(
                match.group("name"),
                bool(match.group("optional")),
                match.span(),
                match.group("prefix"),
            )
            for match in matches
        ]
        self.params_map: Final = {param.name: param for param in self.params}
        if len(self.params) != len(self.params_map):
            # TODO: remove this restriction?
            raise ValueError(
                "parameters may only be used once per template URL"
            )
        # Check special params
        if (
            self.params_map.get("searchTerms") is None
            or self.params_map["searchTerms"].optional
        ):
            raise ValueError(
                "the searchTerms parameter must exist and must *not* be optional"
            )

    def get_surfraw_template(
        self,
        namespacer: Callable[[str], str],
        varname_map: Optional[Mapping[str, str]] = None,
    ) -> str:
        # Collected in order of occurrence
        names_to_vars = {
            "searchTerms": "${_}",
        }
        if varname_map:
            names_to_vars.update(varname_map)
        new_template = self.raw
        for param in self.params:
            # Slow, but it works
            new_template = re.sub(
                _TEMPLATE_PARAM_RE,
                names_to_vars[param.name],
                new_template,
                count=1,
            )
        return new_template


class OpenSearchURL(argparse.Namespace):
    def __init__(
        self,
        *,
        template: str,
        type: str,
        rel: str = "results",
        index_offset: int = 1,
        page_offset: int = 1,
    ):
        self.template: Final = OpenSearchURLTemplate(template)
        self.type: Final = type
        self.rels: Final = rel.split(" ")
        self.index_offset: Final = index_offset
        self.page_offset: Final = page_offset

    @property
    def params(self) -> List[OpenSearchParameter]:
        return self.template.params


# NS_OPENSEARCH_1_0: Final = ""
NS_OPENSEARCH_1_1: Final = "http://a9.com/-/spec/opensearch/1.1/"


def _get_opensearch_prefix(
    prefix_map: Mapping[Optional[str], str]
) -> Union[str, None]:
    for prefix, namespace in prefix_map.items():
        if namespace == NS_OPENSEARCH_1_1:
            return prefix
    raise ValueError


class OpenSearchDescription(argparse.Namespace):
    def __init__(self, file: IO[bytes]):
        self._xml: Final = et.parse(file)
        self._root: Final = self._xml.getroot()
        root_qname = et.QName(self._root.tag)
        if root_qname != et.QName(NS_OPENSEARCH_1_1, "OpenSearchDescription"):
            # TODO: say bare namespace of root needs to be the 1.1 namespace?
            raise ValueError(
                "only OpenSearch version 1.1 descriptions are supported"
            )

        # self.raw_shortname: Final = self._root.find(
        #    et.QName(NS_OPENSEARCH_1_1, "ShortName")
        # ).text
        # self.shortname: Final = self.raw_shortname.replace(" ", "").lower()
        self.description: Final = self._root.find(
            et.QName(NS_OPENSEARCH_1_1, "Description")
        ).text

        self.urls: Final[List[OpenSearchURL]] = []
        for url_elem in self._root.xpath(
            "os:Url[@template and @type]", namespaces={"os": NS_OPENSEARCH_1_1}
        ):
            os_url = OpenSearchURL(
                template=cast(str, url_elem.get("template")),
                type=cast(str, url_elem.get("type")),
                rel=url_elem.get("rel", "results"),
                index_offset=int(url_elem.get("indexOffset", "1")),
                page_offset=int(url_elem.get("pageOffset", "1")),
            )
            correct_prefix = _get_opensearch_prefix(url_elem.nsmap)
            # Whether the template parameters use the right prefix (for the namespace)
            for param in os_url.template.params:
                # unqualified params (`None` prefix) implicitly have opensearch namespace
                if param.prefix != correct_prefix or param.prefix is not None:
                    raise ValueError(
                        "only OpenSearch parameters are supported at the moment"
                    )
            self.urls.append(os_url)
        if not self.urls:
            raise ValueError("no Url elements found in OpenSearch description")

        # For ease of access
        self.search_url: OpenSearchURL
        self.json_suggestions_url = None
        self.xml_suggestions_url = None
        for url in self.urls:
            if url.type == "text/html":
                self.search_url = url
            elif (
                url.type == "application/json" and "suggestions" in url.rels
            ) or url.type == "application/x-suggestions+json":
                self.json_suggestions_url = url
            elif (
                url.type == "application/xml" and "suggestions" in url.rels
            ) or url.type == "application/x-suggestions+xml":
                self.xml_suggestions_url = url
        if not hasattr(self, "search_url"):
            raise ValueError("search url must exist")

        # Should they be validated?
        self.languages: List[str] = [
            elem.text for elem in self._root.findall("Language")
        ]
        self.input_encodings: List[str] = [
            elem.text for elem in self._root.findall("InputEncoding")
        ]
        self.output_encodings: List[str] = [
            elem.text for elem in self._root.findall("OutputEncoding")
        ]


@contextmanager
def _handle_opensearch_errors(log: logging.Logger) -> Iterator[None]:
    try:
        yield
    except et.LxmlSyntaxError as e:
        log.critical(
            f"an error occurred while parsing XML: {e}",
        )
        sys.exit(EX_DATAERR)
    except URLError as e:
        log.critical(
            f"an error occurred while retrieving data from the network: {e}",
        )
        sys.exit(EX_UNAVAILABLE)
    except (OSError, Exception) as e:
        log.critical(f"{e}")
        sys.exit(EX_UNAVAILABLE)


def main(argv: Optional[List[str]] = None) -> int:
    ctx, log = setup_cli(
        PROGRAM_NAME, argv, _get_parser(), OpenSearchContext()
    )

    os_desc: OpenSearchDescription
    with ExitStack() as cm:
        cm.enter_context(_handle_opensearch_errors(log))
        if not urlparse(ctx.file_or_url).scheme:
            # Just a local file.
            os_desc = OpenSearchDescription(
                cm.enter_context(open(ctx.file_or_url, "rb"))
            )
        else:
            log.info(f"{ctx.file_or_url} is a URL, downloading...")
            resp = cm.enter_context(urlopen(ctx.file_or_url))
            content_type = resp.info().get_content_type()
            if content_type == "application/opensearchdescription+xml":
                os_desc = OpenSearchDescription(resp)
            elif content_type == "text/html":
                # TODO: use an internal finder?
                log.info(
                    "need to find OpenSearch description, running opensearch-discover..."
                )
                proc = subprocess.run(
                    ["opensearch-discover", "--first", ctx.file_or_url],
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    log.critical(
                        f"an error occurred while running opensearch-discover (code: {proc.returncode})"
                    )
                    # Remove extra newline (the logger adds one itself).
                    log.critical(proc.stderr.strip("\n"))
                    return EX_UNAVAILABLE
                log.info(
                    "found, downloading...",
                )
                os_desc = OpenSearchDescription(
                    cm.enter_context(urlopen(proc.stdout.strip()))
                )
            else:
                log.critical(
                    f"Content-Type of {ctx.file_or_url} ({content_type}) is unsupported, it must be an OpenSearch description or HTML file",
                )
                return EX_DATAERR

    # Set up for processing
    scheme, base_url, *_ = urlparse(os_desc.search_url.template.raw)

    try:
        elvis = Elvis(
            ctx.name,
            base_url,
            # Placeholder URL.  It'll be modified in `template_vars`.
            os_desc.search_url.template.raw,
            scheme=scheme,
            description=os_desc.description,
            append_search_args=False,
            # TODO: add --num-tabs option?
            generator=PROGRAM_NAME,
        )
    except Exception as e:
        log.critical(f"{e}")
        return EX_USAGE

    varnames: Dict[str, str] = {}
    opt: SurfrawVarOption
    for param in os_desc.search_url.params:
        if param.name == "count":
            varnames["count"] = elvis.namespacer("results")
            elvis.add_results_option()
        elif param.name == "language":
            varnames["language"] = elvis.namespacer("language")
            if not os_desc.languages:
                # No need for enum.
                elvis.add_language_option()
            else:
                langs = os_desc.languages.copy()
                for i, lang in enumerate(langs):
                    if lang == "*":
                        langs[i] = "any"

                opt = SurfrawEnum(
                    param.name,
                    # Should the default be any?  That's what the spec says.  Strange that it doesn't allow websites to make their own default though.
                    default=langs[0],
                    values=langs,
                )
                opt.metavar = "ISOCODE"
                opt.description = (
                    "Two letter language code (resembles ISO country codes)"
                )
                ctx.options.append(opt)
        elif param.name in ("startIndex", "startPage"):
            if param.name == "startIndex":
                default = os_desc.search_url.index_offset
                desc = "Offset of first result"
            else:
                default = os_desc.search_url.page_offset
                desc = "Which page of results to show"

            opt = SurfrawAnything(param.name.lower(), str(default))
            varnames[param.name] = elvis.namespacer(opt.name)

            opt.metavar = "NUM"
            opt.description = desc
            ctx.options.append(opt)
        elif param.name in ("inputEncoding", "outputEncoding"):
            if param.name == "inputEncoding":
                encodings = os_desc.input_encodings
                desc = "Specify how search terms are encoded"
            else:
                encodings = os_desc.output_encodings
                desc = "Request output encoded as ENC"

            default_encoding = "UTF-8"
            try:
                if default_encoding not in encodings:
                    default_encoding = encodings[0]
            except IndexError:
                # FIXME: is our behaviour compliant with the spec?
                log.critical(
                    f"OpenSearch description used {param.name} parameter without defining any in {param.name[0].upper()}{param.name[1:]} elements",
                )
                return EX_DATAERR
            opt = SurfrawEnum(param.name.lower(), default_encoding, encodings)
            varnames[param.name] = elvis.namespacer(opt.name)

            opt.metavar = "ENCODING"
            opt.description = desc
            ctx.options.append(opt)
        # FIXME: support non-OpenSearch parameters

    # No need to call `elvis.resolve_options` because not parsing elvis options from CLI.

    # Generate the elvis.
    template_vars = elvis.get_template_vars()

    # Resolve `search_url` with correct elvis variables.
    _, __, *rest = urlparse(
        os_desc.search_url.template.get_surfraw_template(
            elvis.namespacer, varname_map=varnames
        )
    )
    template_vars["search_url"] = urlunparse((scheme, base_url, *rest))

    # Atomically write output file.
    try:
        elvis.write(template_vars)
    except OSError as e:
        # Don't delete tempfile to allow for inspection on write errors.
        log.critical(f"{e}")
        return EX_OSERR
    return EX_OK
