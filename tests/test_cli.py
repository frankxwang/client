import pytest, os, traceback
from wandb import cli, Api
from click.testing import CliRunner
from .api_mocks import *
import netrc, signal, time
import six, time, inquirer

@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr(cli, 'api', Api(load_config=False))
    monkeypatch.setattr(inquirer, 'prompt', lambda x: {'model': 'test_model', 'files': ['weights.h5']})
    return CliRunner()

@pytest.fixture
def empty_netrc(monkeypatch):
    monkeypatch.setattr(netrc, "netrc", lambda x: {'hosts': []})

@pytest.fixture
def local_netrc(monkeypatch):
    #TODO: this seems overkill...
    origexpand = os.path.expanduser
    def expand(path):
        return os.path.realpath("netrc") if "netrc" in path else origexpand(path)
    monkeypatch.setattr(os.path, "expanduser", expand)

def test_help(runner):
    result = runner.invoke(cli.cli)
    assert result.exit_code == 0
    assert 'Console script for Weights & Biases' in result.output
    help_result = runner.invoke(cli.cli, ['--help'])
    assert help_result.exit_code == 0
    assert '--help  Show this message and exit.' in help_result.output

def test_config(runner, request_mocker, query_models, monkeypatch):
    query_models(request_mocker)
    with runner.isolated_filesystem():
        with open('.wandb', 'w') as f:
            f.write("""[default]
model: cli_test
entity: cli_test
            """)
        monkeypatch.setattr(cli, 'api', Api())
        result = runner.invoke(cli.config)
        assert "cli_test" in result.output

def test_push(runner, request_mocker, query_model, upload_url):
    query_model(request_mocker)
    upload_url(request_mocker)
    with runner.isolated_filesystem():
        with open('weights.h5', 'wb') as f:
            f.write(os.urandom(5000))
        result = runner.invoke(cli.push, ['default', 'weights.h5', '--model', 'test', '-m', 'My description'])
        print(result.output)
        print(result.exception)
        print(traceback.print_tb(result.exc_info[2]))
        assert result.exit_code == 0
        assert "Uploading model: test" in result.output

def test_push_no_bucket(runner):
    with runner.isolated_filesystem():
        with open('weights.h5', 'wb') as f:
            f.write(os.urandom(5000))
        result = runner.invoke(cli.push, ['weights.h5', '-M', 'test', '-m', 'Something great'])
        print(result.output)
        print(result.exception)
        print(traceback.print_tb(result.exc_info[2]))
        assert result.exit_code == 2
        assert "Bucket is required if files are specified." in result.output

def test_push_auto(runner, request_mocker, mocker, query_model, upload_url):
    query_model(request_mocker)
    upload_url(request_mocker)
    edit_mock = mocker.patch("click.edit")
    with runner.isolated_filesystem():
        with open('weights.h5', 'wb') as f:
            f.write(os.urandom(5000))
        with open('fake.json', 'wb') as f:
            f.write(os.urandom(100))
        result = runner.invoke(cli.push, ['--model', 'test', '-m', 'Testing'])
        print(result.output)
        print(result.exception)
        print(traceback.print_tb(result.exc_info[2]))
        assert result.exit_code == 0
        assert "Uploading file: weights.h5" in result.output
        #TODO: test without specifying message
        #assert edit_mock.called

def test_pull(runner, request_mocker, query_model, download_url):
    query_model(request_mocker)
    download_url(request_mocker)
    with runner.isolated_filesystem():
        result = runner.invoke(cli.pull, ['--model', 'test'])
        
        print(result.output)
        print(result.exception)
        print(traceback.print_tb(result.exc_info[2]))
        assert result.exit_code == 0
        assert "Downloading model: test" in result.output
        assert os.path.isfile("weights.h5")
        assert "Downloading model" in result.output
        assert "Downloading weights" in result.output

def test_models(runner, request_mocker, query_models):
    query_models(request_mocker)
    result = runner.invoke(cli.models)
    assert result.exit_code == 0
    assert "test_2 - Test model" in result.output

def test_status(runner, request_mocker, query_model):
    query_model(request_mocker)
    result = runner.invoke(cli.status)
    assert result.exit_code == 0
    assert "/default" in result.output

def test_status_model_and_bucket(runner, request_mocker, query_model):
    query_model(request_mocker)
    result = runner.invoke(cli.status, ["test/awesome"])
    assert result.exit_code == 0
    assert "test/awesome" in result.output

def test_add(runner):
    with runner.isolated_filesystem():
        with open("test.h5", "w") as f:
            f.write("fake data")
        with open(".wandb", "w") as f:
            f.write("[default]\nfiles: test.json")
        result = runner.invoke(cli.add, ["test.h5"])
        assert result.exit_code == 0
        assert "test.h5" in result.output
        assert "test.json" in result.output

def test_add_no_config(runner):
    with runner.isolated_filesystem():
        with open("test.h5", "w") as f:
            f.write("fake data")
        result = runner.invoke(cli.add, ["test.h5"])
        print(result.output)
        assert result.exit_code == 1
        assert "Directory not configured" in result.output

def test_rm(runner):
    with runner.isolated_filesystem():
        with open(".wandb", "w") as f:
            f.write("[default]\nfiles: test.h5,test.json")
        result = runner.invoke(cli.rm, ["test.h5"])
        assert result.exit_code == 0
        assert "test.json" in result.output
        assert "test.h5" not in result.output

def test_models_error(runner, request_mocker, query_models):
    query_models(request_mocker, status_code=400)
    result = runner.invoke(cli.models)
    assert result.exit_code == 1
    print(result.output)
    assert "Error" in result.output

def test_init_new_login(runner, empty_netrc, local_netrc, request_mocker, query_models):
    query_models(request_mocker)
    with runner.isolated_filesystem():
        result = runner.invoke(cli.init, input="12345\nvanpelt")
        assert result.exit_code == 0
        with open("netrc", "r") as f:
            generatedNetrc = f.read()
        with open(".wandb", "r") as f:
            generatedWandb = f.read()
        assert "12345" in generatedNetrc
        assert "test_model" in generatedWandb

def test_init_add_login(runner, empty_netrc, local_netrc, request_mocker, query_models):
    query_models(request_mocker)
    with runner.isolated_filesystem():
        with open("netrc", "w") as f:
            f.write("previous config")
        result = runner.invoke(cli.init, input="12345\nvanpelt\n")
        print(result.output)
        print(traceback.print_tb(result.exc_info[2]))
        assert result.exit_code == 0
        with open("netrc", "r") as f:
            generatedNetrc = f.read()
        with open(".wandb", "r") as f:
            generatedWandb = f.read()
        assert "12345" in generatedNetrc
        assert "previous config" in generatedNetrc

def test_existing_login(runner, local_netrc, request_mocker, query_models):
    query_models(request_mocker)
    with runner.isolated_filesystem():
        with open("netrc", "w") as f:
            f.write("machine api.wandb.ai\n\ttest\t12345")
        result = runner.invoke(cli.init, input="vanpelt\n")
        print(result.output)
        print(result.exception)
        print(traceback.print_tb(result.exc_info[2]))
        assert result.exit_code == 0
        with open(".wandb", "r") as f:
            generatedWandb = f.read()
        assert "test_model" in generatedWandb
        assert "This directory is configured" in result.output
