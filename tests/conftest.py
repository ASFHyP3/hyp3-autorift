import pytest
from botocore.stub import Stubber

from hyp3_autorift.process import S3_CLIENT


@pytest.fixture
def s3_stubber():
    with Stubber(S3_CLIENT) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()
