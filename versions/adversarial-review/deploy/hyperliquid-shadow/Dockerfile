FROM python:3.14-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backtesting /app/backtesting
COPY research /app/research
RUN useradd --create-home --uid 10001 recorder && mkdir -p /data /logs && chown recorder:recorder /data /logs
USER recorder
CMD ["python", "-m", "backtesting", "record", "--symbol", "BTC", "--timeframes", "1m", "5m", "15m", "1h", "4h", "--data-network", "mainnet", "--output", "/data/hyperliquid_btc", "--log-file", "/logs/events.jsonl", "--alert-file", "/logs/alerts.jsonl"]
