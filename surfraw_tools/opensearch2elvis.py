# SPDX-FileCopyrightText: 2021 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Generate a surfraw elvis for an OpenSearch-enabled website (v1.1, Draft 6).

Exit codes are taken from the `sysexits.h` file.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from contextlib import ExitStack, contextmanager
from functools import wraps
from os import EX_DATAERR, EX_OK, EX_OSERR, EX_UNAVAILABLE, EX_USAGE
from typing import (
    IO,
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    cast,
)
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlparse, urlunparse
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from typing_extensions import Final

# No stubs.
import lxml.html as html  # type: ignore
from lxml import etree as et

from surfraw_tools.lib.cliopts import MappingOption
from surfraw_tools.lib.common import BASE_PARSER, ExecContext, setup_cli
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
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[BASE_PARSER],
    )
    parser.add_argument("name", help="name for the elvis")
    parser.add_argument(
        "file_or_url",
        help="local OpenSearch description file or any URL on the website",
    )
    parser.add_argument(
        "--user-agent", "-U", help="define a User-Agent header"
    )
    return parser


class _OpenSearchContext(ExecContext):
    def __init__(self) -> None:
        super().__init__()
        self.name: str = "DEFAULT"
        self.file_or_url: str = ""
        self.user_agent: str = "Mozilla/5.0"


class OpenSearchParameter(argparse.Namespace):
    """Parameter for OpenSearch URL template, regardless of HTTP request method."""

    def __init__(
        self,
        name: str,
        optional: bool,
        prefix: Optional[str] = None,
        namespace: Optional[str] = None,
        param: Optional[str] = None,
    ):
        self.name: Final = name
        self.optional: Final = optional
        self.prefix: Final = prefix
        self.namespace: Final = namespace or NS_OPENSEARCH_1_1

        # POST method attributes
        self.param: Final = param
        # # None of these have any special processing.  Just stored for now.
        # self.minimum: Final = minimum
        # self.maximum: Final = maximum
        # self.pattern: Final = pattern
        # self.title: Final = title
        # self.min_exclusive: Final = min_exclusive
        # self.max_exclusive: Final = max_exclusive
        # self.min_inclusive: Final = min_inclusive
        # self.max_inclusive: Final = max_inclusive
        # self.step: Final = step


_TEMPLATE_PARAM_RE: Final = re.compile(
    r"{(?:(?P<prefix>[^:&=/?]+):)?(?P<name>[^:&=/?]+)(?P<optional>\?)?}"
)


class OpenSearchURL(argparse.Namespace):
    """URL for an OpenSearch website."""

    def __init__(
        self,
        *,
        template: str,
        type: str,
        rel: str = "results",
        index_offset: int = 1,
        page_offset: int = 1,
        namespaces: Mapping[Optional[str], str],
        method: Optional[str] = None,
        enctype: Optional[str] = None,
        params: Optional[Iterable[et._Element]] = None,
    ):
        self.raw_template: str = template
        self.extra_params: List[str] = []
        self.type: Final = type
        self.rels: Final = rel.split(" ")
        self.index_offset: Final = index_offset
        self.page_offset: Final = page_offset
        # Ignore method for now.  Assume everything uses "get".
        # TODO: validate whether `method` is "a valid HTTP request method, as specified in RFC 2616."
        if method:
            self.method = method.lower()
        else:
            self.method = "get"
        # TODO: validate according to this value?
        self.enctype = enctype or "application/x-www-form-urlencoded"

        if self.method not in ("get", "post"):
            raise ValueError(
                "only GET requests are supported, with POST requests becoming GET requests"
            )

        # Determine whether mappings can be used
        self.params: List[OpenSearchParameter] = []
        parts = urlparse(self.raw_template)
        if params:
            if parts.query:
                raise ValueError(
                    "this site uses `<Param>`/`<Parameter>` elements AND embedded query parameters at the same time!  what a weird site..."
                )
            for param in params:
                # `value` is what would go into the template URL
                value = param.get("value")
                if not value:
                    raise ValueError(
                        f"no value for <{et.QName(param).localname}> found"
                    )

                match = re.match(_TEMPLATE_PARAM_RE, value)
                if not match:
                    # The search engine is using OpenSearch weirdly.
                    self.extra_params.append(f"{param.get('name')}={value}")
                    continue
                self.params.append(
                    OpenSearchParameter(
                        match.group("name"),
                        bool(match.group("optional")),
                        # Each <Param> and <Parameter> element affect the interpretations of prefix they contain.
                        prefix=match.group("prefix"),
                        namespace=param.nsmap.get(match.group("prefix")),
                        param=param.get("name"),
                    )
                )
        elif parts.query:
            for key, val in parse_qsl(parts.query):
                match = re.match(_TEMPLATE_PARAM_RE, val)
                if not match:
                    self.extra_params.append(f"{key}={val}")
                    continue
                self.params.append(
                    OpenSearchParameter(
                        match.group("name"),
                        bool(match.group("optional")),
                        prefix=match.group("prefix"),
                        namespace=namespaces.get(match.group("prefix")),
                        param=key,
                    )
                )
        else:
            # A strange URL indeed: one that doesn't have any query parameters.
            matches = re.finditer(_TEMPLATE_PARAM_RE, self.raw_template)
            self.params.extend(
                OpenSearchParameter(
                    match.group("name"),
                    bool(match.group("optional")),
                    prefix=match.group("prefix"),
                    namespace=namespaces.get(match.group("prefix")),
                )
                for match in matches
            )

        params_map: Final = {param.name: param for param in self.params}
        if len(self.params) != len(params_map):
            # TODO: remove this restriction?
            raise ValueError(
                "parameters may only be used once per template URL"
            )
        elif (
            params_map.get("searchTerms") is None
            or params_map["searchTerms"].optional
        ):
            raise ValueError(
                "the searchTerms parameter must exist and must *not* be optional"
            )

    def get_surfraw_template(
        self,
        namespacer: Callable[[str], str],
        varname_map: Optional[Mapping[str, str]] = None,
    ) -> str:
        """Return the template URL with the placeholder replaced by shell variables.

        This should only be needed (or called) if the `Elvis` object doesn't
        have a query parameter (or mappings, in this module's case).
        """
        # Collected in order of occurrence
        names_to_vars = {
            "searchTerms": "${it}",
        }
        if varname_map:
            names_to_vars.update(varname_map)
        new_template = self.raw_template
        for param in self.params:
            # Slow, but it works
            new_template = re.sub(
                _TEMPLATE_PARAM_RE,
                names_to_vars[param.name],
                new_template,
                count=1,
            )
        return new_template


# NS_OPENSEARCH_1_0: Final = ""
# Draft 6 (with some parts before Draft 3 for compatibility)
NS_OPENSEARCH_1_1: Final = "http://a9.com/-/spec/opensearch/1.1/"
# Draft 2
NS_OPENSEARCH_EXT_PARAMETERS_1_0: Final = (
    "http://a9.com/-/spec/opensearch/extensions/parameters/1.0/"
)


class OpenSearchDescription(argparse.Namespace):
    """Description for an OpenSearch-enabled website.

    Only version 1.1 (draft 6) is supported, but `<Param>` elements will be
    accepted if there are no `<Parameter>` elements from the parameters
    extension for OpenSearch.  Likewise for the `method` attribute of `<Url>`
    elements, the version from the parameters extension is preferred, but the
    pre-draft 3 version (i.e., without an XML prefix) is accepted.

    The input description must contain *one* `<Url>` element of type
    `text/html`.  This is stored as `search_url`.  The suggestions extension is
    planned to be supported (in `opensearch2elvis`), so these `<Url>` elements
    are stored as `json_suggestions_url` and `xml_suggestions_url`, depending
    on the format advertised.

    The supported languages, and input and output encodings are stored as
    `languages`, `input_encodings`, and `output_encodings` respectively.
    """

    def __init__(self, file: IO[bytes]):
        _xml: Final = et.parse(file)
        _root: Final = _xml.getroot()
        root_qname = et.QName(_root.tag)
        if root_qname != et.QName(NS_OPENSEARCH_1_1, "OpenSearchDescription"):
            # TODO: say bare namespace of root needs to be the 1.1 namespace?
            raise ValueError(
                "only OpenSearch version 1.1 descriptions are supported"
            )

        # self.raw_shortname: Final = _root.find(
        #    et.QName(NS_OPENSEARCH_1_1, "ShortName")
        # ).text
        # self.shortname: Final = self.raw_shortname.replace(" ", "").lower()
        self.description: Final = _root.find(
            et.QName(NS_OPENSEARCH_1_1, "Description")
        ).text

        self.urls: Final[List[OpenSearchURL]] = []
        for url_elem in _root.xpath(
            "os:Url[@template and @type]", namespaces={"os": NS_OPENSEARCH_1_1}
        ):
            # According to the spec, this attribute *needs* an XML prefix.
            method_attr_name = et.QName(
                NS_OPENSEARCH_EXT_PARAMETERS_1_0, "method"
            )

            params = url_elem.findall(
                "param:Parameter",
                namespaces={"param": NS_OPENSEARCH_EXT_PARAMETERS_1_0},
            ) or url_elem.findall(
                "os:Param", namespaces={"os": NS_OPENSEARCH_1_1}
            )

            rel = url_elem.get("rel", "results")
            # Can't understand any other rel values, so just ignore this URL (the spec says this too).
            if set(rel.split(" ")) - {"results", "suggestions"}:
                continue

            self.urls.append(
                OpenSearchURL(
                    template=cast(str, url_elem.get("template")),
                    type=cast(str, url_elem.get("type")),
                    rel=rel,
                    index_offset=int(url_elem.get("indexOffset", "1")),
                    page_offset=int(url_elem.get("pageOffset", "1")),
                    # Prefer using the extension.
                    method=url_elem.get(
                        method_attr_name, url_elem.get("method")
                    ),
                    # According to the spec, this attribute *needs* an XML prefix.
                    enctype=url_elem.get(
                        et.QName(NS_OPENSEARCH_EXT_PARAMETERS_1_0, "enctype")
                    ),
                    params=params,
                    # should namespaces of each param element be taken instead?
                    namespaces=url_elem.nsmap,
                )
            )
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
            elem.text for elem in _root.findall("Language")
        ]
        self.input_encodings: List[str] = [
            elem.text for elem in _root.findall("InputEncoding")
        ]
        self.output_encodings: List[str] = [
            elem.text for elem in _root.findall("OutputEncoding")
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
    except HTTPError as e:
        log.critical(
            f"got an HTTP error {e.code}",
        )
        sys.exit(EX_UNAVAILABLE)
    except URLError as e:
        log.critical(
            f"an error occurred while retrieving data from the network: {e.reason}",
        )
        sys.exit(EX_UNAVAILABLE)
    except AssertionError:
        # Don't fail silently, especially here!
        raise
    except (OSError, Exception) as e:
        log.critical(f"{e}")
        sys.exit(EX_UNAVAILABLE)


OPENSEARCH_DESC_MIME: Final = "application/opensearchdescription+xml"


def _retrieve_opensearch_description(
    file_or_url: str, user_agent: str, log: logging.Logger
) -> OpenSearchDescription:
    with ExitStack() as cm:
        cm.enter_context(_handle_opensearch_errors(log))
        if not urlparse(file_or_url).scheme:
            # Just a local file.
            os_desc = OpenSearchDescription(
                cm.enter_context(open(file_or_url, "rb"))
            )
        else:
            log.info(f"{file_or_url} is a URL, downloading...")
            # Some websites aren't nice to bots.
            fake_headers = {"User-Agent": user_agent}
            resp = cm.enter_context(
                urlopen(Request(file_or_url, headers=fake_headers))
            )
            content_type = resp.info().get_content_type()
            if content_type == OPENSEARCH_DESC_MIME:
                os_desc = OpenSearchDescription(resp)
            elif content_type == "text/html":
                log.info(
                    "looking for OpenSearch description from HTML page..."
                )

                tree = html.parse(resp)
                tree.getroot().make_links_absolute(resp.geturl())
                # Only get the first OpenSearch link (for now).
                # Not checking the `href` attribute: it can only really be checked by downloading it.
                try:
                    url = tree.xpath(
                        f"/html/head//link[@type='{OPENSEARCH_DESC_MIME}' and contains(@rel, 'search') and @href][1]/@href"
                    )[0]
                except IndexError:
                    log.critical("no OpenSearch description found")
                    sys.exit(EX_DATAERR)

                log.info(
                    f"found at {url}, downloading...",
                )
                os_desc = OpenSearchDescription(
                    # Assuming that the page resolves to an OpenSearch document (what site wouldn't?)
                    cm.enter_context(
                        urlopen(Request(url, headers=fake_headers))
                    )
                )
            else:
                log.critical(
                    f"Content-Type of {file_or_url} ({content_type}) is unsupported, it must be an OpenSearch description or HTML file",
                )
                sys.exit(EX_DATAERR)
    return os_desc


def _create_option_objects(
    elvis: Elvis, os_desc: OpenSearchDescription, log: logging.Logger
) -> Dict[str, str]:
    varnames: Dict[str, str] = {}
    opt: SurfrawVarOption
    for param in os_desc.search_url.params:
        if param.optional:
            log.debug(
                f"disregarding optionality of param '{param.name}': elvi can't have *required* options"
            )
        if param.namespace != NS_OPENSEARCH_1_1:
            # FIXME: support non-OpenSearch parameters
            assert param.param
            assert param.prefix
            # Assume that the parameters sharing this namespace have the same prefix
            log.debug(
                f"assuming that the parameters with the namespace {param.namespace} have the same prefix"
            )
            optname = f"{param.prefix}{param.name.lower()}"
            # No default for now.
            # TODO: extract default values from OpenSearch description.
            log.debug(
                f"adding -{optname}= (anything) option for custom parameter '{param.prefix}{param.name}'"
            )
            log.debug(
                "richer options for custom parameters are currently unsupported"
            )
            elvis.options.append(SurfrawAnything(optname, ""))
            elvis.mappings.append(MappingOption(optname, param.param))
            continue

        # OpenSearch parameters:
        if param.name == "count":
            elvis.add_results_option()
            varnames[param.name] = elvis.namespacer("results")
        elif param.name == "language":
            varnames[param.name] = elvis.namespacer(param.name)
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
                    metavar="ISOCODE",
                    description="Two letter language code (resembles ISO country codes)",
                )
                elvis.options.append(opt)
        elif param.name in ("startIndex", "startPage"):
            if param.name == "startIndex":
                default = os_desc.search_url.index_offset
                desc = "Offset of first result"
            else:
                default = os_desc.search_url.page_offset
                desc = "Which page of results to show"

            opt = SurfrawAnything(
                param.name.lower(),
                str(default),
                metavar="NUM",
                description=desc,
            )
            elvis.options.append(opt)
            varnames[param.name] = elvis.namespacer(opt.name)
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
                sys.exit(EX_DATAERR)

            opt = SurfrawEnum(
                param.name.lower(),
                default_encoding,
                encodings,
                metavar="ENCODING",
                description=desc,
            )
            elvis.options.append(opt)
            varnames[param.name] = elvis.namespacer(opt.name)

        if param.param:
            if param.name == "searchTerms":
                elvis.query_parameter = param.param
                elvis.append_search_args = True
            else:
                elvis.mappings.append(
                    MappingOption(param.name.lower(), param.param)
                )

    elvis.resolve_options([], [], [])

    return varnames


_MainFunc = Callable[[Optional[List[str]]], int]


def _convert_system_exit_to_return(main_func: _MainFunc) -> _MainFunc:
    # This helps with testing.
    @wraps(main_func)
    def wrapper(argv: Optional[List[str]] = None) -> int:
        try:
            exit_status = main_func(argv)
        except SystemExit as e:
            exit_status = e.code
        return exit_status

    return wrapper


@_convert_system_exit_to_return
def main(argv: Optional[List[str]] = None) -> int:  # noqa: D103
    # Docstring is copied from the module.
    ctx, log = setup_cli(
        PROGRAM_NAME, argv, _get_parser(), _OpenSearchContext()
    )

    os_desc = _retrieve_opensearch_description(
        ctx.file_or_url, ctx.user_agent, log
    )
    if os_desc.search_url.method == "post":
        log.info(
            "search URL uses method POST: treating it as GET and hoping for the best..."
        )

    # Set up for processing
    scheme, base_url, *_ = urlparse(os_desc.search_url.raw_template)

    try:
        elvis = Elvis(
            ctx.name,
            base_url,
            # Placeholder URL.  It'll be modified in `template_vars`.
            os_desc.search_url.raw_template,
            scheme=scheme,
            description=os_desc.description,
            append_search_args=False,
            enable_completions=ctx.enable_completions,
            # TODO: add --num-tabs option?
            generator=PROGRAM_NAME,
        )
    except Exception as e:
        log.critical(f"{e}")
        return EX_USAGE

    varnames = _create_option_objects(elvis, os_desc, log=log)

    if not elvis.query_parameter:
        assert not elvis.mappings
        # Resolve `search_url` with correct elvis variables.
        _, __, *rest = urlparse(
            os_desc.search_url.get_surfraw_template(
                elvis.namespacer, varname_map=varnames
            )
        )
        elvis.search_url = urlunparse(("", base_url, *rest)).lstrip("/")
    else:
        # Take out placeholders (and their param name) in template URL
        # but leave any non-varying key-value pairs in.
        if os_desc.search_url.extra_params:
            suffix = "&"
        else:
            suffix = "?"
        parts = urlparse(os_desc.search_url.raw_template)
        elvis.search_url = (
            urlunparse(
                (
                    "",
                    parts.netloc,
                    parts.path,
                    parts.params,
                    # Query and fragment will be overridden by the mappings.
                    "&".join(os_desc.search_url.extra_params),
                    "",
                )
            )
            + suffix
        ).lstrip("/")

    # Generate the elvis.
    try:
        elvis.write(elvis.get_template_vars(), ctx.outfile)
    except OSError as e:
        # Don't delete tempfile to allow for inspection on write errors.
        log.critical(f"{e}")
        return EX_OSERR
    return EX_OK


main.__doc__ = __doc__
