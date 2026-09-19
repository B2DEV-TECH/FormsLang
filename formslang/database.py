"""Oracle database source code and DDL parser for FormsLang.

Generic ingestion of Oracle schema definitions (.sql), package specifications (.pks),
and package bodies (.pkb) into structured, queryable models with lexical evidence.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import plsql, plsql_evidence


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
class DatabaseProject:
    """Aggregated database project containing tables, views, packages, sequences."""

    tables: dict[str, Table] = field(default_factory=dict)
    views: dict[str, View] = field(default_factory=dict)
    package_specs: dict[str, PackageSpec] = field(default_factory=dict)
    package_bodies: dict[str, PackageBody] = field(default_factory=dict)
    sequences: dict[str, Sequence] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tables": {k: v.to_dict() for k, v in self.tables.items()},
            "views": {k: v.to_dict() for k, v in self.views.items()},
            "package_specs": {k: v.to_dict() for k, v in self.package_specs.items()},
            "package_bodies": {k: v.to_dict() for k, v in self.package_bodies.items()},
            "sequences": {k: v.to_dict() for k, v in self.sequences.items()},
            "files": self.files,
        }


def _strip_comments_preserving_strings(text: str) -> str:
    """Strip SQL/PLSQL comments while preserving string literals."""
    tokens = plsql_evidence.tokens(text)
    # Reconstruct text without comments
    parts = []
    last_idx = 0
    for t in tokens:
        # tokens() skips comments in its returned token stream
        parts.append(text[t.start:t.end])
    # For robust parsing, we can split into statements by semicolons and slash
    return text


def _extract_statements(text: str) -> list[tuple[str, int]]:
    """Extract top-level statements separated by ; or / with line numbers."""
    tokens = plsql_evidence.tokens(text)
    statements: list[tuple[str, int]] = []
    cur_tokens: list[plsql_evidence.Token] = []
    cur_start_line = 1
    depth = 0
    in_package_or_type = False

    i = 0
    while i < len(tokens):
        t = tokens[i]
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

        if t.value == ";" and depth == 0:
            if not in_package_or_type:
                # Top level statement finished
                start_offset = cur_tokens[0].start if cur_tokens else t.start
                stmt_text = text[start_offset:t.end].strip()
                if stmt_text:
                    statements.append((stmt_text, cur_start_line))
                cur_tokens = []
                i += 1
                continue
            else:
                # Inside package or type: check if this is the final END [name];
                # A package ends with `END [name];`
                if len(cur_tokens) >= 2 and cur_tokens[-1].kind == "word" and cur_tokens[-2].value.upper() == "END":
                    start_offset = cur_tokens[0].start
                    stmt_text = text[start_offset:t.end].strip()
                    statements.append((stmt_text, cur_start_line))
                    cur_tokens = []
                    in_package_or_type = False
                    i += 1
                    continue
                elif len(cur_tokens) >= 1 and cur_tokens[-1].value.upper() == "END":
                    start_offset = cur_tokens[0].start
                    stmt_text = text[start_offset:t.end].strip()
                    statements.append((stmt_text, cur_start_line))
                    cur_tokens = []
                    in_package_or_type = False
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


def parse_package_spec(text: str, source_file: str = "") -> PackageSpec | None:
    """Parse an Oracle package specification."""
    # Match package name
    m = re.search(r"CREATE\s+(?:OR\s+REPLACE\s+)?PACKAGE\s+(?:BODY\s+)?([A-Za-z0-9_$#.]+)\s+(?:AS|IS)", text, re.IGNORECASE)
    if not m or "BODY" in m.group(0).upper():
        return None

    raw_pkg_name = m.group(1).split(".")[-1].strip().upper()
    pkg_spec = PackageSpec(name=raw_pkg_name, source_file=source_file, raw_text=text)

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
    m = re.search(r"CREATE\s+(?:OR\s+REPLACE\s+)?PACKAGE\s+BODY\s+([A-Za-z0-9_$#.]+)\s+(?:AS|IS)", text, re.IGNORECASE)
    if not m:
        return None

    raw_pkg_name = m.group(1).split(".")[-1].strip().upper()
    pkg_body = PackageBody(name=raw_pkg_name, source_file=source_file, raw_text=text)

    tokens = plsql_evidence.tokens(text)
    i = 0
    # Advance past PACKAGE BODY <name> AS/IS
    while i < len(tokens):
        if tokens[i].value.upper() in {"AS", "IS"} and i > 2 and tokens[i - 2].value.upper() == "BODY":
            i += 1
            break
        i += 1

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

    # Check for package spec
    if p.suffix.lower() == ".pks" or "PACKAGE " in text.upper():
        pkg_spec = parse_package_spec(text, source_file=rel_path)
        if pkg_spec:
            project.package_specs[pkg_spec.name] = pkg_spec

    # Check for package body
    if p.suffix.lower() == ".pkb" or "PACKAGE BODY " in text.upper():
        pkg_body = parse_package_body(text, source_file=rel_path)
        if pkg_body:
            project.package_bodies[pkg_body.name] = pkg_body

    # Extract statements for DDL, views, sequences, comments
    stmts = _extract_statements(text)
    for stmt_sql, line_no in stmts:
        s_upper = stmt_sql.strip().upper()
        if s_upper.startswith("CREATE TABLE") or " CREATE TABLE " in s_upper:
            table = parse_create_table(stmt_sql, source_file=rel_path)
            if table:
                project.tables[table.name] = table
        elif s_upper.startswith("CREATE OR REPLACE VIEW") or s_upper.startswith("CREATE VIEW"):
            view = parse_create_view(stmt_sql, source_file=rel_path)
            if view:
                project.views[view.name] = view
        elif s_upper.startswith("CREATE SEQUENCE"):
            seq = parse_create_sequence(stmt_sql, source_file=rel_path)
            if seq:
                project.sequences[seq.name] = seq
        elif s_upper.startswith("COMMENT ON TABLE"):
            m_cm = re.search(r"COMMENT\s+ON\s+TABLE\s+([A-Za-z0-9_$#.]+)\s+IS\s+'(.*?)'", stmt_sql, re.IGNORECASE | re.DOTALL)
            if m_cm:
                tname = m_cm.group(1).split(".")[-1].upper()
                cm_text = m_cm.group(2).replace("''", "'")
                if tname in project.tables:
                    project.tables[tname].comment = cm_text
                elif tname in project.views:
                    project.views[tname].comment = cm_text


    return project


def parse_database_sources(paths: list[Path | str] | Path | str) -> DatabaseProject:
    """Parse multiple database sources and merge into a unified DatabaseProject."""
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

    merged = DatabaseProject()
    for fp in file_paths:
        proj = parse_database_file(fp)
        merged.tables.update(proj.tables)
        merged.views.update(proj.views)
        merged.package_specs.update(proj.package_specs)
        merged.package_bodies.update(proj.package_bodies)
        merged.sequences.update(proj.sequences)
        merged.files.extend(proj.files)

    return merged
