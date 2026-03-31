"""Task selection filter maps UI buttons to YAML category strings."""

from cccb.screens.task_select import TASK_FILTER_BUTTONS


def test_filter_button_ids_map_to_yaml_categories() -> None:
    by_id = {bid: ck for _, bid, ck in TASK_FILTER_BUTTONS}
    assert by_id["filter_all"] is None
    assert by_id["filter_codegen"] == "codegen"
    assert by_id["filter_debugging"] == "debugging"
    assert by_id["filter_refactoring"] == "refactoring"
