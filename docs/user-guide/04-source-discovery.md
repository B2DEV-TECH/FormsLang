# 4. Source discovery

Choose source folders in the wizard. Discovery inventories supported candidates and reports safe remediation for malformed or unsupported inputs.

Forms-related candidates include `.xml`, `.fmb`, `.pll`, `.mmb` and `.olb`. Discovery is not semantic parsing. FormsLang needs a supported Forms2XML representation for project Forms analysis.

When matching FMB/XML representations exist, XML is preferred. This does **not** prove the XML is the newest binary export. FMB-only modules remain disclosed conversion work. Explicit configured Forms2XML conversion uses staged copies; proprietary Oracle binaries are not bundled or silently invoked.

Database candidates include `.sql`, `.pks`, `.pkb`, `.prc`, `.fnc`, `.trg` and `.vw`. Semantic classification comes from parsed content, not just extensions. Duplicate/conflicting objects and unsupported SQL remain visible.

Generated/build/version-control/project metadata directories are excluded. Symlink/junction escapes are rejected. Same basenames in different roots retain distinct identities. Missing database source does not prevent assessment; it limits cross-layer evidence.
