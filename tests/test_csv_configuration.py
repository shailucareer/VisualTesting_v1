from core.runner import TestRunner


def test_load_test_cases_from_csv(tmp_path):
    config_path = tmp_path / "testcases.csv"
    config_path.write_text(
        "name,run,device,figma_file_name,url,figma_file_id,figma_node_id,"
        "page_data_load_wait,run_mode,baseline_mode,figma_access_token\n"
        "home,false,Mobile,home.png,https://example.com,,,,selected,figma,token\n"
        "checkout,true,Desktop,,,,node-1,8,,,\n",
        encoding="utf-8",
    )

    runner = object.__new__(TestRunner)
    runner.project_path = tmp_path
    runner.config_baseline_mode = "auto"
    runner.run_mode = "selected"
    runner.target_test_name = None

    cases = runner._load_test_cases()

    assert [case.name for case in cases] == ["home", "checkout"]
    assert cases[0].run is False
    assert cases[0].device == "Mobile"
    assert cases[0].figma_access_token == "token"
    assert cases[0].page_data_load_wait == 3
    assert cases[1].run is True
    assert cases[1].figma_node_id == "node-1"
    assert cases[1].page_data_load_wait == 8
    assert runner.run_mode == "selected"
    assert runner.config_baseline_mode == "figma"