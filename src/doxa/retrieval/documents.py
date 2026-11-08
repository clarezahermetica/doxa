"""Bounded document parsing in a credential-free subprocess; no generated code runs."""

import base64
import ctypes
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree

from pydantic import Field

from doxa.core.models import Contract

MAX_FILE_BYTES = 10_000_000
MAX_TEXT_BYTES = 1_000_000


class DocumentTreeBuilder(ElementTree.TreeBuilder):
    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        # The parser recognizes XML encodings; raw byte scans alone miss UTF-16 DTDs.
        raise ValueError("XML document types and entities are not permitted")


class ParsedDocument(Contract):
    text: str = Field(min_length=1, max_length=MAX_TEXT_BYTES)
    parser_version: str
    page_count: int | None = None
    warnings: tuple[str, ...] = ()


def parse_bytes(filename: str, data: bytes) -> ParsedDocument:
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("Document size exceeds the 10 MB import bound")
    suffix = Path(filename).suffix.lower()
    pages = None
    warnings: tuple[str, ...] = ()
    if suffix in {".txt", ".md", ".json"}:
        text = data.decode("utf-8-sig")
        parser = "utf8-text-v1"
    elif suffix == ".docx":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > 512 or sum(i.file_size for i in members) > 20_000_000:
                raise ValueError("Word archive expansion exceeds the parser bound")
            document = archive.getinfo("word/document.xml")
            if document.file_size > 5_000_000 or document.flag_bits & 1:
                raise ValueError("Unsupported encrypted or oversized Word document")
            raw = archive.read(document)
            if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
                raise ValueError("XML declarations/entities are not permitted")
            root = ElementTree.fromstring(
                raw, parser=ElementTree.XMLParser(target=DocumentTreeBuilder())
            )
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            text = "\n".join(
                "".join(t.text or "" for t in p.findall(".//w:t", ns))
                for p in root.findall(".//w:p", ns)
            )
        parser = "docx-paragraphs-v1"
        warnings = ("Paragraph text only; document layout and embedded objects are not imported.",)
    elif suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or len(reader.pages) > 100:
            raise ValueError("Encrypted PDFs and documents over 100 pages are unsupported")
        pages = len(reader.pages)
        parts = []
        size = 0
        for index, page in enumerate(reader.pages):
            content = page.extract_text() or ""
            size += len(content.encode())
            if size > MAX_TEXT_BYTES:
                raise ValueError("Extracted text exceeds the import bound")
            parts.append(f"[Page {index + 1}]\n" + content)
        if not any((p.split("\n", 1)[1]).strip() for p in parts):
            raise ValueError("No extractable PDF text; OCR is not enabled")
        text = "\n\n".join(parts)
        from importlib.metadata import version

        parser = "pypdf-text-" + version("pypdf") + "-v1"
        warnings = (
            "Text extraction may reorder layout; no OCR or independent content verification.",
        )
    else:
        raise ValueError("Choose TXT, Markdown, JSON, DOCX or a text-based PDF")
    if len(text.encode()) > MAX_TEXT_BYTES or not text.strip():
        raise ValueError("Document has no usable text or exceeds the extracted-text bound")
    return ParsedDocument(text=text, parser_version=parser, page_count=pages, warnings=warnings)


class WindowsParserJob:
    """Enforced child-process memory/CPU caps and termination when the job closes."""

    kernel: Any
    handle: int

    def __init__(self, process: subprocess.Popen[bytes]):
        if sys.platform != "win32":
            raise OSError("Windows parser jobs require Windows")
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", w.DWORD),
                ("min_working", ctypes.c_size_t),
                ("max_working", ctypes.c_size_t),
                ("active", w.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", w.DWORD),
                ("scheduling", w.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "read_ops",
                    "write_ops",
                    "other_ops",
                    "read_bytes",
                    "write_bytes",
                    "other_bytes",
                )
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Basic),
                ("io", IO),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        kernel = ctypes.windll.kernel32
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        kernel.CreateJobObjectW.restype = w.HANDLE
        kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        kernel.CloseHandle.argtypes = [w.HANDLE]
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise RuntimeError("Cannot create bounded parser job")
        limits = Extended()
        limits.basic.flags = 0x100 | 0x2000 | 0x2 | 0x8
        limits.basic.process_time = 6 * 10_000_000
        limits.basic.active = 2  # Windows virtualenv launcher plus the parser interpreter.
        limits.process_memory = 512 * 1024 * 1024
        if not kernel.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ) or not kernel.AssignProcessToJobObject(handle, int(cast(Any, process)._handle)):
            kernel.CloseHandle(handle)
            raise RuntimeError("Cannot enforce parser limits")
        self.kernel = kernel
        self.handle = handle

    def close(self) -> None:
        self.kernel.CloseHandle(self.handle)


def extract_document(filename: str, data: bytes) -> ParsedDocument:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Choose a document up to 10 MB")
    if Path(filename).suffix.lower() in {".txt", ".md", ".json"}:
        return parse_bytes(filename, data)
    command = (
        [sys.executable, "--parse-document"]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "doxa.retrieval.document_worker"]
    )
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH"}
    }
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    job = None
    try:
        if sys.platform == "win32":
            job = WindowsParserJob(process)
        message = json.dumps(
            {"filename": filename, "data": base64.b64encode(data).decode()}
        ).encode()
        output, _ = process.communicate(message, timeout=12)
        if process.returncode != 0 or len(output) > 6_000_000:
            raise ValueError("Document parser rejected the document or exceeded its limits")
        return ParsedDocument.model_validate_json(output)
    except subprocess.TimeoutExpired:
        raise ValueError("Document parser exceeded its time limit") from None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        if job:
            job.close()
