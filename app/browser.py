from dataclasses import dataclass
import ipaddress
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class BrowserSession:
    browser: object
    page: object
    playwright: object
    context: object = None


class BrowserController:
