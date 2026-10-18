"""Start only a local supervised controller; no agent launch at startup."""
import os
import sys
from pathlib import Path

from .architect import MockArchitect
from .controller import Controller
from .github import GitHubGateway
from .policy import Autonomy, Settings
from .runners import FixtureCommitRunner, GitReader, Verifier
from .store import Store
from .web import create_app


def build_controller() -> Controller:
    root = Path(os.getenv('ORCH_WORKTREE_ROOT', str(Path.cwd().parent / 'acq-agent-runs'))).resolve()
    root.mkdir(parents=True, exist_ok=True)
    db_path = Path(os.getenv('ORCH_DB_PATH', str(Path.cwd() / 'data' / 'orchestrator.db'))).resolve()
    settings = Settings(root, db_path, os.getenv('ORCH_FOUNDER_LOGIN', 'ShubMisra'),
                        autonomy=Autonomy(os.getenv('ORCH_AUTONOMY', 'SUPERVISED')))
    store, git = Store(settings), GitReader()
    return Controller(settings, store, GitHubGateway(), MockArchitect(),
                      {'codex': FixtureCommitRunner('codex'),
                       'kilo': FixtureCommitRunner('kilo')}, Verifier(git), git)


def main():
    if sys.argv[1:] != ['serve']:
        raise SystemExit('Usage: python -m orchestrator serve')
    if len(os.getenv('ORCH_ADMIN_TOKEN', '')) < 16:
        raise SystemExit('Set ORCH_ADMIN_TOKEN to a founder-owned value of at least 16 characters')
    import uvicorn
    uvicorn.run(create_app(build_controller()), host='127.0.0.1', port=8091)


if __name__ == '__main__':
    main()
