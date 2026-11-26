"""Unit tests run against the FastAPI agent only, so they never call the hosted model."""

import os

os.environ["FINSIGHT_DEFAULT_PROVIDER"] = "local"
