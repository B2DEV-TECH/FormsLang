# 5. Analysis

**Analyze Project** invokes one shared orchestrator: discover, parse, correlate dependencies, apply existing reasoning, build assessment and publish it.

Progress reports real phases, processed counts where known, elapsed time and diagnostics. It does not invent time remaining. A malformed file does not discard safe results from other sources; completion and warnings disclose incomplete coverage.

**Cancel** requests cancellation at safe boundaries. It does not terminate arbitrary processes or overwrite the last committed assessment. Closing the application interrupts local jobs; dead-worker recovery reports interruption on reopen.

Publication checks source fingerprints and revision preconditions. Changed source during a run is not published as a current mixed assessment. Concurrent operations may report a conflict or busy project; inspect the running operation and reload, rather than repeatedly submitting writes.

Static analysis is offline: no AI provider, database credential, APEX workspace or YAML file is required.
