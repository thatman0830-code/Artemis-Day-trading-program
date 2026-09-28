# IBKR official client installation evidence

- Captured: 2026-09-06
- Source: official Windows TWS API installer from `interactivebrokers.github.io`
- Installed source path: `C:\TWS API\source\pythonclient`
- API version: `10.50.01` (`ibapi` package version `10.50.1`)
- Upstream commit: `8d9f7bf0a4050a13366cb3a4cd2eafc19f5e8e84`
- Required dependency: `protobuf==5.29.5`
- Project interpreter: `.venv\Scripts\python.exe`

SHA-256:

- `API_VersionNum.txt`: `31ae8d1e1e4d47417aa4cba1406bdeabd1cf7ec8522137bcd01b572e592fddf6`
- `gitCommitSha1Checksum.txt`: `28a7717df17839d3f8c53a5d948bf1a053a88b3620e0c35b7e4c9cfacfcd44d7`
- `source\pythonclient\setup.py`: `5d221921bdfcc524704e5e8ef03ee4372e2b7332b745384fd9a0c75a8dbfe882`

The official source was staged temporarily inside the repository because the
protected installer directory cannot accept build metadata. The temporary copy
was removed after installation. No third-party `ibapi` distribution was used.

The first real handshake used `127.0.0.1:7497`, client ID `71`, with TWS in
Simulated Trading and Read-Only API mode. It connected to server version `226`
and disconnected without requesting account data, market data, contracts, or
orders. This evidence grants no paper or live trading authority.
