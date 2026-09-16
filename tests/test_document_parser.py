import asyncio

import pytest

from app.core.exceptions import AppError, ErrorCode
from app.providers.parsers.markdown import MarkdownParser
from app.providers.parsers.registry import get_document_parser, validate_upload_extension
from app.services.document_ingestion import prepare_document_content


def test_markdown_parser_normalizes_text():
    parser = MarkdownParser()
    parsed = asyncio.run(parser.parse(b"# Title\r\n\r\nBody", filename="note.md"))
    assert parsed.source_type == "markdown"
    assert "# Title" in parsed.content
    assert "\r" not in parsed.content


def test_prepare_document_content_pass_through():
    parsed = asyncio.run(
        prepare_document_content(
            content="hello world",
            file_path=None,
            filename="a.txt",
        )
    )
    assert parsed.content == "hello world"
    assert parsed.source_type == "text"


def test_validate_upload_extension_rejects_zip():
    with pytest.raises(AppError) as exc:
        validate_upload_extension("archive.zip")
    assert exc.value.code == ErrorCode.PARAM_ERROR.code


def test_get_document_parser_for_md():
    parser = get_document_parser("readme.md")
    assert parser.name == "markdown"


def test_docx_parser_if_installed():
    pytest.importorskip("mammoth")
    pytest.importorskip("markdownify")
    from app.providers.parsers.docx import DocxParser
    import io
    import zipfile

    buffer = io.BytesIO()
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>退款政策内容</w:t></w:r></w:p></w:body>
</w:document>"""
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)

    parser = DocxParser()
    parsed = asyncio.run(parser.parse(buffer.getvalue(), filename="sample.docx"))
    assert parsed.source_type == "docx"
    assert "退款" in parsed.content


def test_docx_parser_converts_tables_if_installed():
    pytest.importorskip("mammoth")
    pytest.importorskip("markdownify")
    from app.providers.parsers.docx import DocxParser
    import io
    import zipfile

    def cell(text: str) -> str:
        return f"<w:tc><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"

    table = (
        "<w:tbl><w:tr>"
        + cell("职级")
        + cell("金额")
        + "</w:tr><w:tr>"
        + cell("P8")
        + cell("8000")
        + "</w:tr></w:tbl>"
    )
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{table}</w:body>
</w:document>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        archive.writestr("word/document.xml", document_xml)

    parsed = asyncio.run(DocxParser().parse(buffer.getvalue(), filename="table.docx"))
    assert "| 职级 | 金额 |" in parsed.content
    assert "| --- | --- |" in parsed.content
    assert "8000" in parsed.content


def test_docx_parser_strips_word_bookmark_anchors_if_installed():
    pytest.importorskip("mammoth")
    pytest.importorskip("markdownify")
    from app.providers.parsers.docx import docx_html_to_markdown

    html = (
        '<p><a id="heading_0"></a><strong>1. 总则</strong></p>'
        '<p>正文内容</p>'
        '<p><a id="heading_1"></a><strong>2. 奖励</strong></p>'
    )
    markdown = docx_html_to_markdown(html)
    assert "<a id=" not in markdown
    assert "1. 总则" in markdown
    assert "正文内容" in markdown


def test_pdf_parser_if_installed():
    pytest.importorskip("fitz")
    from app.providers.parsers.pdf import PdfParser
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PDF 验收文本")
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = PdfParser()
    parsed = asyncio.run(parser.parse(pdf_bytes, filename="sample.pdf"))
    assert parsed.source_type == "pdf"
    assert "PDF" in parsed.content
