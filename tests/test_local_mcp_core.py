"""Offline tests: no MCP package, Upwork, credentials, or network needed."""
from unittest.mock import patch
from local_mcp import core


def test_machine_status_is_non_sensitive():
    result = core.machine_status()
    assert "logical_cpus" in result
    assert "repo_disk_free_gb" in result
    assert "credentials" not in str(result).lower()


def test_only_fixed_check_names():
    for name in ["powershell", "git push", "tests && whoami", "../../outside"]:
        assert core.run_check(name, execute=True)["ok"] is False


def test_default_denies_execution():
    with patch.dict("os.environ", {"ACQ_ENABLE_CHECKS": "0"}):
        with patch.object(core, "_run_fixed") as runner:
            result = core.run_check("tests", execute=True)
            assert result["status"] == "denied"
            runner.assert_not_called()


def test_preview_never_runs_process():
    with patch.object(core, "_run_fixed") as runner:
        plan = core.run_check("audit", execute=False)
        assert plan["status"] == "preview_only"
        assert plan["executes"] is False
        runner.assert_not_called()


def test_allowlisted_checks_use_fixed_commands():
    with patch.dict("os.environ", {"ACQ_ENABLE_CHECKS": "1"}):
        with patch.object(core, "_run_fixed", return_value={"ok": True, "exit_code": 0}) as runner:
            res = core.run_check("tests", execute=True)
            assert res["status"] == "completed"
            assert runner.call_args.args[0] == [core.sys.executable, "-m", "pytest", "-q"]
