"""The repository layout is a contract too, and this is what holds it.

A structure that exists only in a README is a suggestion. Everything asserted here was
either decided deliberately or learned the hard way, and each rule names which — so a
later change either satisfies it or has to argue with a specific reason rather than with
an unexplained convention. See ADR 0003.

This is deliberately about *shape*, never about content. It does not care what an ADR
argues, only that decisions get recorded as ADRs; not what a spec says, only that specs
carry the sections the workflow depends on.

**Adapted from agentic-sdlc-eventbus, and inverted in one place on purpose.** That
repository is a library three repos install, so it asserts its package lives under
`src/`. This one is an application nothing installs, so it asserts the opposite. Copying
that file here unchanged would assert the reverse of what this repository decided — see
ADR 0002.
"""

import subprocess
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "url_shortener"
TIERS = ("unit", "contract", "integration", "evaluation")


# --- the package ---------------------------------------------------------------------


def test_the_package_lives_at_the_repository_root():
    # Not under src/. The container resolves this package because WORKDIR /app puts the
    # working directory on sys.path; a src/ move breaks that build unless the app also
    # starts installing itself, which is ceremony an application does not need. ADR 0002.
    assert PACKAGE.is_dir()
    assert not (REPO / "src").exists(), "no src/ layout here - see ADR 0002"


def test_nothing_turns_this_application_into_a_distribution():
    # A [project] table or a build backend would mean something installs this. Nothing
    # does, and the moment one appears the Dockerfile's assumptions stop being true.
    #
    # Parsed rather than grepped: the first version of this test substring-matched
    # "[project]" and failed on the comment in pyproject.toml explaining why there
    # isn't one.
    assert not (REPO / "setup.py").exists()
    assert not (REPO / "setup.cfg").exists()
    with (REPO / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert set(pyproject) <= {"tool"}, (
        f"pyproject.toml must carry [tool.*] only; found {sorted(pyproject)} - see ADR 0002"
    )


def test_every_module_the_service_needs_is_present():
    expected = {
        "__init__.py",
        "auth.py",
        "db.py",
        "main.py",
        "models.py",
        "rate_limit.py",
        "repository.py",
        "schemas.py",
        "telemetry.py",
    }
    assert expected <= {p.name for p in PACKAGE.glob("*.py")}


def test_tool_configuration_is_not_scattered():
    # pytest.ini and .coveragerc were folded into pyproject.toml. Two files claiming to
    # configure the same run is how they drift apart.
    assert (REPO / "pyproject.toml").is_file()
    assert not (REPO / "pytest.ini").exists()
    assert not (REPO / ".coveragerc").exists()


# --- tests -----------------------------------------------------------------------------


def test_every_test_lives_in_one_of_the_four_tiers():
    # CI can select by marker, so a test outside a tier would be collected, counted as
    # passing, and never actually run by the filtered command. conftest.py turns this
    # into a collection error at runtime; this asserts the layout that makes it possible.
    strays = [p.name for p in (REPO / "tests").glob("test_*.py") if p.parent.name not in TIERS]
    assert strays == [], f"move these into tests/{{{','.join(TIERS)}}}/: {strays}"


def test_all_four_tiers_exist_and_none_is_empty():
    for tier in TIERS:
        directory = REPO / "tests" / tier
        assert directory.is_dir(), f"missing tier: tests/{tier}/"
        assert list(directory.glob("test_*.py")), f"tests/{tier}/ has no tests"


def test_the_shared_fixtures_stay_at_the_tests_root():
    # The client fixture is used from more than one tier, and the tier directories are
    # siblings: a fixture defined in one is not visible from the other.
    assert (REPO / "tests" / "conftest.py").is_file()
    for tier in TIERS:
        assert not (REPO / "tests" / tier / "conftest.py").exists(), (
            f"tests/{tier}/conftest.py would hide fixtures from the sibling tiers"
        )


def test_the_marker_hook_derives_tiers_from_the_directory():
    # The one rule that has to exist in code rather than in prose. A test with no marker
    # is collected, counted in "passed", and skipped entirely by a marker-filtered run;
    # --strict-markers catches a misspelled marker, never a missing one.
    conftest = (REPO / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "pytest_collection_modifyitems" in conftest
    assert "UsageError" in conftest, "a stray test must fail collection, not run unmarked"


def test_every_tier_is_a_registered_marker():
    # An unregistered marker is a warning today and an error under --strict-markers,
    # which is enabled. A tier directory with no matching marker breaks every filtered run.
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "--strict-markers" in pyproject
    for tier in TIERS:
        assert f'"{tier}:' in pyproject, f"tier {tier} is not a registered marker"


def test_the_evaluation_tier_carries_its_verification_report():
    # Most of what can go wrong at the telemetry seam cannot be reached by a unit test,
    # so the report is a primary QA artefact rather than a supplement. Article III.
    assert (REPO / "tests" / "evaluation" / "REPORT.md").is_file()


# --- the spec-driven layer -------------------------------------------------------------


def test_the_constitution_and_every_template_are_present():
    assert (REPO / ".specify" / "memory" / "constitution.md").is_file()
    templates = REPO / ".specify" / "templates"
    for name in ("spec", "plan", "tasks"):
        assert (templates / f"{name}-template.md").is_file(), f"missing {name}-template.md"


def test_every_spec_directory_is_numbered_and_complete():
    specs = sorted(d for d in (REPO / "specs").iterdir() if d.is_dir())
    assert specs, "specs/ must hold at least the record of how this layout arrived"
    for spec in specs:
        assert spec.name[:3].isdigit(), f"{spec.name} must start with a three-digit number"
        for required in ("spec.md", "plan.md", "tasks.md"):
            assert (spec / required).is_file(), f"{spec.name} is missing {required}"


def test_spec_numbers_are_unique():
    numbers = [d.name[:3] for d in (REPO / "specs").iterdir() if d.is_dir()]
    assert len(numbers) == len(set(numbers))


# --- decisions and governance ----------------------------------------------------------


def test_adrs_are_numbered_without_gaps_or_duplicates():
    # A gap means an ADR was deleted rather than superseded, and a superseded decision
    # still has to be readable or the record is worse than none.
    adrs = (REPO / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")
    numbers = sorted(int(p.name[:4]) for p in adrs)
    assert numbers, "docs/adr/ must hold at least ADR 0001"
    assert numbers == list(range(1, len(numbers) + 1)), f"ADR numbering has a gap: {numbers}"


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "CLAUDE.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "pyproject.toml",
        "requirements.txt",
        "requirements.lock",
        "Dockerfile",
        "docker-compose.yml",
        ".github/CODEOWNERS",
        ".github/dependabot.yml",
    ],
)
def test_required_root_file_exists(path):
    assert (REPO / path).is_file(), f"missing {path}"


@pytest.mark.parametrize("workflow", ["ci.yml", "security.yml"])
def test_required_workflow_exists(workflow):
    assert (REPO / ".github" / "workflows" / workflow).is_file()


def test_the_readme_follows_the_section_order_claude_md_mandates():
    # CLAUDE.md fixes this order and says "nothing else". It was not being followed, and
    # a documentation standard nothing checks is a preference.
    headings = [
        line[3:].strip()
        for line in (REPO / "README.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]
    assert headings == [
        "Tech stack",
        "Architecture",
        "Quickstart",
        "Local development",
        "Testing",
        "Deployment and CI",
    ], f"README top-level sections are {headings}"


def test_the_required_ci_job_names_are_unchanged():
    # Required status checks match a job's *display name*. Renaming one leaves branch
    # protection waiting on a context nothing reports: every check green, the pull
    # request stuck at BLOCKED. The ruleset on main requires exactly these two.
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "\n  test:\n" in ci, "the required check `test` was renamed"
    assert "\n  compose-smoke-test:\n" in ci, "the required check `compose-smoke-test` was renamed"


def test_the_security_workflow_is_not_path_filtered():
    # A path-filtered workflow does not report on a pull request outside its paths, so
    # requiring its check blocks those pull requests forever. This one is not required
    # today, and this assertion keeps it safe to require later.
    security = (REPO / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    assert "paths:" not in security, "a path-filtered check must never become required"


def test_local_compose_overrides_are_ignored_not_committed():
    # Compose merges .env and docker-compose.override.yml automatically from beside
    # docker-compose.yml, silently. Committing either would apply one developer's local
    # overrides to everybody. They may exist on a machine; they must never be tracked.
    ignored = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored
    assert "docker-compose.override.yml" in ignored


def test_only_example_templates_are_tracked_under_secrets():
    # .gitignore covers the ordinary case; this covers the one it cannot, a file added
    # with `git add -f` or committed before the rule existed.
    #
    # Asks git, not the filesystem. The first version of this test listed the directory
    # and failed on a developer's real, correctly-ignored local secret - which is the
    # normal state of a working tree and none of this test's business. What is tracked
    # is the contract; what exists on a machine is not.
    tracked = subprocess.run(
        ["git", "ls-files", "secrets/"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    offenders = [name for name in tracked if not name.endswith(".example")]
    assert offenders == [], f"only .example templates belong under secrets/: {offenders}"


# --- scripts ---------------------------------------------------------------------------


def test_required_script_exists():
    assert (REPO / "scripts" / "validate-mermaid.mjs").is_file()


def test_python_scripts_use_underscores_so_the_contract_tier_can_import_them():
    # There are no Python scripts yet; the rule is here for the first one. A hyphenated
    # module name cannot be imported, and the contract tier imports what it verifies.
    offenders = [p.name for p in (REPO / "scripts").glob("*.py") if "-" in p.stem]
    assert offenders == [], f"rename to underscores; tests import these: {offenders}"
