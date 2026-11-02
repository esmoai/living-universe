"""One public HTML page per explicit capture. No link following or script execution."""

import hashlib, http.client, ipaddress, json, re, socket, ssl, time, zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urljoin, urldefrag

LIMIT = 4 * 1024**2


def target(url):
    url = urldefrag(url.strip())[0]
    parts = urlsplit(url)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise ValueError(
            "Enter a public http:// or https:// page URL without credentials"
        )
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port not in (80, 443):
        raise ValueError("Page capture accepts standard HTTP/HTTPS ports only")
    addresses = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    ips = list(dict.fromkeys(row[4][0] for row in addresses))
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError(
            "Capture requires a public address; private and local services are excluded"
        )
    return url, parts, port, ips[0]


def fetch(url):
    # Pin the validated IP, preserving the real hostname for HTTP and TLS.
    # Every redirect is independently validated; environment proxies are unused.
    deadline = time.monotonic() + 45
    for _ in range(6):
        if time.monotonic() > deadline:
            raise ValueError("Page capture timed out")
        url, parts, port, ip = target(url)
        connection = http.client.HTTPConnection(parts.hostname, port, timeout=20)
        connection.sock = socket.create_connection((ip, port), timeout=20)
        if parts.scheme == "https":
            context = ssl.create_default_context()
            import certifi

            context.load_verify_locations(certifi.where())
            connection.sock = context.wrap_socket(
                connection.sock, server_hostname=parts.hostname
            )
        try:
            connection.request(
                "GET",
                (parts.path or "/") + ("?" + parts.query if parts.query else ""),
                headers={
                    "User-Agent": "Xputty-Open-Weight/0.3 (user-initiated page capture)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Page redirect has no destination")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(f"Page returned HTTP {response.status}")
            mime = response.getheader("Content-Type", "")
            if not any(
                t in mime.lower() for t in ("text/html", "application/xhtml+xml")
            ):
                raise ValueError(
                    "This URL is not an HTML page. Upload the downloaded file instead."
                )
            if response.getheader("Content-Encoding", "identity").lower() not in (
                "identity",
                "",
            ):
                raise ValueError(
                    "Page returned compressed content despite requesting identity encoding"
                )
            chunks = []
            length = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("Page capture timed out")
                if response.isclosed():
                    break
                chunk = response.read1(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                length += len(chunk)
                if length > LIMIT:
                    raise ValueError("HTML page exceeds the 4 MiB capture limit")
            blob = b"".join(chunks)
            match = re.search(r'charset=["\']?([\w-]+)', mime, re.I)
            encoding = match.group(1) if match else "utf-8"
            try:
                html = blob.decode(encoding, errors="replace")
            except LookupError:
                html = blob.decode("utf-8", errors="replace")
            return url, blob, html
        finally:
            connection.close()
    raise ValueError("Too many redirects")


class MainText(HTMLParser):
    BLOCKS = {
        "p",
        "div",
        "section",
        "article",
        "main",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "tr",
        "blockquote",
        "pre",
        "br",
    }
    IGNORE = {
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "noscript",
        "template",
        "svg",
        "form",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.all = []
        self.main = []
        self.article = []
        self.title = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        parent = self.stack[-1] if self.stack else (None, False, False, False, False)
        skip = (
            parent[1]
            or tag in self.IGNORE
            or "hidden" in a
            or a.get("aria-hidden") == "true"
        )
        item = (
            tag,
            skip,
            parent[2] or tag == "main" or a.get("role") == "main",
            parent[3] or tag == "article",
            parent[4] or tag == "title",
        )
        if tag not in {
            "br",
            "hr",
            "img",
            "meta",
            "link",
            "input",
            "source",
            "wbr",
            "area",
            "base",
            "embed",
            "param",
            "track",
            "col",
        }:
            self.stack.append(item)
        if tag in self.BLOCKS:
            self.add("\n", item)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                item = self.stack[i]
                if tag in self.BLOCKS:
                    self.add("\n", item)
                del self.stack[i:]
                break

    def add(self, text, item):
        if item[4]:
            self.title.append(text)
            return
        if item[1]:
            return
        self.all.append(text)
        if item[2]:
            self.main.append(text)
        if item[3]:
            self.article.append(text)

    def handle_data(self, data):
        self.add(
            data, self.stack[-1] if self.stack else (None, False, False, False, False)
        )

    def result(self):
        source = (
            self.main
            if "".join(self.main).strip()
            else self.article
            if "".join(self.article).strip()
            else self.all
        )
        lines = [
            re.sub(r"[\t \r\f\v]+", " ", line).strip()
            for line in "".join(source).split("\n")
        ]
        return "\n\n".join(line for line in lines if line), " ".join(
            "".join(self.title).split()
        )


def capture(url, folder):
    final, raw, html = fetch(url)
    parser = MainText()
    parser.feed(html)
    text, title = parser.result()
    if not text.strip():
        raise ValueError(
            "No readable page text found. This page may require JavaScript or a login."
        )
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "original.html").write_bytes(raw)
    (folder / "content.txt").write_bytes(text.encode("utf-8"))
    metadata = {
        "url": url,
        "final_url": final,
        "title": title,
        "captured_at_ns": time.time_ns(),
        "html_sha256": hashlib.sha256(raw).hexdigest(),
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "extraction": "main, article, or body; scripts/navigation excluded; no JavaScript rendering",
        "scope": "single page; user initiated; no recursive crawling",
    }
    (folder / "source.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    with zipfile.ZipFile(folder / "capture.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("original.html", "content.txt", "source.json"):
            z.write(folder / name, name)
    return metadata, text
