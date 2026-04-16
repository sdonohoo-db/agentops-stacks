import os
import pathlib
import pytest
import subprocess
from utils import (
    read_workflow,
    generate,
    databricks_cli,
    markdown_checker_configs,
    paths,
    generated_project_dir,
    parametrize_by_cloud,
    parametrize_by_project_generation_params,
)
from unittest import mock

DEFAULT_PROJECT_NAME = "my-agentops-project"
DEFAULT_PROJECT_DIRECTORY = "my_agentops_project"
# UUID that when set as project name, prevents the removal of files needed in testing
TEST_PROJECT_NAME = "27896cf3-bb3e-476e-8129-96df0406d5c7"
TEST_PROJECT_DIRECTORY = "27896cf3_bb3e_476e_8129_96df0406d5c7"


def assert_no_disallowed_strings_in_files(
    file_paths, disallowed_strings, exclude_path_matches=None
):
    """
    Assert that all files in file_paths, besides those with paths containing
    one of exclude_path_matches as a substring, do not contain any of the specified disallowed strings
    """
    if exclude_path_matches is None:
        exclude_path_matches = []
    # Exclude binary files like pngs from being string-matched
    exclude_path_matches = exclude_path_matches + [".png", ".parquet", ".tar.gz"]
    for path in file_paths:
        assert os.path.exists(path), "Provided nonexistent path to test: %s" % path

    def assert_no_disallowed_strings(filepath):
        with open(filepath, "r") as f:
            data = f.read()
        for s in disallowed_strings:
            assert s not in data

    def should_check_file_for_disallowed_strings(path):
        return not any(
            substring in path for substring in exclude_path_matches
        ) and os.path.isfile(path)

    test_paths = list(filter(should_check_file_for_disallowed_strings, file_paths))
    for path in test_paths:
        assert_no_disallowed_strings(path)


@parametrize_by_project_generation_params
def test_no_template_strings_after_param_substitution(
    cloud, generated_project_dir
):
    assert_no_disallowed_strings_in_files(
        file_paths=[
            os.path.join(generated_project_dir, path)
            for path in paths(generated_project_dir)
        ],
        disallowed_strings=["{{", "{%", "%}"],
        exclude_path_matches=[".github", ".yml", ".yaml"],
    )


def test_no_databricks_workspace_urls():
    # Test that there are no accidental hardcoded Databricks workspace URLs included in source files
    template_dir = pathlib.Path(__file__).parent.parent / "template"
    test_paths = [os.path.join(template_dir, path) for path in paths(template_dir)]
    assert_no_disallowed_strings_in_files(
        file_paths=test_paths,
        disallowed_strings=[
            "azuredatabricks.net",
            "cloud.databricks.com",
            "gcp.databricks.com",
        ],
    )


def test_no_databricks_doc_strings_before_project_generation():
    template_dir = pathlib.Path(__file__).parent.parent / "template"
    test_paths = [os.path.join(template_dir, path) for path in paths(template_dir)]
    assert_no_disallowed_strings_in_files(
        file_paths=test_paths,
        disallowed_strings=[
            "https://learn.microsoft.com/en-us/azure/databricks",
            "https://docs.databricks.com/",
            "https://docs.gcp.databricks.com/",
        ],
    )


@pytest.mark.large
@parametrize_by_project_generation_params
def test_markdown_links(cloud, generated_project_dir):
    markdown_checker_configs(generated_project_dir)
    subprocess.run(
        """
        npm install -g markdown-link-check@3.10.3
        find . -name \*.md -print0 | xargs -0 -n1 markdown-link-check -c ./checker-config.json
        """,
        shell=True,
        check=True,
        executable="/bin/bash",
        cwd=(generated_project_dir / "my-agentops-project"),
    )


@pytest.mark.parametrize(
    "invalid_params",
    [
        {"input_project_name": "a"},
        {"input_project_name": "a-"},
        {"input_project_name": "Name with spaces"},
        {"input_project_name": "name/with/slashes"},
        {"input_project_name": "name\\with\\backslashes"},
        {"input_project_name": "name.with.periods"},
    ],
)
def test_generate_fails_with_invalid_params(tmpdir, databricks_cli, invalid_params):
    with pytest.raises(Exception):
        generate(tmpdir, databricks_cli, invalid_params)


@pytest.mark.parametrize("valid_params", [{}])
def test_generate_succeeds_with_valid_params(tmpdir, databricks_cli, valid_params):
    generate(tmpdir, databricks_cli, valid_params)


@parametrize_by_project_generation_params
def test_generate_project_with_default_values(
    tmpdir,
    databricks_cli,
    cloud,
    cicd_platform,
    setup_cicd_and_project,
):
    """
    Asserts the default parameter values. If this test fails due to an update
    of the default values, check:
    - The default param value constants in this test are up to date.
    - The default param values in the pre_gen_project.py hook are up to date.
    - The default param values in databricks_template_schema.json are up to date.
    """
    context = {
        "input_project_name": TEST_PROJECT_NAME,
        "input_root_dir": TEST_PROJECT_NAME,
        "input_cloud": cloud,
        "input_cicd_platform": cicd_platform,
    }
    # Testing that Azure is the default option.
    if cloud == "azure":
        del context["input_cloud"]
    generate(tmpdir, databricks_cli, context=context)


def prepareContext(cloud, cicd_platform, setup_cicd_and_project):
    context = {
        "input_setup_cicd_and_project": setup_cicd_and_project,
        "input_project_name": TEST_PROJECT_NAME,
        "input_root_dir": TEST_PROJECT_NAME,
        "input_cloud": cloud,
        "input_cicd_platform": cicd_platform,
    }
    return context


@parametrize_by_project_generation_params
def test_generate_project_agent_structure(
    tmpdir,
    databricks_cli,
    cloud,
    cicd_platform,
    setup_cicd_and_project,
):
    """
    Asserts that generated AgentOps project has agent structure and no ML-only artifacts.
    """
    context = prepareContext(cloud, cicd_platform, setup_cicd_and_project)
    generate(tmpdir, databricks_cli, context=context)
    project_dir = tmpdir / TEST_PROJECT_NAME
    if setup_cicd_and_project != "CICD_Only":
        # new agent-in-app structure
        assert (project_dir / "agent_server" / "agent.py").exists()
        assert (project_dir / "agent_server" / "start_server.py").exists()
        assert (project_dir / "scripts" / "setup.py").exists()
        assert (project_dir / "app.yaml").exists()
        assert (project_dir / "pyproject.toml").exists()
        # old structures removed
        assert not (project_dir / "agent_development").exists()
        assert not (project_dir / "data_preparation").exists()
        assert not (project_dir / "training").exists()
        assert not (project_dir / "feature_engineering").exists()
        assert not (project_dir / "agent_deployment").exists()


def test_generate_project_default_project_name_params(tmpdir, databricks_cli):
    # Asserts default parameter values for parameters that involve the project name
    generate(tmpdir, databricks_cli, context={})
    readme_contents = (tmpdir / DEFAULT_PROJECT_NAME / "README.md").read_text("utf-8")
    assert DEFAULT_PROJECT_NAME in readme_contents
