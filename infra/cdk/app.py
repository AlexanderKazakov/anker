#!/usr/bin/env python3
"""CDK entry point for Ankify MCP Server deployment."""

import aws_cdk as cdk

from stacks import AnkifyStack

app = cdk.App()

AnkifyStack(
    app,
    "AnkifyStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account") or None,
        region=app.node.try_get_context("region") or None,
    ),
)

app.synth()
