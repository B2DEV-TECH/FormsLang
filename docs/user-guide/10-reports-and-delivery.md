# 10. Reports and modernization delivery

Open **Reports** to export Executive Assessment, Technical Assessment, Risk Report, Backlog CSV/JSON, Decision History JSON or a Modernization Package.

Reports use a revision-bound persisted snapshot, not fresh analysis. Stale/incomplete status, source and review revisions, target, limitations and generation exclusions accompany the result.

Default exports exclude source bodies and private human notes but retain technical identifiers: **they are not anonymous**. Review before sharing. Explicit note inclusion affects decision/backlog evidence, never executive HTML. Explicit generated-artifact inclusion may contain business logic.

The package manifest lists exact member hashes, revisions, validation evidence and exclusions. Unsupported or edited artifacts are excluded transparently, not regenerated. CSV neutralizes spreadsheet formulas; JSON preserves supported raw values subject to documented privacy redaction.

HTML is printable and viewable without FormsLang. There is no PDF requirement, issue-tracker upload or automatic publication. Files are downloaded as attachments, not rendered inside the privileged Workbench. See [package contract](../project-reports.md).
