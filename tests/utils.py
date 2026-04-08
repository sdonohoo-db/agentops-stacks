import os
import pathlib
import pytest
import json
import subprocess
from functools import wraps

RESOURCE_TEMPLATE_ROOT_DIRECTORY = str(pathlib.Path(__file__).parent.parent)

AZURE_DEFAULT_PARAMS = {
    "input_setup_cicd_and_project": "CICD_and_Project",
    "input_root_dir": "my-agentops-project",
    "input_project_name": "my-agentops-project",
    "input_cloud": "azure",
    "input_cicd_platform": "github_actions",
}

AWS_DEFAULT_PARAMS = {
    **AZURE_DEFAULT_PARAMS,
    "input_cloud": "aws",
}

GCP_DEFAULT_PARAMS = {
    **AZURE_DEFAULT_PARAMS,
    "input_cloud": "gcp",
}


def parametrize_by_cloud(fn):
    @wraps(fn)
    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


def parametrize_by_project_generation_params(fn):
    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    @pytest.mark.parametrize(
        "cicd_platform",
        [
            "github_actions",
            "github_actions_for_github_enterprise_servers",
            "azure_devops",
        ],
    )
    @pytest.mark.parametrize(
        "setup_cicd_and_project",
        [
            "CICD_and_Project",
            "Project_Only",
            "CICD_Only",
        ],
    )
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


@pytest.fixture
def generated_project_dir(
    tmpdir,
    databricks_cli,
    cloud,
    cicd_platform,
    setup_cicd_and_project,
):
    params = {
        "input_setup_cicd_and_project": setup_cicd_and_project,
        "input_root_dir": "my-agentops-project",
        "input_cloud": cloud,
    }
    if setup_cicd_and_project != "Project_Only":
        params["input_cicd_platform"] = cicd_platform
    if setup_cicd_and_project != "CICD_Only":
        params["input_project_name"] = "my-agentops-project"
    generate(tmpdir, databricks_cli, params)
    return tmpdir


def read_workflow(tmpdir):
    return (tmpdir / "my-agentops-project" / ".github/workflows/my-agentops-project-run-tests.yml").read_text(
        "utf-8"
    )


def markdown_checker_configs(tmpdir):
    markdown_checker_config_dict = {
        "ignorePatterns": [
            {"pattern": "http://127.0.0.1:5000"},
        ],
        "httpHeaders": [
            {
                "urls": ["https://docs.github.com/"],
                "headers": {"Accept-Encoding": "zstd, br, gzip, deflate"},
            },
        ],
    }

    file_name = "checker-config.json"

    with open(tmpdir / "my-agentops-project" / file_name, "w") as outfile:
        json.dump(markdown_checker_config_dict, outfile)


def generate(directory, databricks_cli, context):
    if context.get("input_cloud") == "aws":
        default_params = AWS_DEFAULT_PARAMS
    elif context.get("input_cloud") == "gcp":
        default_params = GCP_DEFAULT_PARAMS
    else:
        default_params = AZURE_DEFAULT_PARAMS
    params = {
        **default_params,
        **context,
    }
    json_string = json.dumps(params)
    config_file = directory / "config.json"
    config_file.write(json_string)
    subprocess.run(
        f"echo dapi123 | {databricks_cli} configure --host https://123",
        shell=True,
        check=True,
    )
    subprocess.run(
        f"{databricks_cli} bundle init {RESOURCE_TEMPLATE_ROOT_DIRECTORY} --config-file {config_file} --output-dir {directory}",
        shell=True,
        check=True,
    )


@pytest.fixture(scope="session")
def databricks_cli(tmp_path_factory):
    # create tools dir
    tool_dir = tmp_path_factory.mktemp("tools")
    # copy script and make it executable
    install_script_path = os.path.join(os.path.dirname(__file__), "install.sh")
    # download databricks cli
    databricks_cli_dir = tool_dir / "databricks_cli"
    databricks_cli_dir.mkdir()
    subprocess.run(
        ["bash", install_script_path, databricks_cli_dir],
        capture_output=True,
        text=True,
    )

    yield f"{databricks_cli_dir}/databricks"
    # no need to remove the files as they are in test temp dir


def paths(directory):
    paths = list(pathlib.Path(directory).glob("**/*"))
    paths = [r.relative_to(directory) for r in paths]
    return {str(f) for f in paths if str(f) != "."}
