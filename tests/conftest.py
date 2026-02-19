import os
import pytest

from dotenv import load_dotenv

from ankify.settings import AWSProviderAccess, AzureProviderAccess


load_dotenv()


@pytest.fixture
def azure_access():
    """Create Azure access settings from environment."""
    access = AzureProviderAccess(
        subscription_key=os.environ.get("ANKIFY__PROVIDERS__AZURE__SUBSCRIPTION_KEY"),
    )
    if access.subscription_key is None:
        pytest.skip("Azure key not available")
    if azure_region := os.environ.get("ANKIFY__PROVIDERS__AZURE__REGION"):
        access.region = azure_region
    return access


@pytest.fixture
def aws_access():
    """Create AWS access settings from environment."""
    access = AWSProviderAccess(
        access_key_id=os.environ.get("ANKIFY__PROVIDERS__AWS__ACCESS_KEY_ID"),
        secret_access_key=os.environ.get("ANKIFY__PROVIDERS__AWS__SECRET_ACCESS_KEY"),
    )
    if access.access_key_id is None or access.secret_access_key is None:
        pytest.skip("AWS keys not available")
    if aws_region := os.environ.get("ANKIFY__PROVIDERS__AWS__REGION"):
        access.region = aws_region
    return access
