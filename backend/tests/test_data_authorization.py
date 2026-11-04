from uuid import uuid4

from app.orchestration.data_authorization import LocalRealDataAuthorization


def test_real_data_authorization_is_denied_by_default():
    authorization = LocalRealDataAuthorization()

    assert not authorization.allows(uuid4(), "package", "dataset", "source")


def test_real_data_authorization_requires_the_exact_source_identity():
    authorization = LocalRealDataAuthorization()
    project = uuid4()
    authorization.grant(project, "package", "dataset", "source-v1")

    assert authorization.allows(project, "package", "dataset", "source-v1")
    assert not authorization.allows(project, "package", "dataset", "source-v2")
    assert not authorization.allows(project, "package", "other-dataset", "source-v1")


def test_real_data_authorization_is_project_scoped():
    authorization = LocalRealDataAuthorization()
    project = uuid4()
    authorization.grant(project, "package", "dataset", "source")

    assert not authorization.allows(uuid4(), "package", "dataset", "source")
