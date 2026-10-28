"""Vendor dependencies namespace for bdpan_cli.

This package vendors the Baidu Netdisk OpenAPI Client to allow standard
PyPI / Wheel packaging without local relative directory dependencies.
"""

from . import openapi_client

__all__ = ["openapi_client"]
