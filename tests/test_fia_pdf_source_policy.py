from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import requests
from requests.adapters import HTTPAdapter
from requests.models import Response

from scripts import download_fia_pdfs
from scripts.download_fia_pdfs import RegulationLink, download_link, is_official_fia_url


def test_only_https_fia_hosts_are_trusted():
    assert is_official_fia_url("https://www.fia.com/file.pdf")
    assert is_official_fia_url("https://media.fia.com/file.pdf")
    assert not is_official_fia_url("http://www.fia.com/file.pdf")
    assert not is_official_fia_url("https://fia.com.attacker.example/file.pdf")
    assert not is_official_fia_url("https://attacker-fia.com/file.pdf")
    assert not is_official_fia_url("https://.fia.com/file.pdf")
    assert not is_official_fia_url("https://user:password@fia.com/file.pdf")
    assert not is_official_fia_url("https://www.fia.com:8443/file.pdf")


def test_external_url_is_rejected_before_a_request_is_made():
    class NoNetwork:
        def get(self, *_args, **_kwargs):
            raise AssertionError("the untrusted URL must not be requested")

    link = RegulationLink(
        url="https://attacker.example/sporting_regs_2026.pdf",
        doc_type="sporting_regs",
        year=2026,
        title="Untrusted copy",
    )

    assert not download_link(link, NoNetwork())

    path_traversal = RegulationLink(
        url="https://www.fia.com/sporting_regs_2026.pdf",
        doc_type="../outside",
        year=2026,
        title="Invalid path",
    )
    assert not download_link(path_traversal, NoNetwork())


def test_external_redirect_target_is_never_requested():
    requested_urls: list[str] = []

    class RedirectAdapter(HTTPAdapter):
        def send(self, request, **_kwargs):
            requested_urls.append(request.url)
            response = Response()
            response.url = request.url
            response.request = request
            if len(requested_urls) == 1:
                response.status_code = 302
                response.headers["Location"] = "http://127.0.0.1/private"
            else:
                response.status_code = 200
            response._content = b"%PDF-fake"
            return response

    session = requests.Session()
    adapter = RedirectAdapter()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    assert download_fia_pdfs._get("https://www.fia.com/regulations.pdf", session) is None
    assert requested_urls == ["https://www.fia.com/regulations.pdf"]


def test_official_redirect_is_followed_manually():
    requested_urls: list[str] = []

    class RedirectAdapter(HTTPAdapter):
        def send(self, request, **_kwargs):
            requested_urls.append(request.url)
            response = Response()
            response.url = request.url
            response.request = request
            response.status_code = 302 if len(requested_urls) == 1 else 200
            if response.status_code == 302:
                response.headers["Location"] = "https://media.fia.com/regulations.pdf"
            response._content = b"PDF"
            return response

    session = requests.Session()
    session.mount("https://", RedirectAdapter())

    response = download_fia_pdfs._get("https://www.fia.com/regulations.pdf", session)

    assert response is not None
    assert response.url == "https://media.fia.com/regulations.pdf"
    assert requested_urls == [
        "https://www.fia.com/regulations.pdf",
        "https://media.fia.com/regulations.pdf",
    ]


def test_redirect_outside_fia_domain_is_rejected_before_writing(monkeypatch, tmp_path):
    response = SimpleNamespace(
        url="https://attacker.example/sporting_regs_2026.pdf",
        headers={"Content-Type": "application/pdf"},
        content=b"%PDF-fake",
        close=lambda: None,
    )
    monkeypatch.setattr(download_fia_pdfs.CFG, "_repo_root", tmp_path)
    monkeypatch.setattr(download_fia_pdfs, "_get", lambda *_args: response)
    link = RegulationLink(
        url="https://www.fia.com/sporting_regs_2026.pdf",
        doc_type="sporting_regs",
        year=2026,
        title="Formula 1 Sporting Regulations 2026",
    )

    assert not download_link(link, object())
    assert not download_fia_pdfs.CFG.docs_dir.exists()


def test_known_url_list_discards_external_hosts(monkeypatch, tmp_path):
    monkeypatch.setattr(download_fia_pdfs.CFG, "_repo_root", tmp_path)
    known_urls = download_fia_pdfs.CFG.known_urls_file
    known_urls.parent.mkdir(parents=True)
    known_urls.write_text(
        json.dumps(
            [
                {"url": "https://www.fia.com/2026.pdf", "doc_type": "sporting_regs", "year": 2026},
                {
                    "url": "https://attacker.example/2026.pdf",
                    "doc_type": "sporting_regs",
                    "year": 2026,
                },
            ]
        ),
        encoding="utf-8",
    )

    links = download_fia_pdfs.load_known_urls()

    assert [link.url for link in links] == ["https://www.fia.com/2026.pdf"]


def test_scraper_accepts_only_official_pdf_links(monkeypatch):
    page = SimpleNamespace(
        url="https://www.fia.com/regulation/category/110",
        text=(
            '<a href="https://www.fia.com/sporting_regs_2026.pdf">'
            "Formula 1 Sporting Regulations 2026</a>"
            '<a href="https://attacker.example/sporting_regs_2026.pdf">'
            "Formula 1 Sporting Regulations 2026</a>"
        ),
    )
    monkeypatch.setattr(download_fia_pdfs, "_get", lambda *_args: page)

    links = download_fia_pdfs.scrape_regulation_links("sporting_regs", object())

    assert [link.url for link in links] == ["https://www.fia.com/sporting_regs_2026.pdf"]


def test_scraper_rejects_a_category_page_redirect(monkeypatch):
    page = SimpleNamespace(url="https://attacker.example/regs", text="")
    monkeypatch.setattr(download_fia_pdfs, "_get", lambda *_args: page)

    assert download_fia_pdfs.scrape_regulation_links("sporting_regs", object()) == []


def test_get_returns_successful_fia_response_without_retrying():
    response = SimpleNamespace(
        url="https://www.fia.com/regulations/category/110",
        status_code=200,
        headers={},
        raise_for_status=lambda: None,
        close=lambda: None,
    )

    class Session:
        def __init__(self):
            self.calls = 0

        def get(self, url, timeout, allow_redirects):
            self.calls += 1
            assert url == "https://www.fia.com/regulations/category/110"
            assert timeout > 0
            assert allow_redirects is False
            return response

    session = Session()
    assert (
        download_fia_pdfs._get("https://www.fia.com/regulations/category/110", session) is response
    )
    assert session.calls == 1


def test_output_path_rejects_untrusted_file_name_components():
    link = RegulationLink(
        url="https://www.fia.com/2026.pdf",
        doc_type="../outside",
        year=2026,
        title="Invalid type",
    )

    with pytest.raises(ValueError, match="Unsupported regulation document type or year"):
        download_fia_pdfs.output_path(link)
