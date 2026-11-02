"""Persistent lexical cache and isolated source ingestion acceptance tests."""

import asyncio
import base64
import io
import zipfile
from uuid import UUID, uuid4

import pytest

from doxa.core.models import SourceDocument
from doxa.core.workbench import ImportDocument, import_document
from doxa.core.workbench_demo import demonstrate
from doxa.retrieval.documents import extract_document
from doxa.retrieval.persistent import PersistentSearch
from doxa.storage.database import connection


def test_windows_parser_job_refuses_non_windows_before_native_calls(monkeypatch):
    from doxa.retrieval import documents

    with monkeypatch.context() as platform:
        platform.setattr(documents.sys, "platform", "linux")
        with pytest.raises(OSError, match="require Windows"):
            documents.WindowsParserJob(None)


def test_fts_cache_reuses_rows_filters_principals_and_rebuilds(controller):
    a, b = uuid4(), uuid4()
    cache = PersistentSearch(controller.settings.database_path)
    assert cache.rank(
        [(a, "Paper A", "cache invalidation"), (b, "Private", "private cache")], "cache"
    )
    assert cache.rank([(a, "Paper A", "cache invalidation")], "cache") == (a,)
    with connection(controller.settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM search_documents").fetchone()[0] == 2
    assert PersistentSearch(controller.settings.database_path).rank(
        [(a, "Paper A", "cache invalidation")], "invalidation"
    ) == (a,)
    cache.rebuild()
    with connection(controller.settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM search_documents").fetchone()[0] == 0
    assert cache.rank([(a, "Paper A", "cache invalidation")], "cache") == (a,)
    with pytest.raises(ValueError, match="Immutable"):
        cache.rank([(a, "Paper A", "changed text")], "cache")


def docx_bytes(text="A source with explicit provenance."):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
            + text
            + "</w:t></w:r></w:p></w:body></w:document>",
        )
    return stream.getvalue()


def test_docx_worker_extracts_text_and_enforces_xml_policy():
    parsed = extract_document("source.docx", docx_bytes())
    assert parsed.text == "A source with explicit provenance."
    assert parsed.parser_version == "docx-paragraphs-v1"
    assert parsed.warnings
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", "<!DOCTYPE bad><document/>")
    with pytest.raises(ValueError):
        extract_document("bad.docx", stream.getvalue())


def test_pdf_worker_reports_no_text_instead_of_fabricating_ocr():
    from pypdf import PdfWriter

    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(stream)
    with pytest.raises(ValueError):
        extract_document("scan.pdf", stream.getvalue())


def test_pdf_worker_extracts_actual_page_text():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 20 100 Td (Evidence from the paper) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = io.BytesIO()
    writer.write(stream)
    parsed = extract_document("paper.pdf", stream.getvalue())
    assert "Evidence from the paper" in parsed.text
    assert parsed.page_count == 1 and parsed.warnings


def test_document_import_persists_original_and_extraction_provenance(controller):
    result = asyncio.run(demonstrate(controller))
    # The demonstration is completed; a new configured task is needed for source admission.
    from doxa.core.models import TaskSpecification
    from doxa.core.workbench import NewExperiment, ParticipantGroup, create_experiment

    template = controller.configuration().agents[0]
    run = create_experiment(
        controller,
        NewExperiment(
            name="Import",
            task=TaskSpecification(question="Read the source"),
            participants=(ParticipantGroup(agent_id=template.id),),
            idempotency_key=str(uuid4()),
        ),
    )
    raw = docx_bytes()
    source = import_document(
        controller,
        run.id,
        ImportDocument(
            filename="source.docx",
            data_base64=base64.b64encode(raw).decode(),
            idempotency_key="doc",
        ),
    )
    assert isinstance(source, SourceDocument) and source.original is not None
    assert source.parser_version == "docx-paragraphs-v1"
    from doxa.storage.artifacts import ArtifactStore

    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    assert store.get(source.original) == raw
    assert store.get(source.content).decode() == "A source with explicit provenance."
    assert source.original.sha256 != source.content.sha256
    with pytest.raises(ValueError):
        import_document(
            controller,
            UUID(str(result["run_id"])),
            ImportDocument(
                filename="source.docx",
                data_base64=base64.b64encode(raw).decode(),
                idempotency_key="late",
            ),
        )


@pytest.mark.parametrize(
    "name,data", [("file.exe", b"anything"), ("empty.txt", b""), ("broken.pdf", b"not a pdf")]
)
def test_parser_rejects_unsupported_or_broken_documents(name, data):
    with pytest.raises(ValueError):
        extract_document(name, data)
