import subprocess

import pytest

from scripts.local_ingestion_release import approve_release, verify_release


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def release(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "ops/local-ingestion")
    (root / "collector.py").write_text("print('fixture')\n")
    git(root, "add", "collector.py")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-m", "Fixture release")
    state = tmp_path / "operations"
    commit = git(root, "rev-parse", "HEAD")
    approve_release(root, state, branch="ops/local-ingestion", commit=commit)
    return root, state, commit


def test_approved_clean_release_passes_without_database_or_network(release):
    root, state, commit = release
    assert verify_release(root, state) == {"branch": "ops/local-ingestion", "commit": commit}
    (root / "tmp").mkdir()
    (root / "tmp" / "analysis.py").write_text("# local analysis\n")
    assert verify_release(root, state)["commit"] == commit


@pytest.mark.parametrize("mutation", ["dirty", "staged", "branch", "commit", "untracked", "missing"])
def test_release_drift_is_rejected(release, mutation):
    root, state, commit = release
    if mutation in {"dirty", "staged", "commit"}:
        (root / "collector.py").write_text("print('changed')\n")
        if mutation != "dirty":
            git(root, "add", "collector.py")
        if mutation == "commit":
            git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-m", "Unapproved change")
    elif mutation == "branch":
        git(root, "switch", "-c", "experiment")
    elif mutation == "untracked":
        (root / "scripts").mkdir()
        (root / "scripts" / "new_collector.py").write_text("# unreviewed\n")
    else:
        (state / "approved-ingestion-release.json").unlink()
    with pytest.raises(ValueError):
        verify_release(root, state)


def test_approval_cannot_bless_another_commit_or_branch(release):
    root, state, commit = release
    with pytest.raises(ValueError):
        approve_release(root, state, branch="main", commit=commit)
    with pytest.raises(ValueError):
        approve_release(root, state, branch="ops/local-ingestion", commit="0" * 40)
