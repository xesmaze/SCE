# SCE v2.0 — Phase 2 Add-on

Install by **copying the `sce`, `scripts`, `tests`, `examples`, and `docs` directories into your SCE fork**, merging folders rather than replacing Phase 1 files. All files are additive; `scripts/run_sce_v2.py` and the validated template remain untouched.

Read `docs/PHASE2_ENVIRONMENT.md`. It describes the required site-specific weather, soil donor and layerwise N/water inputs. The example JSONs are **illustrative only** and do not provide ready-to-run measured soil for your sites.

Quick local unit tests:

```bash
python3 -m unittest discover -s tests -p 'test_environment.py' -v
```

Use `python3 scripts/prepare_environment.py --help` to inspect the command. To stage your existing three-trial manifest, fill an environment configuration with all three IDs and ensure each site provides the three referenced files, with matching soil layers.
