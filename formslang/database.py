"""Oracle database source code and DDL parser for FormsLang.

Generic ingestion of Oracle schema definitions (.sql), package specifications (.pks),
and package bodies (.pkb) into structured, queryable models with lexical evidence.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import plsql, plsql_evidence

# Coverage status of one supplied database source.
PARSED = "PARSED"                                  # every supported CREATE became an object
PARSED_WITH_WARNINGS = "PARSED_WITH_WARNINGS"      # objects, plus supported CREATEs that did not
NO_RECOGNIZED_OBJECTS = "NO_RECOGNIZED_OBJECTS"    # read, but no object came out of it
REJECTED_OR_UNREADABLE = "REJECTED_OR_UNREADABLE"  # never read; `reason` says why

@dataclass
class Parameter:
    """Subprogram parameter definition."""

    name: str
    data_type: str
    mode: str = "IN"
    default_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubprogramSpec:
    """Specification of a procedure or function in a package."""

    name: str
    subprogram_type: str  # PROCEDURE or FUNCTION
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str | None = None
    source_file: str = ""
    line_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "subprogram_type": self.subprogram_type,
            "parameters": [p.to_dict() for p in self.parameters],
            "return_type": self.return_type,
            "source_file": self.source_file,
            "line_number": self.line_number,
        }


@dataclass
class Constant:
    """Package constant declaration."""

    name: str
    data_type: str
    value: str = ""
    source_file: str = ""
    line_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PackageSpec:
    """Oracle package specification."""

    name: str
    constants: list[Constant] = field(default_factory=list)
    subprograms: list[SubprogramSpec] = field(default_factory=list)
    source_file: str = ""
    comment: str | None = None
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "constants": [c.to_dict() for c in self.constants],
            "subprograms": [s.to_dict() for s in self.subprograms],
            "source_file": self.source_file,
            "comment": self.comment,
        }


@dataclass
class SubprogramBody:
    """Implementation of a procedure or function in a package body."""

    name: str
    subprogram_type: str  # PROCEDURE or FUNCTION
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str | None = None
    body_text: str = ""
    plsql_evidence: dict[str, Any] = field(default_factory=dict)
    source_file: str = ""
    line_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "subprogram_type": self.subprogram_type,
            "parameters": [p.to_dict() for p in self.parameters],
            "return_type": self.return_type,
            "body_text": self.body_text[:1000] if len(self.body_text) > 1000 else self.body_text,
            "source_file": self.source_file,
            "line_number": self.line_number,
        }


@dataclass
class PackageBody:
    """Oracle package body implementation."""

    name: str
    subprograms: list[SubprogramBody] = field(default_factory=list)
    source_file: str = ""
    comment: str | None = None
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "subprograms": [s.to_dict() for s in self.subprograms],
            "source_file": self.source_file,
            "comment": self.comment,
        }


@dataclass
class PackageDeclaration:
    """One lexical CREATE PACKAGE occurrence, including its parsed contents."""

    kind: str
    owner: str | None
    name: str
    qualified_name: str
    source_file: str
    line: int
    order: int
    header_text: str
    parsed: PackageSpec | PackageBody
    projection_status: str = "PROJECTED"

    def to_dict(self) -> dict[str, Any]:
        # Source bodies are deliberately absent from this inventory projection.
        return {"kind": self.kind, "owner": self.owner, "name": self.name,
                "qualified_name": self.qualified_name, "source_file": self.source_file,
                "line": self.line, "order": self.order, "header_text": self.header_text,
                "subprograms": [s.name for s in self.parsed.subprograms],
                "projection_status": self.projection_status}


@dataclass
class Column:
    """Database table column definition."""

    name: str
    data_type: str
    nullable: bool = True
    default_value: str | None = None
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Constraint:
    """Database constraint definition (PRIMARY KEY, FOREIGN KEY, CHECK, UNIQUE)."""

    name: str
    constraint_type: str
    columns: list[str] = field(default_factory=list)
    reference_table: str | None = None
    reference_columns: list[str] = field(default_factory=list)
    check_condition: str | None = None
    raw_sql: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Table:
    """Database table definition."""

    name: str
    columns: list[Column] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    comment: str | None = None
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "columns": [c.to_dict() for c in self.columns],
            "constraints": [k.to_dict() for k in self.constraints],
            "comment": self.comment,
            "source_file": self.source_file,
        }


@dataclass
class View:
    """Database view definition."""

    name: str
    query_text: str = ""
    columns: list[str] = field(default_factory=list)
    comment: str | None = None
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Sequence:
    """Database sequence definition."""

    name: str
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceCoverage:
    """What one supplied database source yielded.

    `objects` are the extracted objects, `not_extracted` the CREATE statements of a
    supported kind that produced none, and `unsupported` the CREATE statements of a
    kind FormsLang does not model. Entries are {"kind", "name"}; statements add
    "line", "severity" and "reason". The name is None when the header could not
    be read. A not-extracted statement is a WARNING and makes the source
    PARSED_WITH_WARNINGS; an unsupported one is INFO -- a limit of the model, not
    of the read -- and leaves the status alone while staying listed.
    """

    source_file: str
    status: str
    objects: list[dict[str, Any]] = field(default_factory=list)
    not_extracted: list[dict[str, Any]] = field(default_factory=list)
    unsupported: list[dict[str, Any]] = field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatabaseProject:
    """Aggregated database project containing tables, views, packages, sequences."""

    tables: dict[str, Table] = field(default_factory=dict)
    views: dict[str, View] = field(default_factory=dict)
    package_specs: dict[str, PackageSpec] = field(default_factory=dict)
    package_bodies: dict[str, PackageBody] = field(default_factory=dict)
    package_declarations: list[PackageDeclaration] = field(default_factory=list)
    sequences: dict[str, Sequence] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    # One entry per supplied source. None means coverage was never computed,
    # which is unknown, not an estate without gaps.
    coverage: list[SourceCoverage] | None = None

    def coverage_summary(self) -> dict[str, int] | None:
        if self.coverage is None:
            return None
        counts = Counter(c.status for c in self.coverage)
        return {"supplied": len(self.coverage), "parsed": counts[PARSED],
                "parsed_with_warnings": counts[PARSED_WITH_WARNINGS],
                "no_recognized_objects": counts[NO_RECOGNIZED_OBJECTS],
                "rejected_or_unreadable": counts[REJECTED_OR_UNREADABLE]}

    def to_dict(self) -> dict[str, Any]:
        return {
            "tables": {k: v.to_dict() for k, v in self.tables.items()},
            "views": {k: v.to_dict() for k, v in self.views.items()},
            "package_specs": {k: v.to_dict() for k, v in self.package_specs.items()},
            "package_bodies": {k: v.to_dict() for k, v in self.package_bodies.items()},
            "package_declarations": [d.to_dict() for d in self.package_declarations],
            "sequences": {k: v.to_dict() for k, v in self.sequences.items()},
            "files": self.files,
            "coverage": None if self.coverage is None else [c.to_dict() for c in self.coverage],
        }


def _extract_statements(text: str) -> list[tuple[str, int]]:
    """Extract top-level statements separated by ; or / with line numbers."""
    tokens = plsql_evidence.tokens(text)
    # A SQLcl slash is a command only when it is alone on its physical line.
    # Match that offset against lexical tokens so slash inside strings/comments
    # cannot become a delimiter.
    slash_offsets = set()
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.strip() == "/":
            slash_offsets.add(offset + line.index("/"))
        offset += len(line)
    statements: list[tuple[str, int]] = []
    cur_tokens: list[plsql_evidence.Token] = []
    cur_start_line = 1
    depth = 0
    in_package_or_type = False

    i = 0
    while i < len(tokens):
        t = tokens[i]
        if in_package_or_type and cur_tokens and t.kind == "word" and t.value == "CREATE":
            # SQL exports may put the next DDL directly after END pkg; without
            # SQLcl's slash. Do not let the prior package swallow that CREATE.
            stmt_text = text[cur_tokens[0].start:cur_tokens[-1].end].strip()
            if stmt_text:
                statements.append((stmt_text, cur_start_line))
            cur_tokens = []
            depth = 0
            in_package_or_type = False
        if t.kind == "symbol" and t.value == "/" and t.start in slash_offsets:
            if cur_tokens:
                stmt_text = text[cur_tokens[0].start:cur_tokens[-1].end].strip()
                if stmt_text:
                    statements.append((stmt_text, cur_start_line))
            cur_tokens = []
            depth = 0
            in_package_or_type = False
            i += 1
            continue
        if not cur_tokens:
            cur_start_line = t.line

        # Track block depth
        if t.value == "(":
            depth += 1
        elif t.value == ")":
            depth = max(0, depth - 1)

        val_upper = t.value.upper()
        if val_upper in {"PACKAGE", "TYPE"} and i > 0 and tokens[i - 1].value.upper() in {"CREATE", "REPLACE"}:
            in_package_or_type = True

        # A package/type contains nested semicolons and END clauses. Its
        # SQLcl execution delimiter, or EOF, closes the statement.
        if t.value == ";" and depth == 0 and not in_package_or_type:
            start_offset = cur_tokens[0].start if cur_tokens else t.start
            stmt_text = text[start_offset:t.end].strip()
            if stmt_text:
                statements.append((stmt_text, cur_start_line))
            cur_tokens = []
            i += 1
            continue

        cur_tokens.append(t)
        i += 1

    if cur_tokens:
        start_offset = cur_tokens[0].start
        stmt_text = text[start_offset:cur_tokens[-1].end].strip()
        if stmt_text and stmt_text not in {"/", ";"}:
            statements.append((stmt_text, cur_start_line))

    return statements


def _parse_params(param_str: str) -> list[Parameter]:
    """Parse parameter list string, e.g. 'p_id in number, p_name in varchar2 default null'."""
    params: list[Parameter] = []
    if not param_str.strip():
        return params

    # Split by top-level commas (handling defaults with parentheses if any)
    parts = []
    cur = []
    depth = 0
    for ch in param_str:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())

    for part in parts:
        if not part:
            continue
        words = part.split()
        if not words:
            continue
        p_name = words[0]
        mode = "IN"
        idx = 1
        if idx < len(words) and words[idx].upper() in {"IN", "OUT"}:
            if idx + 1 < len(words) and words[idx].upper() == "IN" and words[idx + 1].upper() == "OUT":
                mode = "IN OUT"
                idx += 2
            else:
                mode = words[idx].upper()
                idx += 1
        if idx < len(words) and words[idx].upper() == "NOCOPY":
            idx += 1

        p_type = words[idx] if idx < len(words) else "VARCHAR2"
        idx += 1

        default_val = None
        part_rest = " ".join(words[idx:])
        default_match = re.search(r"(?:DEFAULT|:=)\s*(.*)", part_rest, re.IGNORECASE)
        if default_match:
            default_val = default_match.group(1).strip()

        params.append(Parameter(name=p_name.upper(), data_type=p_type.upper(), mode=mode, default_value=default_val))

    return params


# An Oracle identifier: quoted (any characters but a double quote) or unquoted.
_IDENTIFIER = r'(?:"[^"]+"|[A-Za-z][A-Za-z0-9_$#]*)'

# CREATE [OR REPLACE] [EDITIONABLE | NONEDITIONABLE] PACKAGE [BODY] [owner .] name
# with the supported Oracle header clauses. Keep the exact header as provenance;
# parsing one does not establish its runtime or privilege semantics.
_SHARING_CLAUSE = r"SHARING\s*=\s*(?:EXTENDED\s+DATA|METADATA|DATA|NONE)\b"
_QUOTED_HEADER_NAME = r'"(?:[^"]|"")+"'
_ACCESSIBLE_CLAUSE = rf'ACCESSIBLE\s+BY\s*\((?:{_QUOTED_HEADER_NAME}|[^();"])+\)'
_SPEC_CLAUSE = (rf"(?:AUTHID\s+(?:CURRENT_USER|DEFINER)\b|"
                rf"{_ACCESSIBLE_CLAUSE}|"
                rf"DEFAULT\s+COLLATION\s+{_IDENTIFIER}|{_SHARING_CLAUSE})")
_BODY_CLAUSE = _SHARING_CLAUSE
_PACKAGE_HEADER = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:EDITIONABLE|NONEDITIONABLE)\s+)?PACKAGE\s+(?P<body>BODY\s+)?"
    rf"(?:(?P<owner>{_IDENTIFIER})\s*\.\s*)?(?P<name>{_IDENTIFIER})"
    rf"(?:\s+(?(body){_BODY_CLAUSE}|{_SPEC_CLAUSE}))*\s*(?:AS|IS)\b",
    re.IGNORECASE,
)


def _object_name(identifier: str) -> str:
    """Oracle folds an unquoted name to upper case and keeps a quoted one exactly."""
    return identifier[1:-1] if identifier.startswith('"') else identifier.upper()


def _package_header(text: str, body: bool) -> re.Match[str] | None:
    """The first package specification (or body) header in the text."""
    tokens = plsql_evidence.tokens(text)
    lexical_text = _lexical_header_text(text, tokens)
    return next((m for t in tokens if t.kind == "word" and t.value == "CREATE"
                 if (m := _match_package_header(lexical_text, tokens, t.start))
                 and bool(m.group("body")) == body), None)


def _match_package_header(lexical_text: str, tokens: list[plsql_evidence.Token],
                          start: int) -> re.Match[str] | None:
    match = _PACKAGE_HEADER.match(lexical_text, start)
    if match is None:
        return None
    # A regex can backtrack into a word such as PAS, or punctuation inside a
    # quoted name. The delimiter must be its own lexical AS/IS token.
    if not any(t.kind == "word" and t.value in {"AS", "IS"} and t.end == match.end()
               for t in tokens):
        return None
    return match


def _lexical_header_text(text: str, tokens: list[plsql_evidence.Token]) -> str:
    """Preserve offsets while hiding comments and string literals from headers."""
    chars = ["\n" if ch == "\n" else " " for ch in text]
    for token in tokens:
        if token.kind in {"word", "quoted", "symbol"}:
            chars[token.start:token.end] = text[token.start:token.end]
    return "".join(chars)


def _package_occurrences(text: str, source_file: str) -> list[PackageDeclaration]:
    """Parse each lexical package CREATE within its own source interval."""
    tokens = plsql_evidence.tokens(text)
    lexical_text = _lexical_header_text(text, tokens)
    slash_offsets = set()
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.strip() == "/":
            slash_offsets.add(offset + line.index("/"))
        offset += len(line)
    slash_offsets.intersection_update(t.start for t in tokens if t.kind == "symbol" and t.value == "/")
    create_offsets = [t.start for i, t in enumerate(tokens) if t.kind == "word" and t.value == "CREATE"
                      and (i + 1 == len(tokens) or tokens[i + 1].value not in {"ON", "OR"}
                           or i + 2 < len(tokens) and tokens[i + 2].value == "REPLACE")]
    occurrences = []
    for order, start in enumerate(create_offsets):
        match = _match_package_header(lexical_text, tokens, start)
        if not match:
            continue
        end = create_offsets[order + 1] if order + 1 < len(create_offsets) else len(text)
        end = min((slash for slash in slash_offsets if start < slash < end), default=end)
        segment = text[start:end]
        kind = "PACKAGE BODY" if match.group("body") else "PACKAGE"
        parsed = (parse_package_body(segment, source_file) if match.group("body")
                  else parse_package_spec(segment, source_file))
        if parsed is None:
            continue
        # The member parsers see one sliced CREATE, so rebase their local lines
        # to physical lines in the source file before exposing the inventory.
        line_offset = text.count("\n", 0, start)
        for member in parsed.subprograms:
            member.line_number += line_offset
        if isinstance(parsed, PackageSpec):
            for constant in parsed.constants:
                constant.line_number += line_offset
        owner = _object_name(match.group("owner")) if match.group("owner") else None
        name = _object_name(match.group("name"))
        occurrences.append(PackageDeclaration(
            kind=kind, owner=owner, name=name,
            qualified_name=f"{owner}.{name}" if owner else name,
            source_file=source_file, line=text.count("\n", 0, start) + 1,
            order=len(occurrences) + 1, header_text=text[start:match.end()], parsed=parsed))
    return occurrences


def _project_unique_packages(project: DatabaseProject) -> None:
    """Keep legacy bare-name maps only where they cannot choose a collision."""
    groups: dict[str, list[PackageDeclaration]] = {}
    for declaration in project.package_declarations:
        groups.setdefault(declaration.name, []).append(declaration)
        declaration.projection_status = "PROJECTED"
    for matches in groups.values():
        kinds = Counter(d.kind for d in matches)
        if len({d.owner for d in matches}) > 1 or any(n > 1 for n in kinds.values()):
            for declaration in matches:
                declaration.projection_status = "AMBIGUOUS_BARE_NAME"
    for kind, family in (("PACKAGE", "package_specs"), ("PACKAGE BODY", "package_bodies")):
        setattr(project, family, {d.name: d.parsed for d in project.package_declarations
                                  if d.kind == kind and d.projection_status == "PROJECTED"})


# The statement kinds extracted into a DatabaseProject family.
_FAMILY_OF_KIND = {"TABLE": "tables", "VIEW": "views", "SEQUENCE": "sequences",
                   "PACKAGE": "package_specs", "PACKAGE BODY": "package_bodies"}
# Words that may sit between CREATE [OR REPLACE] and the object kind.
_CREATE_MODIFIERS = {"EDITIONABLE", "NONEDITIONABLE", "EDITIONING", "FORCE", "NOFORCE",
                     "GLOBAL", "PRIVATE", "TEMPORARY", "SHARDED", "DUPLICATED", "BLOCKCHAIN",
                     "IMMUTABLE", "UNIQUE", "BITMAP", "MULTIVALUE", "PUBLIC", "SHARED"}
_TWO_WORD_KINDS = {("PACKAGE", "BODY"), ("TYPE", "BODY"), ("MATERIALIZED", "VIEW"), ("DATABASE", "LINK")}


def _create_statements(text: str) -> list[dict[str, Any]]:
    """Every CREATE statement in the text, found lexically: comments and strings are skipped.

    This is independent of the extractors, so a statement they miss still shows up.
    CREATE followed by ON or OR (a DDL trigger event) is not a statement.
    """
    toks = plsql_evidence.tokens(text)

    def word(j: int) -> str | None:
        return toks[j].value.upper() if j < len(toks) and toks[j].kind == "word" else None

    found: list[dict[str, Any]] = []
    for i, tok in enumerate(toks):
        if word(i) != "CREATE":
            continue
        j = i + 1
        if word(j) == "OR" and word(j + 1) == "REPLACE":
            j += 2
        while word(j) in _CREATE_MODIFIERS or (word(j) == "NO" and word(j + 1) == "FORCE"):
            j += 2 if word(j) == "NO" else 1
        kind = word(j)
        if kind is None or kind in {"ON", "OR"}:
            continue
        j += 1
        if (kind, word(j)) in _TWO_WORD_KINDS:
            kind = f"{kind} {word(j)}"
            j += 1
        if (word(j), word(j + 1), word(j + 2)) == ("IF", "NOT", "EXISTS"):
            j += 3
        # [owner .] name; the name is the last part, with Oracle case semantics.
        name = None
        while j < len(toks) and toks[j].kind in {"word", "quoted"}:
            name = _object_name(toks[j].value)
            if j + 2 < len(toks) and toks[j + 1].value == ".":
                j += 2
            else:
                break
        found.append({"kind": kind, "name": name, "line": tok.line})
    return found


def _coverage(project: DatabaseProject, text: str, source_file: str,
              nonpackage_occurrences: list[dict[str, Any]] | None = None) -> SourceCoverage:
    """Compare the objects extracted from one source with the CREATE statements it holds."""
    objects = list(nonpackage_occurrences or [])
    objects.extend({"kind": d.kind, "name": d.name, "owner": d.owner,
                    "qualified_name": d.qualified_name, "line": d.line, "order": d.order}
                   for d in project.package_declarations)
    objects.sort(key=lambda o: (o["kind"], o["name"], o.get("order", 0)))
    statements = _create_statements(text)
    extracted_packages = Counter((d.kind, d.name, d.line) for d in project.package_declarations)
    extracted_other = Counter((o["kind"], o["name"], o["line"]) for o in objects
                              if not o["kind"].startswith("PACKAGE"))
    collision_counts = Counter((o["kind"], o["name"]) for o in objects
                               if not o["kind"].startswith("PACKAGE"))
    not_extracted = [{**o, "severity": "WARNING", "reason": "COLLIDING_BARE_NAME"}
                     for o in objects if not o["kind"].startswith("PACKAGE")
                     and collision_counts[(o["kind"], o["name"])] > 1]
    for statement in statements:
        kind = statement["kind"]
        if kind not in _FAMILY_OF_KIND:
            continue
        if kind.startswith("PACKAGE"):
            identity = (kind, statement["name"], statement["line"])
            if extracted_packages[identity]:
                extracted_packages[identity] -= 1
                continue
        else:
            identity = (kind, statement["name"], statement["line"])
            if extracted_other[identity]:
                extracted_other[identity] -= 1
                continue
        not_extracted.append({**statement, "severity": "WARNING", "reason": "NOT_EXTRACTED"})
    unsupported = [{**s, "severity": "INFO", "reason": "UNSUPPORTED_BY_MODEL"} for s in statements
                   if s["kind"] not in _FAMILY_OF_KIND]
    if not objects:
        status = NO_RECOGNIZED_OBJECTS
    elif not_extracted:
        status = PARSED_WITH_WARNINGS
    else:
        status = PARSED
    return SourceCoverage(source_file, status, objects, not_extracted, unsupported,
                          reason=None if statements or objects else "NO_CREATE_STATEMENT")


def parse_package_spec(text: str, source_file: str = "") -> PackageSpec | None:
    """Parse an Oracle package specification."""
    m = _package_header(text, body=False)
    if not m:
        return None

    pkg_spec = PackageSpec(name=_object_name(m.group("name")), source_file=source_file, raw_text=text)

    # Tokenize spec body to extract constants and subprograms
    body_start = m.end()
    spec_body = text[body_start:]

    # Extract subprogram declarations: function ... return ...; or procedure ...;
    # Regex for procedure / function declarations
    sub_pattern = re.compile(
        r"\b(FUNCTION|PROCEDURE)\s+([A-Za-z0-9_$#]+)\s*(?:\((.*?)\))?\s*(?:RETURN\s+([A-Za-z0-9_$#%]+))?\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    for sm in sub_pattern.finditer(spec_body):
        stype = sm.group(1).upper()
        sname = sm.group(2).upper()
        param_text = sm.group(3) or ""
        ret_type = sm.group(4).upper() if sm.group(4) else None
        params = _parse_params(param_text)
        line_no = text[: body_start + sm.start()].count("\n") + 1
        pkg_spec.subprograms.append(
            SubprogramSpec(
                name=sname,
                subprogram_type=stype,
                parameters=params,
                return_type=ret_type,
                source_file=source_file,
                line_number=line_no,
            )
        )

    # Extract constants: <name> constant <type> := <val>;
    const_pattern = re.compile(
        r"\b([A-Za-z0-9_$#]+)\s+CONSTANT\s+([A-Za-z0-9_$#%]+(?:\s*\([^)]*\))?)\s*(?::=|DEFAULT)\s*([^;]+);",
        re.IGNORECASE,
    )
    for cm in const_pattern.finditer(spec_body):
        cname = cm.group(1).upper()
        ctype = cm.group(2).upper()
        cval = cm.group(3).strip()
        line_no = text[: body_start + cm.start()].count("\n") + 1
        pkg_spec.constants.append(
            Constant(
                name=cname,
                data_type=ctype,
                value=cval,
                source_file=source_file,
                line_number=line_no,
            )
        )

    return pkg_spec


def parse_package_body(text: str, source_file: str = "") -> PackageBody | None:
    """Parse an Oracle package body implementation."""
    m = _package_header(text, body=True)
    if not m:
        return None

    pkg_body = PackageBody(name=_object_name(m.group("name")), source_file=source_file, raw_text=text)

    tokens = plsql_evidence.tokens(text)
    # Start after the AS/IS the header matched. Counting tokens back from AS/IS
    # to BODY breaks on a schema-qualified name, which adds "OWNER" and ".".
    i = next((k for k, t in enumerate(tokens) if t.start >= m.end()), len(tokens))

    # Now scan subprograms: FUNCTION or PROCEDURE
    while i < len(tokens):
        t = tokens[i]
        val = t.value.upper()
        if val in {"FUNCTION", "PROCEDURE"} and (i == 0 or tokens[i - 1].value.upper() not in {"END", "TYPE"}):
            stype = val
            sub_start_token = t
            sub_line = t.line
            i += 1
            if i >= len(tokens) or tokens[i].kind != "word":
                continue
            sname = tokens[i].value.upper()
            i += 1

            # Parse parameters if present
            param_str = ""
            if i < len(tokens) and tokens[i].value == "(":
                p_start = tokens[i].start + 1
                depth = 1
                i += 1
                while i < len(tokens) and depth > 0:
                    if tokens[i].value == "(":
                        depth += 1
                    elif tokens[i].value == ")":
                        depth -= 1
                    i += 1
                param_str = text[p_start : tokens[i - 1].end - 1]

            # Return type for function
            return_type = None
            if stype == "FUNCTION":
                while i < len(tokens) and tokens[i].value.upper() not in {"IS", "AS"}:
                    if tokens[i].value.upper() == "RETURN" and i + 1 < len(tokens):
                        return_type = tokens[i + 1].value.upper()
                    i += 1

            # Advance past IS / AS
            while i < len(tokens) and tokens[i].value.upper() not in {"IS", "AS"}:
                i += 1
            if i < len(tokens):
                i += 1  # pass IS/AS

            # Scan until matching END <sname>; or END;
            body_start_offset = sub_start_token.start
            depth = 0
            while i < len(tokens):
                tv = tokens[i].value.upper()
                prev_tv = tokens[i - 1].value.upper() if i > 0 else ""
                if tv in {"BEGIN", "CASE", "IF", "LOOP"} and prev_tv != "END":
                    depth += 1
                elif tv == "END":
                    depth -= 1
                    # If this is END IF, END LOOP, END CASE, consume the qualifier token
                    if i + 1 < len(tokens) and tokens[i + 1].value.upper() in {"IF", "LOOP", "CASE"}:
                        i += 1
                    if depth <= 0:
                        # Check if followed by sname or ;
                        end_token = tokens[i]
                        i += 1
                        if i < len(tokens) and tokens[i].value.upper() == sname:
                            end_token = tokens[i]
                            i += 1
                        if i < len(tokens) and tokens[i].value == ";":
                            end_token = tokens[i]
                            i += 1
                        sub_body_text = text[body_start_offset : end_token.end]
                        params = _parse_params(param_str)
                        evidence = plsql.evidence(sub_body_text)
                        pkg_body.subprograms.append(
                            SubprogramBody(
                                name=sname,
                                subprogram_type=stype,
                                parameters=params,
                                return_type=return_type,
                                body_text=sub_body_text,
                                plsql_evidence=evidence,
                                source_file=source_file,
                                line_number=sub_line,
                            )
                        )
                        break
                i += 1
            continue
        i += 1

    return pkg_body


def _parse_column_definition(col_sql: str) -> Column | None:
    """Parse a single column line inside CREATE TABLE."""
    parts = col_sql.strip().split()
    if not parts:
        return None
    name = parts[0].upper()
    if name in {"CONSTRAINT", "PRIMARY", "FOREIGN", "CHECK", "UNIQUE"}:
        return None  # Table level constraint

    data_type = parts[1].upper() if len(parts) > 1 else "VARCHAR2"
    nullable = "NOT NULL" not in col_sql.upper()

    default_val = None
    default_match = re.search(r"\bDEFAULT\s+([^,\s]+(?:\s+[^,\s]+)?)", col_sql, re.IGNORECASE)
    if default_match:
        default_val = default_match.group(1).strip()

    return Column(name=name, data_type=data_type, nullable=nullable, default_value=default_val)


def _parse_table_constraint(clause: str) -> Constraint | None:
    """Parse table-level constraint definition."""
    clause = clause.strip()
    name = ""
    m_name = re.match(r"CONSTRAINT\s+([A-Za-z0-9_$#]+)\s+(.*)", clause, re.IGNORECASE | re.DOTALL)
    if m_name:
        name = m_name.group(1).upper()
        body = m_name.group(2).strip()
    else:
        body = clause

    b_upper = body.upper()
    if b_upper.startswith("PRIMARY KEY"):
        m_cols = re.search(r"PRIMARY\s+KEY\s*\((.*?)\)", body, re.IGNORECASE)
        cols = [c.strip().upper() for c in m_cols.group(1).split(",")] if m_cols else []
        return Constraint(name=name, constraint_type="PRIMARY KEY", columns=cols, raw_sql=clause)
    elif b_upper.startswith("FOREIGN KEY"):
        m_fk = re.search(r"FOREIGN\s+KEY\s*\((.*?)\)\s*REFERENCES\s+([A-Za-z0-9_$#.]+)\s*(?:\((.*?)\))?", body, re.IGNORECASE)
        if m_fk:
            cols = [c.strip().upper() for c in m_fk.group(1).split(",")]
            ref_tbl = m_fk.group(2).split(".")[-1].upper()
            ref_cols = [c.strip().upper() for c in m_fk.group(3).split(",")] if m_fk.group(3) else []
            return Constraint(name=name, constraint_type="FOREIGN KEY", columns=cols, reference_table=ref_tbl, reference_columns=ref_cols, raw_sql=clause)
    elif b_upper.startswith("CHECK"):
        m_ck = re.search(r"CHECK\s*\((.*)\)", body, re.IGNORECASE | re.DOTALL)
        cond = m_ck.group(1).strip() if m_ck else body
        return Constraint(name=name, constraint_type="CHECK", check_condition=cond, raw_sql=clause)
    elif b_upper.startswith("UNIQUE"):
        m_uq = re.search(r"UNIQUE\s*\((.*?)\)", body, re.IGNORECASE)
        cols = [c.strip().upper() for c in m_uq.group(1).split(",")] if m_uq else []
        return Constraint(name=name, constraint_type="UNIQUE", columns=cols, raw_sql=clause)

    return None


def parse_create_table(sql: str, source_file: str = "") -> Table | None:
    """Parse CREATE TABLE statement into Table model."""
    m = re.search(r"CREATE\s+TABLE\s+([A-Za-z0-9_$#.]+)\s*\((.*)\)", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    table_name = m.group(1).split(".")[-1].strip().upper()
    body = m.group(2).strip()

    # Split body clauses by top-level commas
    clauses: list[str] = []
    cur: list[str] = []
    depth = 0
    for ch in body:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            clauses.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        clauses.append("".join(cur).strip())

    columns: list[Column] = []
    constraints: list[Constraint] = []

    for clause in clauses:
        clause_stripped = clause.strip()
        if not clause_stripped:
            continue
        first_word = clause_stripped.split()[0].upper()
        if first_word in {"CONSTRAINT", "PRIMARY", "FOREIGN", "CHECK", "UNIQUE"}:
            c = _parse_table_constraint(clause_stripped)
            if c:
                constraints.append(c)
        else:
            col = _parse_column_definition(clause_stripped)
            if col:
                columns.append(col)

    return Table(name=table_name, columns=columns, constraints=constraints, source_file=source_file)


def parse_create_view(sql: str, source_file: str = "") -> View | None:
    """Parse CREATE VIEW statement into View model."""
    m = re.search(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([A-Za-z0-9_$#.]+)\s+(?:\((.*?)\)\s+)?AS\s+(.*)", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    view_name = m.group(1).split(".")[-1].strip().upper()
    query_text = m.group(3).strip().rstrip(";")
    return View(name=view_name, query_text=query_text, source_file=source_file)


def parse_create_sequence(sql: str, source_file: str = "") -> Sequence | None:
    """Parse CREATE SEQUENCE statement."""
    m = re.search(r"CREATE\s+SEQUENCE\s+([A-Za-z0-9_$#.]+)", sql, re.IGNORECASE)
    if not m:
        return None
    seq_name = m.group(1).split(".")[-1].strip().upper()
    return Sequence(name=seq_name, source_file=source_file)


def parse_database_file(path: Path | str) -> DatabaseProject:
    """Parse a single SQL, PKS, or PKB database source file into a DatabaseProject."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    rel_path = str(p)

    project = DatabaseProject(files=[rel_path])

    project.package_declarations = _package_occurrences(text, rel_path)
    _project_unique_packages(project)

    # Extract statements for DDL, views, sequences, comments
    stmts = _extract_statements(text)
    nonpackage_occurrences: list[dict[str, Any]] = []
    for stmt_sql, line_no in stmts:
        s_upper = stmt_sql.strip().upper()
        if s_upper.startswith("CREATE TABLE") or " CREATE TABLE " in s_upper:
            table = parse_create_table(stmt_sql, source_file=rel_path)
            if table:
                project.tables[table.name] = table
                nonpackage_occurrences.append({"kind": "TABLE", "name": table.name, "line": line_no})
        elif s_upper.startswith(("CREATE OR REPLACE VIEW", "CREATE VIEW")):
            view = parse_create_view(stmt_sql, source_file=rel_path)
            if view:
                project.views[view.name] = view
                nonpackage_occurrences.append({"kind": "VIEW", "name": view.name, "line": line_no})
        elif s_upper.startswith("CREATE SEQUENCE"):
            seq = parse_create_sequence(stmt_sql, source_file=rel_path)
            if seq:
                project.sequences[seq.name] = seq
                nonpackage_occurrences.append({"kind": "SEQUENCE", "name": seq.name, "line": line_no})
        elif s_upper.startswith("COMMENT ON TABLE"):
            m_cm = re.search(r"COMMENT\s+ON\s+TABLE\s+([A-Za-z0-9_$#.]+)\s+IS\s+'(.*?)'", stmt_sql, re.IGNORECASE | re.DOTALL)
            if m_cm:
                tname = m_cm.group(1).split(".")[-1].upper()
                cm_text = m_cm.group(2).replace("''", "'")
                if tname in project.tables:
                    project.tables[tname].comment = cm_text
                elif tname in project.views:
                    project.views[tname].comment = cm_text

    counts = Counter((o["kind"], o["name"]) for o in nonpackage_occurrences)
    for kind, family in (("TABLE", "tables"), ("VIEW", "views"), ("SEQUENCE", "sequences")):
        for name in list(getattr(project, family)):
            if counts[(kind, name)] > 1:
                del getattr(project, family)[name]
    project.coverage = [_coverage(project, text, rel_path, nonpackage_occurrences)]
    return project


def parse_database_sources(paths: list[Path | str] | Path | str) -> DatabaseProject:
    """Parse multiple database sources and merge into a unified DatabaseProject."""
    missing: list[SourceCoverage] = []
    if isinstance(paths, (str, Path)):
        p = Path(paths)
        if p.is_dir():
            file_paths = sorted([
                f for f in p.rglob("*")
                if f.is_file() and f.suffix.lower() in {".sql", ".pks", ".pkb"}
            ])
        else:
            file_paths = [p]
    else:
        file_paths = []
        for item in paths:
            ip = Path(item)
            if ip.is_dir():
                file_paths.extend(sorted([
                    f for f in ip.rglob("*")
                    if f.is_file() and f.suffix.lower() in {".sql", ".pks", ".pkb"}
                ]))
            elif ip.is_file():
                file_paths.append(ip)
            else:
                # Supplied but absent: reported, never silently skipped.
                missing.append(SourceCoverage(str(ip), REJECTED_OR_UNREADABLE, reason="SOURCE_NOT_FOUND"))

    merged = DatabaseProject(coverage=[])
    for fp in file_paths:
        proj = parse_database_file(fp)
        merged.tables.update(proj.tables)
        merged.views.update(proj.views)
        merged.package_declarations.extend(proj.package_declarations)
        merged.sequences.update(proj.sequences)
        merged.files.extend(proj.files)
        merged.coverage.extend(proj.coverage)
    merged.coverage.extend(missing)
    _project_unique_packages(merged)
    return merged
