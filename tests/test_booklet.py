from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from a6_booklet import INPUT_FORMATS, ISO_A_MM, POINTS_PER_MM, make_booklet
from backend.app import app


def pdf_bytes(count=5, width=210, height=297):
    writer = PdfWriter()
    for index in range(count):
        page = writer.add_blank_page(width=width * POINTS_PER_MM, height=height * POINTS_PER_MM)
        content = DecodedStreamObject()
        content.set_data(f"/source-page-{index + 1} BMC\nEMC\n".encode())
        page[NameObject('/Contents')] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize('page_format', INPUT_FORMATS)
def test_sheet_dimensions_and_padding(tmp_path, page_format):
    source, target = tmp_path / 'source.pdf', tmp_path / 'output.pdf'
    source.write_bytes(pdf_bytes())
    assert make_booklet(source, target, page_format) == (2, 3)
    result = PdfReader(target)
    assert len(result.pages) == 4
    short, long = ISO_A_MM[f'A{int(page_format[1:]) - 1}']
    for page in result.pages:
        assert float(page.mediabox.width) == pytest.approx(long * POINTS_PER_MM)
        assert float(page.mediabox.height) == pytest.approx(short * POINTS_PER_MM)


def test_imposition_order_and_sides(tmp_path):
    source, target = tmp_path / 'source.pdf', tmp_path / 'output.pdf'
    source.write_bytes(pdf_bytes(count=8))
    assert make_booklet(source, target, 'A4') == (2, 0)
    pages = PdfReader(target).pages
    for page, pair in zip(pages, [(8, 1), (2, 7), (6, 3), (4, 5)]):
        content = page.get_contents().get_data()
        assert content.index(f'source-page-{pair[0]}'.encode()) < content.index(f'source-page-{pair[1]}'.encode())


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_upload_download(client):
    result = client.post('/api/booklet?page_format=A4', files={'file': ('résumé.pdf', pdf_bytes(), 'application/pdf')})
    assert result.status_code == 200
    assert result.headers['content-type'] == 'application/pdf'
    assert result.headers['x-booklet-sheets'] == '2'
    assert result.headers['x-booklet-blanks'] == '3'
    assert result.headers['x-booklet-pages'] == '5'
    assert result.headers['cache-control'] == 'no-store'
    assert 'A3.pdf' in result.headers['content-disposition']
    assert len(PdfReader(BytesIO(result.content)).pages) == 4


@pytest.mark.parametrize('content', [b'not a PDF', b'', pdf_bytes(0), pdf_bytes(width=297, height=210)])
def test_invalid_pdf(client, content):
    result = client.post('/api/booklet', files={'file': ('bad.pdf', content)})
    assert result.status_code == 422
    assert isinstance(result.json()['detail'], str)


def test_encrypted_pdf(client):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    writer.encrypt('password')
    buffer = BytesIO()
    writer.write(buffer)
    result = client.post('/api/booklet', files={'file': ('locked.pdf', buffer.getvalue())})
    assert result.status_code == 422
    assert 'password' in result.json()['detail']


def test_upload_limit(client, monkeypatch):
    monkeypatch.setattr('backend.app.MAX_UPLOAD_BYTES', 20)
    assert client.post('/api/booklet', files={'file': ('big.pdf', pdf_bytes())}).status_code == 413


def test_formats_and_invalid_format(client):
    data = client.get('/api/formats').json()
    assert len(data['formats']) == 10
    assert data['formats'][3]['sheet'] == 'A3'
    assert client.get('/api/health').json() == {'status': 'ok'}
    assert client.post('/api/booklet?page_format=A0', files={'file': ('file.pdf', pdf_bytes())}).status_code == 422
