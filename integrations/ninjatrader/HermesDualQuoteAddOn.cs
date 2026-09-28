#region Using declarations
using System;
using System.Collections.Generic;
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
    // Read-only, process-local L1 subscriptions. No account or order API is used.
    public class HermesDualQuoteAddOn : AddOnBase
    {
        private sealed class QuoteState
        {
            public readonly object Gate = new object();
            public readonly string Root;
            public readonly Instrument Instrument;
            public double Bid;
            public double Ask;
            public double Last;
            public long LastVolume;
            public long Sequence;

            public QuoteState(string root, Instrument instrument)
            {
                Root = root;
                Instrument = instrument;
            }
        }

        private readonly List<QuoteState> subscriptions = new List<QuoteState>();
        private string outputDirectory;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "HermesDualQuoteAddOn";
                Description = "Exports sanitized MES/MNQ quotes; never submits orders.";
            }
            else if (State == State.Active)
            {
                outputDirectory = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "HermesQuoteBridge");
                Directory.CreateDirectory(outputDirectory);
                Subscribe("MES", "MES SEP26", OnMesMarketData);
                Subscribe("MNQ", "MNQ SEP26", OnMnqMarketData);
            }
            else if (State == State.Terminated)
            {
                Unsubscribe("MES", OnMesMarketData);
                Unsubscribe("MNQ", OnMnqMarketData);
                subscriptions.Clear();
            }
        }

        private void Subscribe(string root, string fullName, EventHandler<MarketDataEventArgs> handler)
        {
            Instrument instrument = Instrument.GetInstrument(fullName);
            if (instrument == null)
                throw new InvalidOperationException("Required instrument unavailable: " + fullName);
            subscriptions.Add(new QuoteState(root, instrument));
            if (!instrument.Dispatcher.HasShutdownStarted)
                instrument.Dispatcher.InvokeAsync(() => instrument.MarketData.Update += handler);
        }

        private void Unsubscribe(string root, EventHandler<MarketDataEventArgs> handler)
        {
            QuoteState state = subscriptions.Find(value => value.Root == root);
            if (state != null && !state.Instrument.Dispatcher.HasShutdownStarted)
                state.Instrument.Dispatcher.InvokeAsync(() => state.Instrument.MarketData.Update -= handler);
        }

        private void OnMesMarketData(object sender, MarketDataEventArgs update)
        {
            Process("MES", update);
        }

        private void OnMnqMarketData(object sender, MarketDataEventArgs update)
        {
            Process("MNQ", update);
        }

        private void Process(string root, MarketDataEventArgs update)
        {
            QuoteState state = subscriptions.Find(value => value.Root == root);
            if (state == null)
                return;
            lock (state.Gate)
            {
                if (update.MarketDataType == MarketDataType.Bid) state.Bid = update.Price;
                else if (update.MarketDataType == MarketDataType.Ask) state.Ask = update.Price;
                else if (update.MarketDataType == MarketDataType.Last)
                {
                    state.Last = update.Price;
                    state.LastVolume = update.Volume;
                }
                else return;
                if (state.Bid <= 0 || state.Ask <= 0 || state.Last <= 0 || state.Ask < state.Bid)
                    return;
                state.Sequence++;
                WriteSnapshot(state, DateTime.UtcNow);
            }
        }

        private void WriteSnapshot(QuoteState state, DateTime capturedAt)
        {
            string instrument = state.Instrument.FullName.Replace("\\", "\\\\").Replace("\"", "\\\"");
            string core = string.Format(CultureInfo.InvariantCulture,
                "{{\"ask\":{0:R},\"bid\":{1:R},\"captured_at_utc\":\"{2:o}\",\"instrument\":\"{3}\",\"last\":{4:R},\"last_volume\":{5},\"paper_only\":true,\"schema_version\":\"ninjatrader-read-only-quote-v1\",\"sequence\":{6},\"source\":\"NINJATRADER_SIMULATION\",\"trading_authority\":false}}",
                state.Ask, state.Bid, capturedAt, instrument, state.Last, state.LastVolume, state.Sequence);
            string digest;
            using (SHA256 sha = SHA256.Create())
                digest = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(core))).Replace("-", "").ToLowerInvariant();
            string document = core.Substring(0, core.Length - 1) + ",\"payload_sha256\":\"" + digest + "\"}\n";
            string target = Path.Combine(outputDirectory, state.Root + ".quote.json");
            string temporary = target + ".addon.tmp";
            File.WriteAllText(temporary, document, new UTF8Encoding(false));
            if (File.Exists(target)) File.Replace(temporary, target, null); else File.Move(temporary, target);
        }
    }
}
