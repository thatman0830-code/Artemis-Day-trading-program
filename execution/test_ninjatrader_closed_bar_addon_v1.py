from pathlib import Path

def test_closed_bar_addon_is_dual_exact_unmerged_and_read_only():
 source=(Path(__file__).parents[1]/"integrations/ninjatrader/HermesDualClosedBarAddOn.cs").read_text()
 assert 'Subscribe("MES SEP26", OnMesBars)' in source
 assert 'Subscribe("MNQ SEP26", OnMnqBars)' in source
 assert "BarsPeriodType.Minute, Value = 1" in source
 assert "MergePolicy.DoNotMerge" in source and "LookupPolicies.Provider" in source
 assert "bars.Count - 2" in source and source.count("int completed = update.BarsSeries.Count - 2") == 2
 assert "ExportCompletedHistory" in source and "ExportCompletedUpdates" in source
 assert '"is_closed\\\":true' in source and '"trading_authority\\\":false' in source
 for prohibited in ("SubmitOrder","CreateOrder","Account.","PositionUpdate","ExecutionUpdate","HttpClient","Socket","TcpClient"):
  assert prohibited not in source

def test_closed_bar_addon_unsubscribes_and_disposes_both_requests():
 source=(Path(__file__).parents[1]/"integrations/ninjatrader/HermesDualClosedBarAddOn.cs").read_text()
 assert "request.Update -= handler" in source and "request.Dispose()" in source
 assert "DisposeRequest(ref mesRequest, OnMesBars)" in source
 assert "DisposeRequest(ref mnqRequest, OnMnqBars)" in source
 assert "OnConnectionStatusUpdate" in source and "ConnectionStatus.Connected" in source
 assert "RefreshRequests()" in source and "requestGate" in source
