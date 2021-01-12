import pytest
from botocore.stub import Stubber

from hyp3_autorift.io import _s3_client, _s3_client_unsigned


@pytest.fixture
def s3_stub():
    with Stubber(_s3_client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def s3_unsigned_stub():
    with Stubber(_s3_client_unsigned) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()
