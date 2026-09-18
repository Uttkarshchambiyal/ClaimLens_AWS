from unittest.mock import Mock
import json
import pytest

from claimlens.config import Settings
from claimlens.extraction import make_evidence, normalize_field
from claimlens.models import Geometry
from claimlens.money import parse_money_to_paise
from claimlens.repository import InMemoryRepository
from claimlens.service import AnalysisService
from claimlens import workflow


@pytest.mark.parametrize('raw', ['1,23.45', '12,34,56.00'])
def test_malformed_grouping_is_not_a_clean_amount(raw):
    assert parse_money_to_paise(raw).status == 'AMBIGUOUS'


@pytest.mark.parametrize('raw', ['(100', '100)', '(-100)', '9007199254740992.00'])
def test_invalid_sign_or_unsafe_integer_is_rejected(raw):
    assert parse_money_to_paise(raw).status == 'INVALID'


def test_indian_and_western_grouping_remain_supported():
    assert parse_money_to_paise('1,23,456.78').paise == 12345678
    assert parse_money_to_paise('123,456.78').paise == 12345678
    assert parse_money_to_paise('(123.45)').paise == -12345


def test_numeric_date_order_must_be_explicit():
    assert normalize_field('admission_date', '05/06/2026', Settings())[1] == 'AMBIGUOUS'
    assert normalize_field('admission_date', '05/06/2026', Settings(date_order='DMY'))[0] == '2026-06-05'
    assert normalize_field('admission_date', '05/06/2026', Settings(date_order='MDY'))[0] == '2026-05-06'


def test_geometry_cannot_be_fabricated_or_nonfinite():
    with pytest.raises(ValueError): Geometry(float('nan'), 0, .2, .2)
    with pytest.raises(ValueError, match='missing'):
        make_evidence('doc', 1, 1, [{'Id': 'one', 'Confidence': 98}], 'synthetic text')


@pytest.fixture
def pipeline(monkeypatch):
    repo = InMemoryRepository()
    repo.put_once('tenant', 'ANALYSIS', 'analysis', {'claimId': 'claim', 'status': 'QUEUED', 'createdAt': '2026-09-17T12:00:00Z', 'documentIds': ['doc']})
    repo.put_once('tenant', 'DOCUMENT', 'doc', {'claimId': 'claim', 'version': 1, 'documentType': 'BILL', 'objectKey': 'private/source.pdf', 's3VersionId': 'pinned-source'})
    clients = {'repo': repo, 'textract': Mock(), 's3': Mock(), 'bedrock': Mock()}
    monkeypatch.setattr(workflow, '_clients', lambda _: clients)
    monkeypatch.setattr(workflow, 'Settings', lambda: Settings(documents_bucket='synthetic', use_bedrock=False))
    event = {'tenantId': 'tenant', 'analysisId': 'analysis', 'claimId': 'claim', 'documentId': 'doc', 'documentType': 'BILL', 'version': 1}
    clients['textract'].start_document_analysis.return_value = {'JobId': 'job-1'}
    return clients, event


def test_start_pins_record_version_and_reuses_textract_job(pipeline):
    clients, event = pipeline
    first = workflow.start_extraction_handler(event, None)
    assert workflow.start_extraction_handler(event, None)['jobId'] == first['jobId']
    clients['textract'].start_document_analysis.assert_called_once()
    assert clients['textract'].start_document_analysis.call_args.kwargs['DocumentLocation']['S3Object']['Version'] == 'pinned-source'


def test_paginated_partial_extraction_is_preserved_not_ready_and_retry_safe(pipeline):
    clients, event = pipeline
    event = workflow.start_extraction_handler(event, None)
    clients['textract'].get_document_analysis.side_effect = [
        {'JobStatus': 'PARTIAL_SUCCESS', 'Blocks': [], 'DocumentMetadata': {'Pages': 2}, 'NextToken': 'page-2'},
        {'JobStatus': 'PARTIAL_SUCCESS', 'Blocks': []},
    ]
    assert workflow.poll_extraction_handler(event, None)['jobStatus'] == 'PARTIAL_SUCCESS'
    doc = clients['repo'].get_for_tenant('tenant', 'DOCUMENT', 'doc')
    assert doc['status'] == 'PARTIAL'
    assert clients['textract'].get_document_analysis.call_count == 2
    assert clients['s3'].put_object.call_count == 2  # Full raw and normalized archives.
    assert len(json.loads(clients['s3'].put_object.call_args_list[0].kwargs['Body'])) == 2
    workflow.poll_extraction_handler(event, None)
    assert clients['textract'].get_document_analysis.call_count == 2


def test_completed_analysis_retry_never_invokes_model(pipeline):
    clients, event = pipeline
    service = AnalysisService(clients['repo'], Settings())
    service.analyze_fields('tenant', 'analysis', [], set(), semantic_error='OFFLINE')
    result = workflow.analyze_handler({**event, 'documents': [{'documentId': 'doc', 'documentType': 'BILL'}]}, None)
    assert result['analysisStatus'] == 'COMPLETED_WITH_WARNINGS'
    clients['bedrock'].converse.assert_not_called()


def test_failure_is_visible_and_does_not_overwrite_completed_analysis(pipeline):
    clients, event = pipeline
    assert workflow.mark_failed_handler(event, None)['status'] == 'FAILED'
    analysis = clients['repo'].get_for_tenant('tenant', 'ANALYSIS', 'analysis')
    assert any(f['status'] == 'ERROR' for f in analysis['findings'])
    assert clients['repo'].get_for_tenant('tenant', 'ANALYSIS_VERSION', 'analysis#v1')['status'] == 'FAILED'
    clients['repo'].update_for_tenant('tenant', 'ANALYSIS', 'analysis', {'status': 'COMPLETED_WITH_WARNINGS'})
    assert workflow.mark_failed_handler(event, None)['status'] == 'COMPLETED_WITH_WARNINGS'


def test_report_prose_is_bounded_and_cited():
    blocks = [{'Id': 'line-' + str(i), 'BlockType': 'LINE', 'Text': 'Synthetic clinical statement', 'Page': 1} for i in range(50)]
    fields = workflow._adapter_fields(blocks, 'SUPPORTING_REPORT')
    assert len(fields) == 40
    assert all(f['name'] == 'clinical_statement' and f['blocks'] for f in fields)


def test_snapshot_wins_if_an_interrupted_worker_retries(pipeline, consistent_fields):
    clients, _ = pipeline
    service = AnalysisService(clients['repo'], Settings())
    original = service.analyze_fields('tenant', 'analysis', consistent_fields, {'BILL'}, semantic_error='OFFLINE')
    clients['repo'].update_for_tenant('tenant', 'ANALYSIS', 'analysis', {'completedAt': None, 'status': 'PROCESSING'})
    retry = service.analyze_fields('tenant', 'analysis', [], set(), semantic_error='OFFLINE')
    assert retry['findings'] == original['findings']
