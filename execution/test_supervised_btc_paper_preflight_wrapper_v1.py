from pathlib import Path


def test_wrapper_is_read_only_explicit_and_ambiguity_safe():
    source=(Path(__file__).parents[1]/"scripts"/"invoke_supervised_btc_paper_preflight.ps1").read_text("utf-8")
    lowered=source.lower()
    assert "-confirmsupervision" in lowered and "-confirmstopcontrol" in lowered
    assert "newguid().tostring('n')" in lowered
    assert "newest $label artifact is ambiguous" in lowered
    assert "newest btc forward archive is ambiguous" in lowered
    assert "execution.supervised_btc_paper_preflight_v1" in lowered
    for prohibited in ("new-item","set-content","out-file","start-scheduledtask","enable-scheduledtask"):
        assert prohibited not in lowered
