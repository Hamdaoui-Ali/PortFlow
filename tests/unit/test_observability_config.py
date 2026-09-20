from __future__ import annotations

import json
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).parents[2]


def test_grafana_provisions_the_local_prometheus_datasource() -> None:
    datasource = yaml.safe_load(
        (
            REPOSITORY_ROOT
            / "observability"
            / "grafana"
            / "provisioning"
            / "datasources"
            / "prometheus.yml"
        ).read_text(encoding="utf-8")
    )

    assert datasource["apiVersion"] == 1
    assert datasource["datasources"] == [
        {
            "name": "PortFlow Prometheus",
            "type": "prometheus",
            "uid": "portflow-prometheus",
            "access": "proxy",
            "url": "http://prometheus:9090",
            "isDefault": True,
            "editable": False,
        }
    ]


def test_dashboard_contains_required_panels_and_queries() -> None:
    dashboard = json.loads(
        (
            REPOSITORY_ROOT
            / "observability"
            / "grafana"
            / "dashboards"
            / "portflow-streaming.json"
        ).read_text(encoding="utf-8")
    )
    panels = {panel["title"]: panel for panel in dashboard["panels"]}

    assert dashboard["uid"] == "portflow-streaming"
    assert dashboard["title"] == "PortFlow streaming observability"
    assert dashboard["refresh"] == "5s"
    assert "State store availability" in panels
    assert "Run status" in panels
    assert "Latest run duration" in panels
    assert "Stream outcomes" in panels
    assert "Latest run status" in panels
    expressions = {
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    }
    assert "portflow_stream_state_store_available" in expressions
    assert "portflow_stream_runs_count" in expressions
    assert "portflow_stream_last_run_duration_seconds" in expressions
    assert "portflow_stream_consumed_messages_total" in expressions
    assert "portflow_stream_dead_letters_total" in expressions
    dashboard_text = json.dumps(dashboard)
    assert "run_id" not in dashboard_text
    assert "error_message" not in dashboard_text
    assert "state_path" not in dashboard_text


def test_grafana_service_is_loopback_only_and_depends_on_prometheus() -> None:
    compose = yaml.safe_load((REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["grafana"]

    assert service["profiles"] == ["observability"]
    assert "127.0.0.1:3000:3000" in service["ports"]
    assert service["depends_on"]["prometheus"]["condition"] == "service_started"
    assert any(str(mount).endswith(":ro") for mount in service["volumes"])
