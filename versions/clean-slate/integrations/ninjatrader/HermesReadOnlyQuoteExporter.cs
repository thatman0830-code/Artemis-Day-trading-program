#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    // Read-only chart indicator. It has no account, strategy, or order API surface.
    public class HermesReadOnlyQuoteExporter : Indicator
    {
        private double bid;
        private double ask;
        private double last;
        private long lastVolume;
        private long sequence;

        [NinjaScriptProperty]
        [Display(Name = "Output directory", Order = 1, GroupName = "Hermes")]
        public string OutputDirectory { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "HermesReadOnlyQuoteExporter";
                Description = "Exports sanitized MES/MNQ quotes; never submits orders.";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;
                OutputDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "HermesQuoteBridge");
            }
            else if (State == State.DataLoaded)
            {
                string root = Instrument.MasterInstrument.Name.ToUpperInvariant();
                if (root != "MES" && root != "MNQ")
                    throw new InvalidOperationException("Only MES and MNQ are permitted");
                if (!Path.IsPathRooted(OutputDirectory))
                    throw new InvalidOperationException("Output directory must be absolute");
                Directory.CreateDirectory(OutputDirectory);
            }
        }

        protected override void OnMarketData(MarketDataEventArgs update)
        {
            if (update.MarketDataType == MarketDataType.Bid) bid = update.Price;
            else if (update.MarketDataType == MarketDataType.Ask) ask = update.Price;
            else if (update.MarketDataType == MarketDataType.Last) { last = update.Price; lastVolume = update.Volume; }
            else return;
            if (bid <= 0 || ask <= 0 || last <= 0 || ask < bid) return;
            sequence++;
            WriteSnapshot(DateTime.UtcNow);
        }

        private void WriteSnapshot(DateTime capturedAt)
        {
            string instrument = Instrument.FullName.Replace("\\", "\\\\").Replace("\"", "\\\"");
            string core = string.Format(CultureInfo.InvariantCulture,
                "{{\"ask\":{0:R},\"bid\":{1:R},\"captured_at_utc\":\"{2:o}\",\"instrument\":\"{3}\",\"last\":{4:R},\"last_volume\":{5},\"paper_only\":true,\"schema_version\":\"ninjatrader-read-only-quote-v1\",\"sequence\":{6},\"source\":\"NINJATRADER_SIMULATION\",\"trading_authority\":false}}",
                ask, bid, capturedAt, instrument, last, lastVolume, sequence);
            string digest;
            using (SHA256 sha = SHA256.Create())
                digest = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(core))).Replace("-", "").ToLowerInvariant();
            string document = core.Substring(0, core.Length - 1) + ",\"payload_sha256\":\"" + digest + "\"}\n";
            string target = Path.Combine(OutputDirectory, Instrument.MasterInstrument.Name.ToUpperInvariant() + ".quote.json");
            string temporary = target + ".tmp";
            File.WriteAllText(temporary, document, new UTF8Encoding(false));
            if (File.Exists(target)) File.Replace(temporary, target, null); else File.Move(temporary, target);
        }

        protected override void OnBarUpdate() { }
    }
}
