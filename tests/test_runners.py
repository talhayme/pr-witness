"""Runner adapters: argv, labels and environment, without running anything."""

from __future__ import annotations

from pathlib import Path

from pr_witness import runners


def test_django_runner_turns_paths_into_labels_and_configures_junit_out_of_band(tmp_path):
    r = runners.RUNNERS["django"]
    report = tmp_path / "reports" / "head.xml"
    argv = r.build(report, ["tests/migrations/test_writer.py", "tests/admin_views/tests.py", "tests/pkg/__init__.py"])
    assert argv[-3:] == ["migrations.test_writer", "admin_views.tests", "pkg"]
    assert "runtests.py" in argv[1]
    env = r.environment(report, {"PATH": "/x", "PYTHONPATH": "/already"})
    assert env["PR_WITNESS_REPORT"] == str(report)
    assert env["PYTHONPATH"].split(":") == [str(report.parent), "/already"]
    r.prepare(report)
    settings = (report.parent / "pr_witness_django_settings.py").read_text()
    assert "XMLTestRunner" in settings and "from test_sqlite import *" in settings


def test_pytest_runner_is_unchanged_by_the_hooks(tmp_path):
    r = runners.RUNNERS["pytest"]
    report = tmp_path / "r.xml"
    assert r.build(report, ["tests/test_a.py"])[-1] == "tests/test_a.py"
    assert r.environment(report, {"A": "1"}) == {"A": "1"}


def test_detect_prefers_django_for_its_own_checkout(tmp_path):
    (tmp_path / "tests").mkdir(); (tmp_path / "tests" / "runtests.py").write_text("")
    (tmp_path / "django").mkdir(); (tmp_path / "setup.cfg").write_text("")
    assert runners.detect(tmp_path) == "django"
    (tmp_path / "tests" / "runtests.py").unlink()
    assert runners.detect(tmp_path) == "pytest"


def test_bun_runner_and_detection(tmp_path):
    r = runners.RUNNERS["bun"]
    argv = r.build(tmp_path / "r.xml", ["tests/unit/a.test.ts"])
    assert argv[:2] == ["bun", "test"] and argv[-1] == "tests/unit/a.test.ts" and any(a.startswith("--reporter-outfile=") for a in argv)
    (tmp_path / "package.json").write_text('{"scripts": {"test": "bun test tests/unit/"}, "devDependencies": {"vitest": "^4"}}')
    assert runners.detect(tmp_path) == "bun"


def test_pytest_keeps_collecting_past_a_file_that_will_not_import(tmp_path):
    assert "--continue-on-collection-errors" in runners.RUNNERS["pytest"].build(tmp_path / "r.xml")
