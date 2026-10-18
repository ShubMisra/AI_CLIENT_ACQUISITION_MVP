"""Start only a local supervised controller; no agent launch at startup."""
import os
import json
import shutil
import sys
from pathlib import Path

from .architect import MockArchitect
from .controller import Controller
from .github import CITrust, GitHubGateway
from .policy import Autonomy, Settings
from .runners import FixtureCommitRunner, GitReader, Verifier
from .store import Store
from .web import create_app
from .readonly import ReadOnlyPilot
from .readonly_policy import RuntimePin, ProviderTariff


def build_controller() -> Controller:
    root = Path(os.getenv('ORCH_WORKTREE_ROOT', str(Path.cwd().parent / 'acq-agent-runs'))).resolve()
    root.mkdir(parents=True, exist_ok=True)
    db_path = Path(os.getenv('ORCH_DB_PATH', str(Path.cwd() / 'data' / 'orchestrator.db'))).resolve()
    settings = Settings(root, db_path, os.getenv('ORCH_FOUNDER_LOGIN', 'ShubMisra'),
                        autonomy=Autonomy(os.getenv('ORCH_AUTONOMY', 'SUPERVISED')))
    store, git = Store(settings), GitReader()
    ci = CITrust(381492575, '1f69460e79086f27003ce5270f6958408a67fe23')
    return Controller(settings, store, GitHubGateway(ci_trust=ci), MockArchitect(),
                      {'codex': FixtureCommitRunner('codex'),
                       'kilo': FixtureCommitRunner('kilo')}, Verifier(git), git)


def build_pilot(controller: Controller) -> ReadOnlyPilot | None:
    config_path = os.getenv('ORCH_PILOT_CONFIG', '')
    if not config_path:
        return None
    config = json.loads(Path(config_path).resolve(strict=True).read_text(encoding='utf-8'))
    if set(config) != {'profiles', 'tariffs'}:
        raise ValueError('invalid pilot config fields')
    pins = {item['owner']: RuntimePin(**item) for item in config['profiles']}
    tariffs = {(item['owner'], item['provider'], item['model']): ProviderTariff(**item)
               for item in config['tariffs']}
    git_executable = shutil.which('git')
    if not git_executable:
        raise RuntimeError('Git executable unavailable')
    pilot = ReadOnlyPilot(controller.store, controller.settings.root,
                         git_executable, pins, tariffs)
    pilot.recover()
    return pilot


def main():
    if sys.argv[1:] != ['serve']:
        raise SystemExit('Usage: python -m orchestrator serve')
    if len(os.getenv('ORCH_ADMIN_TOKEN', '')) < 16:
        raise SystemExit('Set ORCH_ADMIN_TOKEN to a founder-owned value of at least 16 characters')
    import uvicorn
    controller = build_controller()
    uvicorn.run(create_app(controller, build_pilot(controller)), host='127.0.0.1', port=8091)


if __name__ == '__main__':
    main()
