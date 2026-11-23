"""Hourly records runner. Retry individual official responses before ingestion."""
from contextvars import ContextVar
from functools import wraps
import hashlib
import io
import json
import re
import runpy
import subprocess
import sys
import time
import zipfile
from contextlib import closing
from http.client import IncompleteRead
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request
from xml.etree import ElementTree

class Response(io.BytesIO):
    def __init__(self, data, headers):
        super().__init__(data)
        self.headers = headers


def checked(request, open_response, validate):
    url = request.full_url if isinstance(request, Request) else request
    for attempt in range(3):
        try:
            with closing(open_response(request)) as response:
                data = response.read(512 * 1024**2 + 1)
                if len(data) > 512 * 1024**2:
                    raise ValueError("Official response exceeds archive limit")
                validate(url, data)
                return Response(data, response.headers)
        except HTTPError as exc:
            if exc.code == 304:
                raise
            error = exc
        except (OSError, IncompleteRead, ValueError, KeyError, AttributeError,
                ElementTree.ParseError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
            error = exc
        if attempt == 2:
            if isinstance(error, HTTPError) and error.code == 404:
                error.add_note(url)
                raise error
            raise RuntimeError(f"Official download or parse failed for {url}: {error}") from error
        print(f"Retrying {url} in 60 seconds after {error}", flush=True)
        time.sleep(60)


def install_archive():
    from ingestion import national

    def validate(url, data):
        path = urlsplit(url).path
        if re.search(r"/(?:roll\d+|vote_\d+_\d+_\d+)\.xml$", path, re.I):
            national.parse_vote(data, hashlib.sha256(data).hexdigest())
        elif path.endswith(".xml"):
            if national.xml(data).tag.lower().endswith("html"):
                raise ValueError("Expected XML data, received HTML")
        elif path.endswith(".json"):
            json.loads(data)
        elif path.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                archive.infolist()

    source_context = ContextVar("official_sources", default=None)

    def report_urls(operation):
        @wraps(operation)
        def run(*args, **kwargs):
            urls = []
            token = source_context.set(urls)
            try:
                return operation(*args, **kwargs)
            except Exception as exc:
                if urls:
                    exc.add_note("Official sources: " + ", ".join(urls))
                raise
            finally:
                source_context.reset(token)
        return run

    for name in ("ingest_bills", "ingest_rosters", "ingest_vote", "discover_votes",
                 "ingest_president", "ingest_finance"):
        setattr(national, name, report_urls(getattr(national, name)))

    initialize = national.Archive.__init__
    def init(archive, *args, **kwargs):
        initialize(archive, *args, **kwargs)
        original = archive.opener.open
        def fetch(request, timeout):
            urls = source_context.get()
            if urls is not None:
                urls.append(request.full_url)
            # Refetch vote XML so a previously cached error page cannot survive via HTTP 304.
            if re.search(r"/(?:roll\d+|vote_\d+_\d+_\d+)\.xml$", urlsplit(request.full_url).path, re.I):
                request.remove_header("If-none-match")
                request.remove_header("If-modified-since")
            return checked(request, lambda req: original(req, timeout=timeout), validate)
        archive.opener.open = fetch
    national.Archive.__init__ = init
    from ingestion import live_job
    live_job.published_types = report_urls(live_job.published_types)


def check_debate():
    from urllib.request import urlopen
    files = Path("data/debate").glob("*.json")
    records = {r["url"]: r for r in (json.loads(f.read_text()) for f in files)}
    def validate(url, data):
        record = records[url]
        if hashlib.sha256(data).hexdigest() != record.get("rawSha256", record["sha256"]):
            raise ValueError("Publication hash differs from reviewed source")
        if record["kind"] == "administration":
            subprocess.run(["pdftotext", "-raw", "-", "-"], input=data,
                           stdout=subprocess.DEVNULL, check=True)
        else:
            data.decode()
    namespace = runpy.run_path("scripts/round6/check_debate.py")
    verify = namespace["verify"]
    last = []
    def fetch(url, timeout):
        last[:] = [url]
        return checked(url, lambda u: urlopen(u, timeout=timeout), validate)
    verify.__globals__["urlopen"] = fetch
    try:
        verify()
    except Exception as exc:
        if last:
            exc.add_note(last[0])
        raise

if __name__ == "__main__":
    check_debate()
