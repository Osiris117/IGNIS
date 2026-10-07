# IGNIS v0.6 — Validation Notes

Validation performed before packaging:

- Python compile check: passed (`backend`, launcher and importer).
- JavaScript syntax check with Node: passed.
- HTML/JavaScript ID-reference consistency: 82 JS DOM references, 0 missing IDs.
- FastAPI health endpoint: HTTP 200, version `0.6.0`.
- FastAPI config endpoint: HTTP 200.
- Harmonized analytical demo: HTTP 200, 5 temporal frames.
- Candidate-event layer: 30 candidate events generated in the packaged synthetic demo.
- Candidate-event caveat metadata: present on every demo event.
- Burning Activity Calendar demo: HTTP 200.
- Local Archive status route: HTTP 200 even with an empty archive.
- Real Uvicorn server startup on localhost: passed.
- Root UI route: HTTP 200.
- Event clustering performance smoke test: ~20,000 synthetic observations clustered successfully using the temporal-pruned spatial index.
- Environmental-context endpoint logic tested with a deterministic local stub, including cache hit behavior. External provider calls were not executed from the build container because outbound runtime networking is restricted there.

Important: CesiumJS is still loaded from a CDN in v0.6, so the browser UI is not yet a fully disconnected/offline package. The local Python/archive engine is cross-platform and local.
