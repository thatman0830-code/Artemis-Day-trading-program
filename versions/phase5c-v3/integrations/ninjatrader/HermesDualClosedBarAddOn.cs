#region Using declarations
using System;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    // Read-only complete-bar export. No account, strategy, or order API is used.
    public class HermesDualClosedBarAddOn : AddOnBase
    {
        private BarsRequest mesRequest;
        private BarsRequest mnqRequest;
        private DateTime mesLastClose = DateTime.MinValue;
        private DateTime mnqLastClose = DateTime.MinValue;
        private string outputDirectory;
        private readonly object requestGate = new object();

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "HermesDualClosedBarAddOn";
                Description = "Exports completed MES/MNQ one-minute bars; never submits orders.";
            }
            else if (State == State.Active)
            {
                outputDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "HermesBarBridge");
                Directory.CreateDirectory(outputDirectory);
                Connection.ConnectionStatusUpdate += OnConnectionStatusUpdate;
                RefreshRequests();
            }
            else if (State == State.Terminated)
            {
                Connection.ConnectionStatusUpdate -= OnConnectionStatusUpdate;
                DisposeRequest(ref mesRequest, OnMesBars);
                DisposeRequest(ref mnqRequest, OnMnqBars);
            }
        }

        private void OnConnectionStatusUpdate(object sender, ConnectionStatusEventArgs update)
        {
            if (State != State.Active) return;
            if (update.PriceStatus == ConnectionStatus.Connected) RefreshRequests();
            else if (update.PriceStatus == ConnectionStatus.Disconnected)
                lock (requestGate)
                {
                    DisposeRequest(ref mesRequest, OnMesBars);
                    DisposeRequest(ref mnqRequest, OnMnqBars);
                }
        }

        private void RefreshRequests()
        {
            lock (requestGate)
            {
                DisposeRequest(ref mesRequest, OnMesBars);
                DisposeRequest(ref mnqRequest, OnMnqBars);
                mesRequest = Subscribe("MES SEP26", OnMesBars);
                mnqRequest = Subscribe("MNQ SEP26", OnMnqBars);
            }
        }

        private BarsRequest Subscribe(string fullName, EventHandler<BarsUpdateEventArgs> handler)
        {
            Instrument instrument = Instrument.GetInstrument(fullName);
            if (instrument == null) throw new InvalidOperationException("Required instrument unavailable: " + fullName);
            BarsRequest request = new BarsRequest(instrument, 10);
            request.BarsPeriod = new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 1 };
            request.TradingHours = TradingHours.Get("CME US Index Futures ETH");
            request.LookupPolicy = LookupPolicies.Provider;
            request.MergePolicy = MergePolicy.DoNotMerge;
            request.Update += handler;
            request.Request((bars, errorCode, errorMessage) =>
            {
                if (errorCode != ErrorCode.NoError) return;
                ExportCompletedHistory(fullName.StartsWith("MES", StringComparison.Ordinal) ? "MES" : "MNQ", bars.Bars);
            });
            return request;
        }

        private void DisposeRequest(ref BarsRequest request, EventHandler<BarsUpdateEventArgs> handler)
        {
            if (request == null) return;
            request.Update -= handler;
            request.Dispose();
            request = null;
        }

        private void OnMesBars(object sender, BarsUpdateEventArgs update)
        {
            int completed = update.BarsSeries.Count - 2;
            ExportCompletedUpdates("MES", update.BarsSeries, completed, completed);
        }

        private void OnMnqBars(object sender, BarsUpdateEventArgs update)
        {
            int completed = update.BarsSeries.Count - 2;
            ExportCompletedUpdates("MNQ", update.BarsSeries, completed, completed);
        }

        private void ExportCompletedHistory(string root, Bars bars)
        {
            for (int index = 0; index <= bars.Count - 2; index++)
                ExportOne(root, bars.GetTime(index), bars.GetOpen(index), bars.GetHigh(index),
                    bars.GetLow(index), bars.GetClose(index), bars.GetVolume(index));
        }

        private void ExportCompletedUpdates(string root, BarsSeries bars, int first, int lastIndex)
        {
            for (int index = Math.Max(0, first); index <= lastIndex; index++)
                ExportOne(root, bars.GetTime(index), bars.GetOpen(index), bars.GetHigh(index),
                    bars.GetLow(index), bars.GetClose(index), bars.GetVolume(index));
        }

        private void ExportOne(string root, DateTime closeLocal, double open, double high, double low, double close, long volume)
        {
            DateTime closeUtc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(closeLocal, DateTimeKind.Unspecified), Core.Globals.GeneralOptions.TimeZoneInfo);
            DateTime prior = root == "MES" ? mesLastClose : mnqLastClose;
            if (closeUtc <= prior) return;
            WriteBar(root, root == "MES" ? "MES SEP26" : "MNQ SEP26", closeUtc.AddMinutes(-1), closeUtc,
                open, high, low, close, volume);
            if (root == "MES") mesLastClose = closeUtc; else mnqLastClose = closeUtc;
        }

        private void WriteBar(string root, string fullName, DateTime openUtc, DateTime closeUtc,
                              double open, double high, double low, double close, long volume)
        {
            string instrument = fullName.Replace("\\", "\\\\").Replace("\"", "\\\"");
            string core = string.Format(CultureInfo.InvariantCulture,
                "{{\"close\":{0:R},\"close_time_utc\":\"{1:o}\",\"exchange\":\"XCME\",\"high\":{2:R},\"instrument\":\"{3}\",\"is_closed\":true,\"low\":{4:R},\"open\":{5:R},\"open_time_utc\":\"{6:o}\",\"paper_only\":true,\"schema_version\":\"ninjatrader-closed-bar-v1\",\"source\":\"NINJATRADER_SIMULATION\",\"timeframe\":\"1m\",\"trading_authority\":false,\"volume\":{7}}}",
                close, closeUtc, high, instrument, low, open, openUtc, volume);
            string digest;
            using (SHA256 sha = SHA256.Create())
                digest = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(core))).Replace("-", "").ToLowerInvariant();
            string document = core.Substring(0, core.Length - 1) + ",\"payload_sha256\":\"" + digest + "\"}\n";
            string target = Path.Combine(outputDirectory, root + ".bar.json");
            string temporary = target + ".tmp";
            File.WriteAllText(temporary, document, new UTF8Encoding(false));
            if (File.Exists(target)) File.Replace(temporary, target, null); else File.Move(temporary, target);
        }
    }
}
