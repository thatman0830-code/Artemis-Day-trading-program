from scripts.audit_oracle_shadow_project import audit


def test_clear_project_is_still_not_automatically_deployable(tmp_path):
    (tmp_path / "oracle.py").write_text("def observe(): return 'NEUTRAL'")
    result=audit(tmp_path)
    assert result["state"]=="STATIC_PREFLIGHT_CLEAR"
    assert result["deployment_permitted"] is False and result["trading_authority"] is False


def test_order_or_secret_surfaces_require_review(tmp_path):
    (tmp_path / "engine.py").write_text("private_key = x\nplace_order(y)\n")
    result=audit(tmp_path)
    assert result["state"]=="REVIEW_REQUIRED"
    assert {x["code"] for x in result["findings"]} == {
        "PRIVATE_KEY_REFERENCE", "ORDER_SUBMISSION_SURFACE"}
