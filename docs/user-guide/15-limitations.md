# 15. Limitations and human responsibilities

FormsLang does not guarantee functional equivalence, infer undocumented business intent, replace architects/UAT, convert every Forms construct, deploy automatically to production or turn unknown evidence into safe automation.

- FMB is not directly parsed for project semantics; supported Forms2XML is required.
- Binary library/menu/object-library semantics may remain unavailable.
- Missing database sources, dynamic SQL and unresolved dependencies limit evidence.
- Business rules are candidates until human-confirmed.
- Generation is conservative, selected-module and mapping-limited. It does not merge a whole estate or invent security/workflow behavior.
- Generation/report operations are synchronous; no continuation after process exit is promised.
- Managed artifacts are immutable/hash-checked; edited copies need independent governance.
- Delivery is in memory with a 128 MiB uncompressed-member limit.
- Offline SQLcl validation is not runtime/UAT, Oracle certification or endorsement.
- Automated accessibility checks are not a full manual screen-reader audit.
- Synthetic performance and structured persona review are not customer productivity studies.

Local metadata and exported technical identifiers remain sensitive. Follow organizational access, retention and review policies.
