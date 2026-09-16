#!/usr/bin/env python3
"""优化十二 02 验收：multipart docx/pdf/txt + JSON md 回归。"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000/api/v1"
POLL_INTERVAL_SEC = 2
POLL_TIMEOUT_SEC = 180


def request_multipart(
    path: str,
    api_key: str,
    *,
    kb_id: str,
    file_path: Path,
    title: str | None = None,
) -> dict:
    boundary = "----ragcenterboundary7MA4YWxkTrZu0gW"
    file_bytes = file_path.read_bytes()
    filename = file_path.name
    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())

    add_field("kb_id", kb_id)
    if title:
        add_field("title", title)

    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    parts.append(f"Content-Type: {mime_type}\r\n\r\n".encode())
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(parts)
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("code") != 0:
        raise SystemExit(f"multipart upload failed: {payload}")
    return payload["data"]


def request_json(method: str, path: str, api_key: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"无法连接 {BASE_URL}，请确认后端与 Celery Worker 已启动: {exc}") from exc
    if body.get("code") != 0:
        raise SystemExit(f"API 失败 {path}: {body}")
    return body["data"]


def wait_document_success(api_key: str, document_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT_SEC
    while time.time() < deadline:
        detail = request_json("GET", f"/documents/{document_id}", api_key)
        status = detail.get("status")
        if status == 1:
            return detail
        if status == 2:
            raise SystemExit(f"文档索引失败: {detail.get('error_message')}")
        time.sleep(POLL_INTERVAL_SEC)
    raise SystemExit(f"等待索引超时 document_id={document_id}")


def create_sample_docx(path: Path) -> None:
    import zipfile

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
  <w:body>
    <w:p><w:r><w:t>用户可在订单完成后 7 天内申请退款。</w:t></w:r></w:p>
  </w:body>
</w:document>"""

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)


def create_sample_pdf(path: Path) -> None:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "PDF解析验收：会员补偿标准详见会员等级权益文档。")
    pdf.save(path)
    pdf.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify optimization 12 document parsers.")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--kb-id", required=True)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        txt_path = tmp_dir / "parser_sample.txt"
        txt_path.write_text("## TXT验收\n\nmultipart 文本文件解析验收内容。", encoding="utf-8")

        print("\n[01] JSON md 回归")
        md_upload = request_json(
            "POST",
            "/documents/upload",
            args.api_key,
            {
                "kb_id": args.kb_id,
                "title": "parser_json_md",
                "content": "## JSON回归\n\n优化十二 JSON upload 仍可用。",
            },
        )
        wait_document_success(args.api_key, md_upload["document_id"])
        print("  OK json md")

        print("\n[02] multipart txt")
        txt_upload = request_multipart(
            "/documents/upload",
            args.api_key,
            kb_id=args.kb_id,
            file_path=txt_path,
        )
        txt_detail = wait_document_success(args.api_key, txt_upload["document_id"])
        assert txt_detail.get("source_filename") == "parser_sample.txt"
        print("  OK multipart txt")

        docx_path = tmp_dir / "parser_sample.docx"
        create_sample_docx(docx_path)
        print("\n[03] multipart docx")
        docx_upload = request_multipart(
            "/documents/upload",
            args.api_key,
            kb_id=args.kb_id,
            file_path=docx_path,
        )
        wait_document_success(args.api_key, docx_upload["document_id"])
        retrieve = request_json(
            "POST",
            "/rag/retrieve",
            args.api_key,
            {
                "kb_id": args.kb_id,
                "user_id": "verify_parser_12",
                "query": "退款 7 天",
                "profile": "speed",
            },
        )
        chunks = retrieve.get("retrieved_chunks") or retrieve.get("chunks") or []
        if not chunks:
            raise SystemExit("docx retrieve 无结果")
        print("  OK docx upload + retrieve")

        pdf_path = tmp_dir / "parser_sample.pdf"
        create_sample_pdf(pdf_path)
        print("\n[04] multipart pdf")
        pdf_upload = request_multipart(
            "/documents/upload",
            args.api_key,
            kb_id=args.kb_id,
            file_path=pdf_path,
        )
        wait_document_success(args.api_key, pdf_upload["document_id"])
        print("  OK multipart pdf")

        zip_path = tmp_dir / "bad.zip"
        zip_path.write_bytes(b"PK")
        print("\n[05] 不支持扩展名 .zip")
        try:
            request_multipart(
                "/documents/upload",
                args.api_key,
                kb_id=args.kb_id,
                file_path=zip_path,
            )
        except SystemExit:
            print("  OK zip rejected")
        else:
            raise SystemExit("zip 应被拒绝")

    print("\n优化十二 02 验收通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
