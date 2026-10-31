# Phase 3 design contract

- Inputs: Phase 2 environment manifest and a per-trial JSON management config.
- No assumed regional sowing, MG assignment or auto season calendar.
- Each parameter and unit must be explicit; clocks must fit available weather coverage.
- Reject missing or ambiguous C# replacement targets; never use global regex or silent replacements.
- Only alter the Clock and explicitly selected Manager CodeArray string contents.
- Keep the original SCE v2 cultivar physiological coefficients and APSIM functions as-is.
- Write all generated files to separate output locations, with source-model hashes.
- Require a separate native APSIM 2026 run before asserting correct sowing semantics.
