from __future__ import annotations

import argparse
import re
import subprocess
import sys
from os import EX_OK, EX_OSERR, EX_USAGE, EX_UNAVAILABLE
from typing import (
    IO,
    TYPE_CHECKING,
    Callable,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

if TYPE_CHECKING:
    from typing_extensions import Final

# No stubs.
from lxml import etree as et  # type: ignore

from surfraw_tools.lib.common import BASE_PARSER, _ElvisName, parse_elvis_name
from surfraw_tools.lib.elvis import Elvis
from surfraw_tools.lib.options import SurfrawEnum

PROGRAM_NAME: Final = "opensearch2elvis"


def _get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        PROGRAM_NAME,
        description="generate an elvis for an OpenSearch-enabled website",
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
            # TODO: params inside twice
            raise NotImplementedError("duplicated params in template")
        # Check special params
        if (
            self.params_map.get("searchTerms") is None
            or self.params_map["searchTerms"].optional
        ):
            raise NotImplementedError
        # Get special params:
        #   - searchTerms (query)
        #   - count (results)
        #   - startIndex: "anything"
        #   - startPage: "anything"
        #   - language: enum of supported languages
        #   - inputEncoding: "anything"
        #   - outputEncoding: "anything"
        # how should the {input,output}Encoding params be supported?  should they be validated?  ("anything" options for now)

    def get_surfraw_template(
        self,
        namespacer: Callable[[str], str],
        varname_map: Optional[Mapping[str, str]] = None,
    ) -> str:
        # Collected in order of occurrence
        names_to_vars = {
            "searchTerms": "${_}",
            "count": namespacer("results"),
            # TODO: what option names should they be?
            #'startIndex':
            #'startPage':
            #'startIndex':
            "language": namespacer("language"),
            #'inputEncoding':
            #'outputEncoding':
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
            raise NotImplementedError

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
                    raise NotImplementedError
            self.urls.append(os_url)
        if not self.urls:
            raise NotImplementedError

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
            raise NotImplementedError("search url must exist")

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


def main(argv: Optional[List[str]] = None) -> int:
    parser = _get_parser()
    ctx = OpenSearchContext()
    try:
        parser.parse_args(argv, namespace=ctx)
    except Exception as e:
        print(f"{PROGRAM_NAME}: {e}", file=sys.stderr)
        return EX_USAGE

    # TODO: handle network errors
    os_desc: OpenSearchDescription
    if urlparse(ctx.file_or_url).scheme:
        print(
            f"{PROGRAM_NAME}: {ctx.file_or_url} is a URL, downloading...",
            file=sys.stderr,
        )
        with urlopen(ctx.file_or_url) as resp:
            content_type = resp.info().get_content_type()
            if content_type == "application/opensearchdescription+xml":
                os_desc = OpenSearchDescription(resp)
            elif content_type == "text/html":
                # TODO: use an internal finder?
                print(
                    f"{PROGRAM_NAME}: need to find OpenSearch description, running opensearch-discover...",
                    file=sys.stderr,
                )
                proc = subprocess.run(
                    ["opensearch-discover", "--first", ctx.file_or_url],
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    print(
                        f"{PROGRAM_NAME}: an error occurred while running opensearch-discover (code: {proc.returncode})",
                        file=sys.stderr,
                    )
                    print(
                        "\n".join(
                            f"{PROGRAM_NAME}: {line}"
                            for line in proc.stderr.split("\n")
                        ),
                        file=sys.stderr,
                    )
                    return EX_UNAVAILABLE
                print(
                    f"{PROGRAM_NAME}: found, downloading...", file=sys.stderr
                )
                with urlopen(proc.stdout.strip()) as resp:
                    os_desc = OpenSearchDescription(resp)
            else:
                # ERROR
                raise NotImplementedError(
                    "unsupported content type; needs to be OpenSearch description or HTML (to find one)"
                )
    else:
        with open(ctx.file_or_url, "rb") as f:
            os_desc = OpenSearchDescription(f)

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
        print(f"{PROGRAM_NAME}: {e}", file=sys.stderr)
        return EX_USAGE

    for param in os_desc.search_url.params:
        if param.name == "count":
            elvis.add_results_option()
        elif param.name in (
            "startIndex",
            "startPage",
            "inputEncoding",
            "outputEncoding",
        ):
            pass
        elif param.name == "language":
            if not os_desc.languages:
                # No need for enum
                elvis.add_language_option()
            else:
                ctx.options.append(
                    SurfrawEnum(
                        param.name,
                        default=os_desc.languages[0],
                        values=os_desc.languages,
                    )
                )
                ctx.metavars.append(MetavarOption(param.name, "ISOCODE"))
                ctx.descriptions.append(
                    DescribeOption(
                        param.name,
                        "Two letter language code (resembles ISO country codes)",
                    )
                )

    # No need to call `elvis.resolve_options` because not parsing elvis options from CLI.

    # Generate the elvis.
    template_vars = elvis.get_template_vars()

    # Resolve `search_url` with correct elvis variables.
    _, __, *rest = urlparse(
        os_desc.search_url.template.get_surfraw_template(elvis.namespacer)
    )
    template_vars["search_url"] = urlunparse((scheme, base_url, *rest))

    # Atomically write output file.
    try:
        elvis.write(template_vars)
    except OSError as e:
        # Don't delete tempfile to allow for inspection on write errors.
        print(f"{PROGRAM_NAME}: {e}", file=sys.stderr)
        return EX_OSERR
    return EX_OK
