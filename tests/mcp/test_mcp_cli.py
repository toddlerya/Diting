import pytest

from mcp.knowledge_server import create_parser as create_knowledge_parser
from mcp.loki_server import create_parser as create_loki_parser
from mcp.prometheus_server import create_parser as create_prometheus_parser
from mcp.trace_server import create_parser as create_trace_parser


def test_mcp_cli_transport_options():
    parsers = [
        ("prometheus", create_prometheus_parser(), 8001),
        ("loki", create_loki_parser(), 8002),
        ("trace", create_trace_parser(), 8003),
        ("knowledge", create_knowledge_parser(), 8004),
    ]

    for name, parser, expected_port in parsers:
        # Default options
        args = parser.parse_args([])
        assert args.transport == "stdio", f"{name} default transport should be stdio"
        assert args.port == expected_port, f"{name} default port mismatch"
        assert args.host == "127.0.0.1", f"{name} default host mismatch"

        # Streamable HTTP transport option
        args_http = parser.parse_args(["--transport", "streamable-http", "--port", "9000"])
        assert args_http.transport == "streamable-http"
        assert args_http.port == 9000

        # Deprecated 'sse' option should now fail parsing
        with pytest.raises(SystemExit):
            parser.parse_args(["--transport", "sse"])
