"""CML tokenizer, tolerant parser, and semantic diff."""

import hashlib
import json


_CML_LOGIC_CALLS = {
    "constraint", "require", "exclude", "preference", "recommend", "rule",
    "setdefault", "message",
}
_CML_TOP_LEVEL = {"property", "extern", "define", "type"}


class _CmlToken:
    """Small source-aware token used by the tolerant CML parser."""

    __slots__ = ("kind", "value", "start", "end", "line", "column",
                 "end_line", "end_column")

    def __init__(self, kind, value, start, end, line, column,
                 end_line, end_column):
        self.kind = kind
        self.value = value
        self.start = start
        self.end = end
        self.line = line
        self.column = column
        self.end_line = end_line
        self.end_column = end_column


def _cml_range(start_token, end_token=None):
    """Return a JSON-safe half-open source range for one or more tokens."""
    end_token = end_token or start_token
    return {
        "start": {
            "offset": start_token.start,
            "line": start_token.line,
            "column": start_token.column,
        },
        "end": {
            "offset": end_token.end,
            "line": end_token.end_line,
            "column": end_token.end_column,
        },
    }


def _cml_diag(code, message, token, severity="warning", end_token=None,
              confidence="high"):
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "line": token.line,
        "column": token.column,
        "confidence": confidence,
        "sourceRange": _cml_range(token, end_token),
    }


def _tokenize_cml(content):
    """Tokenize CML while preserving exact offsets and source coordinates."""
    tokens = []
    diagnostics = []
    i, line, column = 0, 1, 1
    size = len(content)
    multi_ops = (
        "<->", "===", "!==", "->", "=>", "==", "!=", "<=", ">=", "&&",
        "||", "..", "::", "+=", "-=", "*=", "/=",
    )

    def advance_one():
        nonlocal i, line, column
        char = content[i]
        i += 1
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1

    def emit(kind, value, start, start_line, start_column):
        tokens.append(_CmlToken(
            kind, value, start, i, start_line, start_column, line, column))

    while i < size:
        char = content[i]
        if char.isspace():
            advance_one()
            continue
        start, start_line, start_column = i, line, column

        if content.startswith("//", i):
            while i < size and content[i] != "\n":
                advance_one()
            continue
        if content.startswith("/*", i):
            advance_one()
            advance_one()
            closed = False
            while i < size:
                if content.startswith("*/", i):
                    advance_one()
                    advance_one()
                    closed = True
                    break
                advance_one()
            if not closed:
                token = _CmlToken(
                    "COMMENT", content[start:i], start, i, start_line,
                    start_column, line, column)
                diagnostics.append(_cml_diag(
                    "unterminated-comment", "Unterminated block comment.",
                    token, "error"))
            continue
        if char in ('"', "'"):
            quote = char
            advance_one()
            escaped = False
            closed = False
            while i < size:
                current = content[i]
                if escaped:
                    escaped = False
                    advance_one()
                elif current == "\\":
                    escaped = True
                    advance_one()
                elif current == quote:
                    advance_one()
                    closed = True
                    break
                else:
                    advance_one()
            emit("STRING", content[start:i], start, start_line, start_column)
            if not closed:
                diagnostics.append(_cml_diag(
                    "unterminated-string", "Unterminated quoted string.",
                    tokens[-1], "error"))
            continue
        if char.isalpha() or char in "_$":
            advance_one()
            while i < size and (
                    content[i].isalnum() or content[i] in "_$"):
                advance_one()
            emit("IDENT", content[start:i], start, start_line, start_column)
            continue
        if char.isdigit() or (
                char == "." and i + 1 < size and content[i + 1].isdigit()):
            if char == ".":
                advance_one()
            while i < size and (
                    content[i].isdigit() or content[i] == "_"):
                advance_one()
            # Do not absorb the first dot of CML's cardinality operator (`..`).
            if (i < size and content[i] == "."
                    and not content.startswith("..", i)):
                advance_one()
                while i < size and (
                        content[i].isdigit() or content[i] == "_"):
                    advance_one()
            if i < size and content[i] in "eE":
                advance_one()
                if i < size and content[i] in "+-":
                    advance_one()
                while i < size and content[i].isdigit():
                    advance_one()
            emit("NUMBER", content[start:i], start, start_line, start_column)
            continue
        operator = next(
            (candidate for candidate in multi_ops
             if content.startswith(candidate, i)), None)
        if operator:
            for _ in operator:
                advance_one()
            emit("OP", operator, start, start_line, start_column)
            continue
        if char in "{}()[];,:.@":
            advance_one()
            emit("SYMBOL", char, start, start_line, start_column)
            continue
        if char in "+-*/%!<>=?&|^":
            advance_one()
            emit("OP", char, start, start_line, start_column)
            continue

        advance_one()
        emit("UNKNOWN", char, start, start_line, start_column)
        diagnostics.append(_cml_diag(
            "unknown-character", f"Unsupported character {char!r}.",
            tokens[-1], "warning"))

    tokens.append(_CmlToken(
        "EOF", "", size, size, line, column, line, column))
    return tokens, diagnostics


class _CmlParser:
    """Tolerant recursive-descent parser for declarations and logic calls."""

    _PRECEDENCE = {
        # Revenue Cloud Developer Guide PDF pp. 1032-1034: implication is
        # lowest; conditional, biconditional, OR, XOR, AND then bind tighter.
        "=": 0, "..": 0, "->": 1, "<->": 3, "||": 4, "or": 4,
        "^": 5, "&&": 6, "and": 6,
        "==": 7, "===": 7, "!=": 7, "!==": 7, "in": 7,
        "<": 8, "<=": 8, ">": 8, ">=": 8,
        "+": 9, "-": 9, "*": 10, "/": 10, "%": 10,
    }
    _RIGHT_ASSOCIATIVE = {"=", "->"}

    def __init__(self, content, tokens, diagnostics):
        self.content = content
        self.tokens = tokens
        self.diagnostics = diagnostics
        self.pos = 0
        self.declarations = []
        self.types = []
        self.logic = []
        self.unknown = []

    @property
    def current(self):
        return self.tokens[self.pos]

    @property
    def previous(self):
        return self.tokens[max(0, self.pos - 1)]

    def _at(self, value=None, kind=None):
        token = self.current
        return ((value is None or token.value == value)
                and (kind is None or token.kind == kind))

    def _at_ci(self, *values):
        return (self.current.kind == "IDENT"
                and self.current.value.lower()
                in {value.lower() for value in values})

    def _take(self):
        token = self.current
        if token.kind != "EOF":
            self.pos += 1
        return token

    def _match(self, *values):
        if self.current.value in values:
            return self._take()
        return None

    def _error(self, code, message, token=None, severity="warning"):
        self.diagnostics.append(_cml_diag(
            code, message, token or self.current, severity))

    def _raw(self, start, end=None):
        end = end or self.previous
        return self.content[start.start:end.end]

    def _node(self, kind, start, end=None, **values):
        end = end or self.previous
        node = {
            "kind": kind,
            "raw": self.content[start.start:end.end],
            "sourceRange": _cml_range(start, end),
        }
        node.update(values)
        return node

    def parse(self):
        while not self._at(kind="EOF"):
            start_pos = self.pos
            annotations = self._parse_annotations()
            if self._at(kind="EOF"):
                if annotations:
                    self._error(
                        "orphan-annotation",
                        "Annotation is not attached to a declaration.",
                        self.previous)
                break
            keyword = self.current.value
            if keyword == "type":
                self._parse_type(annotations)
            elif keyword in ("property", "extern", "define"):
                self._parse_declaration(keyword, annotations)
            else:
                self._parse_unknown("top-level")
            if self.pos == start_pos:
                self._take()
        return self.declarations, self.types, self.logic, self.unknown

    def _parse_annotations(self):
        annotations = []
        while self._at("@"):
            start = self._take()
            if not self._match("("):
                self._error(
                    "malformed-annotation",
                    "Expected '(' after annotation marker.", start)
                annotations.append(self._node(
                    "annotation", start, start, arguments=[]))
                continue
            args = self._parse_expression_list(")")
            if not self._match(")"):
                self._error(
                    "malformed-annotation", "Unclosed annotation.", start)
            annotations.append(self._node(
                "annotation", start, self.previous, arguments=args))
        return annotations

    def _parse_type_spec(self):
        if not self._at(kind="IDENT"):
            return None
        start = self._take()
        name = start.value
        if name in ("decimal", "double") and self._match("("):
            scale = self._take() if self._at(kind="NUMBER") else None
            if not self._match(")"):
                self._error(
                    "malformed-type",
                    f"Expected ')' in {name} type.", start)
            if scale:
                name = f"{name}({scale.value})"
        if self._match("["):
            if not self._match("]"):
                self._error(
                    "malformed-type", "Expected ']' in array type.", start)
            name += "[]"
        return name, start, self.previous

    def _parse_declaration(self, kind, annotations):
        start = self._take()
        data_type = None
        name_token = None
        value = None
        if kind == "extern":
            parsed_type = self._parse_type_spec()
            if parsed_type:
                data_type = parsed_type[0]
            else:
                self._error(
                    "malformed-declaration",
                    "Expected a type after 'extern'.", start)
            if self._at(kind="IDENT"):
                name_token = self._take()
        else:
            if self._at(kind="IDENT"):
                name_token = self._take()

        if not name_token:
            self._error(
                "malformed-declaration",
                f"Expected a name in {kind} declaration.", start, "error")

        if self._match("="):
            value = self._parse_expression()
        elif kind == "define" and not self._at(";"):
            # Official syntax is `define NAME value` (PDF pp. 1009, 1059).
            # Accept `=` too for compatibility with existing local corpora.
            value = self._parse_expression()
        self._consume_terminator(start, top_level=True)
        end = self.previous
        declaration = {
            "kind": kind,
            "name": name_token.value if name_token else None,
            "dataType": data_type,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "value": value,
        }
        self.declarations.append(declaration)

    def _parse_type(self, annotations):
        start = self._take()
        name_token = self._take() if self._at(kind="IDENT") else None
        if not name_token:
            self._error(
                "malformed-type", "Expected a name after 'type'.",
                start, "error")
        parent = None
        parent_token = None
        if self._match(":"):
            if self._at(kind="IDENT"):
                parent_token = self._take()
                parent = parent_token.value
            else:
                self._error(
                    "malformed-inheritance",
                    "Expected a parent type after ':'.", self.current)

        members, closed, stub = [], True, False
        if self._match(";"):
            stub = True
        elif self._match("{"):
            closed = False
            while not self._at(kind="EOF") and not self._at("}"):
                # A declaration aligned with the type header is a useful
                # recovery point when a malformed type body lost its '}'.
                if (self.current.value in _CML_TOP_LEVEL
                        and self.current.column <= start.column):
                    break
                before = self.pos
                member_annotations = self._parse_annotations()
                if self._at("}"):
                    if member_annotations:
                        self._error(
                            "orphan-annotation",
                            "Annotation is not attached to a type member.",
                            self.previous)
                    break
                member = self._parse_member(
                    name_token.value if name_token else "<unknown>",
                    member_annotations)
                if member:
                    members.append(member)
                if self.pos == before:
                    self._take()
            if self._match("}"):
                closed = True
                self._match(";")
            else:
                self._error(
                    "unclosed-type",
                    f"Type '{name_token.value if name_token else '?'}' "
                    "is missing a closing '}'.", start, "error")
        else:
            self._error(
                "malformed-type",
                "Expected ';' or '{' after type declaration.", self.current,
                "error")
            self._consume_terminator(start, top_level=True)

        end = self.previous
        type_record = {
            "kind": "type",
            "name": name_token.value if name_token else None,
            "parent": parent,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "stub": stub,
            "closed": closed,
            "variables": [m for m in members if m["kind"] == "variable"],
            "relations": [m for m in members if m["kind"] == "relation"],
            "unknownMembers": [
                m for m in members if m["kind"] == "unknown"],
        }
        self.types.append(type_record)
        self.declarations.append({
            key: type_record[key] for key in (
                "kind", "name", "parent", "line", "raw", "sourceRange",
                "annotations", "stub")
        })

    def _parse_member(self, scope, annotations):
        if self.current.value == "relation":
            return self._parse_relation(scope, annotations)
        if (self.current.kind == "IDENT"
                and self.current.value.lower() in _CML_LOGIC_CALLS):
            return self._parse_logic(scope, annotations)
        if self._looks_like_variable():
            return self._parse_variable(scope, annotations)
        return self._parse_unknown(scope, annotations)

    def _looks_like_variable(self):
        if not self._at(kind="IDENT"):
            return False
        index = self.pos + 1
        if self.current.value in ("decimal", "double") and index < len(self.tokens):
            if self.tokens[index].value == "(":
                depth = 1
                index += 1
                while index < len(self.tokens) and depth:
                    depth += self.tokens[index].value == "("
                    depth -= self.tokens[index].value == ")"
                    index += 1
        if index + 1 < len(self.tokens) and self.tokens[index].value == "[":
            if self.tokens[index + 1].value == "]":
                index += 2
        return (index < len(self.tokens)
                and self.tokens[index].kind == "IDENT")

    def _parse_variable(self, scope, annotations):
        start = self.current
        parsed_type = self._parse_type_spec()
        name_token = self._take() if self._at(kind="IDENT") else None
        value = None
        if self._match("="):
            value = self._parse_expression()
        self._consume_terminator(start)
        end = self.previous
        if not name_token:
            self._error(
                "malformed-variable", "Expected a variable name.", start)
        return {
            "kind": "variable",
            "name": name_token.value if name_token else None,
            "dataType": parsed_type[0] if parsed_type else None,
            "scope": scope,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "domain": value,
        }

    def _parse_relation(self, scope, annotations):
        start = self._take()
        name_token = self._take() if self._at(kind="IDENT") else None
        if not self._match(":"):
            self._error(
                "malformed-relation", "Expected ':' in relation.", start)
        target_token = self._take() if self._at(kind="IDENT") else None
        cardinality = None
        if self._match("["):
            card_start = self.previous
            lower = None if self._at("..") else self._parse_expression(1)
            fixed = not self._at("..")
            if fixed:
                upper = lower
            else:
                self._take()
                upper = None if self._at("]") else self._parse_expression(1)
            if not self._match("]"):
                self._error(
                    "malformed-cardinality",
                    "Expected ']' after relation cardinality.", card_start)
            cardinality = {
                "raw": self._raw(card_start, self.previous),
                "min": lower,
                "max": upper,
                "fixed": fixed,
                "sourceRange": _cml_range(card_start, self.previous),
            }
        order = None
        if self._at_ci("order"):
            order_start = self._take()
            ordered_types = []
            if self._match("("):
                ordered_types = self._parse_expression_list(")")
                if not self._match(")"):
                    self._error(
                        "malformed-relation-order",
                        "Expected ')' after relation order list.",
                        order_start, "error")
            else:
                self._error(
                    "malformed-relation-order",
                    "Expected '(' after relation order.", order_start,
                    "error")
            order = {
                "raw": self._raw(order_start, self.previous),
                "types": ordered_types,
                "sourceRange": _cml_range(order_start, self.previous),
            }
        body = None
        if self._match("{"):
            body_start = self.previous
            declarations = []
            aggregate_calls = []
            unknown_constructs = []
            while not self._at(kind="EOF") and not self._at("}"):
                declaration_start = self.current
                if (self._at(kind="IDENT")
                        and self.pos + 1 < len(self.tokens)
                        and self.tokens[self.pos + 1].value == "="):
                    derived_name_token = self._take()
                    self._take()
                    expression = self._parse_expression()
                    self._consume_terminator(declaration_start)
                    declaration = self._node(
                        "relationDerivedDeclaration", declaration_start,
                        self.previous, name=derived_name_token.value,
                        expression=expression)
                    declarations.append(declaration)
                    aggregate_calls.extend(
                        self._collect_aggregate_calls(expression))
                else:
                    unknown = self._parse_unknown(
                        f"relation {name_token.value if name_token else '?'}")
                    unknown_constructs.append(unknown)
            if not self._match("}"):
                self._error(
                    "malformed-relation",
                    "Relation body is missing a closing '}'.",
                    body_start, "error")
            body = {
                "raw": self._raw(body_start, self.previous),
                "sourceRange": _cml_range(body_start, self.previous),
                "declarations": declarations,
                "aggregateCalls": aggregate_calls,
                "unknownConstructs": unknown_constructs,
                "complete": self.previous.value == "}",
            }
            self._match(";")
        else:
            self._consume_terminator(start)
        end = self.previous
        if not name_token or not target_token:
            self._error(
                "malformed-relation",
                "Relation requires a name and target type.", start, "error")
        return {
            "kind": "relation",
            "name": name_token.value if name_token else None,
            "target": target_token.value if target_token else None,
            "scope": scope,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "cardinality": cardinality,
            "order": order,
            "body": body,
        }

    def _collect_aggregate_calls(self, node):
        calls = []

        def visit(current):
            if not isinstance(current, dict):
                return
            if current.get("kind") == "call":
                callee = current.get("callee") or {}
                aggregate = None
                if callee.get("kind") == "name":
                    aggregate = callee.get("name", "").lower()
                elif callee.get("kind") == "member":
                    aggregate = callee.get("member", "").lower()
                if aggregate in {"count", "max", "min", "sum", "total"}:
                    calls.append({
                        "function": aggregate,
                        "raw": current.get("raw", ""),
                        "arguments": current.get("arguments", []),
                        "sourceRange": current.get("sourceRange"),
                        "quantityBehavior": (
                            "multiplies-by-product-quantity"
                            if aggregate == "sum" else
                            "ignores-product-quantity"
                            if aggregate == "total" else None),
                    })
            for value in current.values():
                if isinstance(value, dict):
                    visit(value)
                elif isinstance(value, list):
                    for child in value:
                        visit(child)

        visit(node)
        return calls

    def _parse_logic(self, scope, annotations):
        start = self._take()
        diagnostic_start = len(self.diagnostics)
        logic_kind = start.value.lower()
        name_token = None
        malformed = False
        args = []
        # Named forms are documented as `constraint name(expression)` (PDF
        # pp. 1038 and 1121); accepting the form for every rule keeps recovery
        # consistent without changing ordinary call syntax.
        if self._at(kind="IDENT"):
            name_token = self._take()
        if self._match("("):
            args = self._parse_expression_list(")")
            if not self._match(")"):
                malformed = True
                self._error(
                    "malformed-logic",
                    f"Unclosed argument list for {logic_kind}.", start,
                    "error")
        else:
            malformed = True
            self._error(
                "malformed-logic",
                f"Expected '(' after {logic_kind}.", start, "error")

        block_expression = None
        if self._match("{"):
            block_start = self.previous
            if not self._at("}"):
                block_expression = self._parse_expression()
            if not self._match("}"):
                malformed = True
                self._error(
                    "malformed-logic",
                    f"Unclosed body for {logic_kind}.", block_start, "error")
            self._match(";")
        else:
            self._consume_terminator(start)
        end = self.previous
        condition = block_expression or (args[0] if args else None)
        logic_diagnostics = self.diagnostics[diagnostic_start:]
        damaging_codes = {
            "malformed-logic", "malformed-expression",
            "malformed-conditional", "malformed-configured-target",
            "malformed-call", "malformed-index", "malformed-member",
        }
        syntax_complete = (
            not malformed and condition is not None
            and _cml_expression_complete(condition)
            and not any(
                diagnostic.get("code") in damaging_codes
                for diagnostic in logic_diagnostics))
        record = {
            "kind": logic_kind,
            "name": name_token.value if name_token else None,
            "scope": scope,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "arguments": args,
            "conditionAst": condition,
            "syntaxComplete": syntax_complete,
            "parseDiagnosticCodes": [
                diagnostic.get("code") for diagnostic in logic_diagnostics],
            "malformed": not syntax_complete,
        }
        self.logic.append(record)
        return record

    def _parse_unknown(self, scope, annotations=None):
        start = self.current
        self._consume_terminator(start, top_level=(scope == "top-level"))
        end = self.previous
        if end.start < start.start:
            end = self._take()
        raw = self._raw(start, end)
        self._error(
            "unsupported-syntax",
            f"Unsupported or malformed construct in {scope}; analysis "
            "continued at the next balanced boundary.",
            start, "warning")
        node = {
            "kind": "unknown",
            "scope": scope,
            "line": start.line,
            "raw": raw,
            "sourceRange": _cml_range(start, end),
            "annotations": annotations or [],
        }
        self.unknown.append(node)
        return node

    def _consume_terminator(self, start, top_level=False):
        depths = {"(": 0, "[": 0, "{": 0}
        pairs = {")": "(", "]": "[", "}": "{"}
        while not self._at(kind="EOF"):
            token = self.current
            if all(value == 0 for value in depths.values()):
                if token.value == ";":
                    self._take()
                    return
                if token.value == "}":
                    return
                if (token is not start and token.value in _CML_TOP_LEVEL
                        and token.line > start.line):
                    return
                if (not top_level and token.value in _CML_LOGIC_CALLS
                        and token.line > start.line):
                    return
            if token.value in depths:
                depths[token.value] += 1
            elif token.value in pairs:
                opener = pairs[token.value]
                if depths[opener] == 0:
                    return
                depths[opener] -= 1
            self._take()
        self._error(
            "missing-terminator",
            "Construct reached end of input without a balanced terminator.",
            start)

    def _parse_expression_list(self, close):
        expressions = []
        while not self._at(kind="EOF") and not self._at(close):
            if self._at(";") or self._at("}"):
                break
            if (expressions and self.current.value in (
                    _CML_TOP_LEVEL | _CML_LOGIC_CALLS)
                    and self.current.line > self.previous.line):
                break
            before = self.pos
            expressions.append(self._parse_expression())
            if self._match(","):
                continue
            if self._at(close):
                break
            self._error(
                "malformed-expression",
                f"Expected ',' or '{close}' in expression list.",
                self.current)
            if self.pos == before:
                self._take()
            while (not self._at(kind="EOF") and not self._at(close)
                   and not self._at(",") and not self._at(";")
                   and not self._at("}")):
                self._take()
            self._match(",")
        return expressions

    def _parse_expression(self, minimum=0):
        start = self.current
        left = self._parse_prefix()
        while True:
            operator = self.current.value
            spaced_biconditional_tokens = 0
            if operator == "<" and self.pos + 1 < len(self.tokens):
                if self.tokens[self.pos + 1].value == "->":
                    spaced_biconditional_tokens = 1
                elif (self.pos + 2 < len(self.tokens)
                      and self.tokens[self.pos + 1].value == "-"
                      and self.tokens[self.pos + 2].value == ">"):
                    spaced_biconditional_tokens = 2
            spaced_biconditional = spaced_biconditional_tokens > 0
            if spaced_biconditional:
                operator = "<->"
            if operator == "?" and minimum <= 2:
                self._take()
                when_true = self._parse_expression()
                if not self._match(":"):
                    self._error(
                        "malformed-conditional",
                        "Expected ':' in conditional expression.",
                        self.current, "error")
                    when_false = self._node(
                        "unknownExpression", self.current, self.current,
                        reason="missing-conditional-branch")
                else:
                    # CML conditional is right-associative (PDF pp. 1032-1034).
                    when_false = self._parse_expression(2)
                left = self._node(
                    "conditional", start, self.previous, condition=left,
                    whenTrue=when_true, whenFalse=when_false)
                continue
            precedence = self._PRECEDENCE.get(operator)
            if precedence is None or precedence < minimum:
                break
            if spaced_biconditional:
                self._error(
                    "malformed-operator-spacing",
                    "The biconditional operator cannot contain spaces. "
                    "Write '<->' instead of '< ->'. Analysis recovered this "
                    "expression as a biconditional.",
                    self.current, "error")
            self._take()
            if spaced_biconditional:
                for _ in range(spaced_biconditional_tokens):
                    self._take()
            right = self._parse_expression(
                precedence if operator in self._RIGHT_ASSOCIATIVE
                else precedence + 1)
            left = self._node(
                "binary", start, self.previous, operator=operator,
                left=left, right=right)
        return left

    def _parse_prefix(self):
        start = self.current
        if start.value in ("!", "not", "-", "+"):
            operator = self._take()
            operand = self._parse_expression(11)
            return self._node(
                "unary", start, self.previous, operator=operator.value,
                operand=operand)
        if self._match("("):
            expression = self._parse_expression()
            if not self._match(")"):
                self._error(
                    "malformed-expression",
                    "Expected ')' after expression.", start)
            expression = self._node(
                "group", start, self.previous, expression=expression)
            return self._parse_postfix(expression, start)
        if self._match("["):
            values = self._parse_expression_list("]")
            if not self._match("]"):
                self._error(
                    "malformed-expression", "Expected ']' after list.", start)
            return self._parse_postfix(
                self._node("list", start, self.previous, values=values), start)
        if self._match("{"):
            values = self._parse_expression_list("}")
            if not self._match("}"):
                self._error(
                    "malformed-row-literal",
                    "Expected '}' after table row literal.", start, "error")
            return self._parse_postfix(
                self._node(
                    "rowLiteral", start, self.previous, values=values),
                start)
        if start.kind == "STRING":
            self._take()
            raw_value = start.value[1:-1] if len(start.value) >= 2 else ""
            node = self._node(
                "literal", start, start, value=raw_value,
                literalType="string")
            return self._parse_postfix(node, start)
        if start.kind == "NUMBER":
            self._take()
            compact = start.value.replace("_", "")
            try:
                value = float(compact) if any(
                    char in compact for char in ".eE") else int(compact)
            except ValueError:
                value = compact
            node = self._node(
                "literal", start, start, value=value,
                literalType="number")
            return self._parse_postfix(node, start)
        if start.kind == "IDENT":
            self._take()
            lowered = start.value.lower()
            if lowered in ("true", "false", "null"):
                value = (lowered == "true") if lowered != "null" else None
                node = self._node(
                    "literal", start, start, value=value,
                    literalType=lowered)
            else:
                node = self._node("name", start, start, name=start.value)
            return self._parse_postfix(node, start)

        self._error(
            "malformed-expression",
            f"Expected expression, found {start.value!r}.", start)
        if start.kind != "EOF":
            self._take()
        return self._node(
            "unknownExpression", start, self.previous,
            reason="unsupported-token")

    def _parse_postfix(self, node, start):
        while True:
            if self._match("."):
                if not self._at(kind="IDENT"):
                    self._error(
                        "malformed-member",
                        "Expected a member name after '.'.", self.current)
                    break
                member = self._take()
                node = self._node(
                    "member", start, member, object=node, member=member.value)
            elif self._match("["):
                index = None if self._at("]") else self._parse_expression()
                if not self._match("]"):
                    self._error(
                        "malformed-index",
                        "Expected ']' after index expression.", start)
                node = self._node(
                    "index", start, self.previous, object=node, index=index)
            elif self._match("("):
                args = self._parse_expression_list(")")
                if not self._match(")"):
                    self._error(
                        "malformed-call",
                        "Expected ')' after call arguments.", start)
                node = self._node(
                    "call", start, self.previous, callee=node, arguments=args)
            elif self._match("{"):
                assignments = []
                configuration_start = self.previous
                while not self._at(kind="EOF") and not self._at("}"):
                    assignment_start = self.current
                    key = self._take() if self._at(kind="IDENT") else None
                    if not key or not self._match("="):
                        self._error(
                            "malformed-configured-target",
                            "Expected attribute=value in configured target.",
                            assignment_start, "error")
                        while (not self._at(kind="EOF")
                               and not self._at(",") and not self._at("}")):
                            self._take()
                        value = self._node(
                            "unknownExpression", assignment_start,
                            self.previous, reason="malformed-assignment")
                    else:
                        value = self._parse_expression(1)
                    assignments.append({
                        "attribute": key.value if key else None,
                        "value": value,
                        "raw": self._raw(assignment_start, self.previous),
                        "sourceRange": _cml_range(
                            assignment_start, self.previous),
                    })
                    if not self._match(","):
                        break
                if not self._match("}"):
                    self._error(
                        "malformed-configured-target",
                        "Expected '}' after configured target attributes.",
                        configuration_start, "error")
                node = self._node(
                    "configuredTarget", start, self.previous, target=node,
                    assignments=assignments)
            else:
                break
        return node


def _cml_expression_complete(node):
    """True only when no recovery placeholder survives in an expression."""
    if not isinstance(node, dict):
        return False
    if node.get("kind") == "unknownExpression":
        return False
    for value in node.values():
        if isinstance(value, dict) and "kind" in value:
            if not _cml_expression_complete(value):
                return False
        elif isinstance(value, list):
            for child in value:
                if (isinstance(child, dict) and "kind" in child
                        and not _cml_expression_complete(child)):
                    return False
                if isinstance(child, dict):
                    nested = child.get("value")
                    if (isinstance(nested, dict)
                            and not _cml_expression_complete(nested)):
                        return False
    return True




_SEMANTIC_POSITION_FIELDS = {
    "raw", "sourceRange", "line", "column", "start", "end",
    "startLine", "endLine", "startColumn", "endColumn",
    "parseDiagnosticCodes", "syntaxComplete", "malformed",
}


def _semantic_value(value):
    """Canonical AST value without formatting or source-position metadata."""
    if isinstance(value, dict):
        return {
            key: _semantic_value(item)
            for key, item in sorted(value.items())
            if key not in _SEMANTIC_POSITION_FIELDS
        }
    if isinstance(value, list):
        return [_semantic_value(item) for item in value]
    return value


def _semantic_line_range(source_range):
    if not isinstance(source_range, dict):
        return None
    start = source_range.get("start") or {}
    end = source_range.get("end") or {}
    start_line = max(1, int(start.get("line") or 1))
    end_line = max(start_line, int(end.get("line") or start_line))
    return {"startLine": start_line, "endLine": end_line}


def _semantic_entity(identity, kind, name, scope, source_range, raw,
                     properties):
    return {
        "identity": identity,
        "kind": kind,
        "name": name,
        "scope": scope,
        "range": _semantic_line_range(source_range),
        "raw": raw or "",
        "properties": _semantic_value(properties),
    }


def _semantic_index(content):
    """Parse CML once and index named entities independently of line order."""
    tokens, diagnostics = _tokenize_cml(content)
    parser = _CmlParser(content, tokens, diagnostics)
    declarations, types, logic, unknown = parser.parse()
    entities = []

    for declaration in declarations:
        kind = declaration.get("kind")
        name = declaration.get("name")
        if kind == "type" or not name:
            continue
        entities.append(_semantic_entity(
            f"{kind}:{name}", kind, name, "top-level",
            declaration.get("sourceRange"), declaration.get("raw"), {
                "dataType": declaration.get("dataType"),
                "annotations": declaration.get("annotations") or [],
                "value": declaration.get("value"),
            }))

    for type_record in types:
        type_name = type_record.get("name")
        if not type_name:
            continue
        entities.append(_semantic_entity(
            f"type:{type_name}", "type", type_name, "top-level",
            type_record.get("sourceRange"), type_record.get("raw"), {
                "parent": type_record.get("parent"),
                "annotations": type_record.get("annotations") or [],
                "stub": bool(type_record.get("stub")),
            }))
        for variable in type_record.get("variables") or []:
            name = variable.get("name")
            if not name:
                continue
            entities.append(_semantic_entity(
                f"variable:{type_name}:{name}", "variable", name, type_name,
                variable.get("sourceRange"), variable.get("raw"), {
                    "dataType": variable.get("dataType"),
                    "annotations": variable.get("annotations") or [],
                    "domain": variable.get("domain"),
                }))
        for relation in type_record.get("relations") or []:
            name = relation.get("name")
            if not name:
                continue
            entities.append(_semantic_entity(
                f"relation:{type_name}:{name}", "relation", name, type_name,
                relation.get("sourceRange"), relation.get("raw"), {
                    "target": relation.get("target"),
                    "cardinality": relation.get("cardinality"),
                    "order": relation.get("order"),
                    "body": relation.get("body"),
                    "annotations": relation.get("annotations") or [],
                }))

    for record in logic:
        kind = record.get("kind") or "logic"
        scope = record.get("scope") or "top-level"
        name = record.get("name")
        properties = {
            "annotations": record.get("annotations") or [],
            "arguments": record.get("arguments") or [],
            "condition": record.get("conditionAst"),
        }
        if name:
            identity = f"logic:{scope}:{kind}:{name}"
        else:
            # Anonymous rules have no platform identity. An exact structural
            # fingerprint safely recognizes moved/unchanged rules without
            # guessing that two different rules are modifications.
            fingerprint = hashlib.sha256(json.dumps(
                _semantic_value(properties), sort_keys=True,
                separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
            identity = f"logic:{scope}:{kind}:anonymous:{fingerprint}"
        entities.append(_semantic_entity(
            identity, kind, name, scope, record.get("sourceRange"),
            record.get("raw"), properties))

    issues = [{
        "code": item.get("code"),
        "severity": item.get("severity"),
        "message": item.get("message"),
        "line": item.get("line"),
    } for item in diagnostics if item.get("severity") in ("error", "warning")]
    return entities, issues, len(unknown)


def _semantic_property_changes(source, target):
    source_props = source.get("properties") or {}
    target_props = target.get("properties") or {}
    changes = []
    for prop in sorted(set(source_props) | set(target_props)):
        if source_props.get(prop) != target_props.get(prop):
            changes.append({
                "property": prop,
                "source": source_props.get(prop),
                "target": target_props.get(prop),
            })
    return changes


def _semantic_result(status, source=None, target=None, changes=None,
                     reason=None):
    entity = source or target or {}
    result = {
        "kind": entity.get("kind"),
        "identity": entity.get("identity"),
        "name": entity.get("name"),
        "scope": entity.get("scope"),
        "status": status,
        "sourceRange": source.get("range") if source else None,
        "targetRange": target.get("range") if target else None,
        "propertyChanges": changes or [],
    }
    if reason:
        result["reason"] = reason
    return result


def compare_cml_semantics(source_content, target_content):
    """Compare parsed CML entities by stable structural identity in O(n)."""
    source_entities, source_issues, source_unknown = _semantic_index(
        source_content or "")
    target_entities, target_issues, target_unknown = _semantic_index(
        target_content or "")
    source_map, target_map = {}, {}
    for entity in source_entities:
        source_map.setdefault(entity["identity"], []).append(entity)
    for entity in target_entities:
        target_map.setdefault(entity["identity"], []).append(entity)

    results = []
    for identity in sorted(set(source_map) | set(target_map)):
        source_group = source_map.get(identity, [])
        target_group = target_map.get(identity, [])
        if len(source_group) > 1 or len(target_group) > 1:
            remaining_target = list(target_group)
            unmatched_source = []
            for source in source_group:
                exact_index = next((
                    index for index, target in enumerate(remaining_target)
                    if source["properties"] == target["properties"]), None)
                if exact_index is None:
                    unmatched_source.append(source)
                    continue
                target = remaining_target.pop(exact_index)
                moved = (
                    (source.get("range") or {}).get("startLine")
                    != (target.get("range") or {}).get("startLine"))
                results.append(_semantic_result(
                    "MOVED" if moved else "UNCHANGED", source, target))
            if len(unmatched_source) == 1 and len(remaining_target) == 1:
                source, target = unmatched_source[0], remaining_target[0]
                results.append(_semantic_result(
                    "MODIFIED", source, target,
                    _semantic_property_changes(source, target)))
            else:
                for source in unmatched_source:
                    results.append(_semantic_result(
                        "AMBIGUOUS", source=source,
                        reason="Duplicate semantic identity in source or target."))
                for target in remaining_target:
                    results.append(_semantic_result(
                        "AMBIGUOUS", target=target,
                        reason="Duplicate semantic identity in source or target."))
            continue

        source = source_group[0] if source_group else None
        target = target_group[0] if target_group else None
        if source is None:
            results.append(_semantic_result("ADDED", target=target))
        elif target is None:
            results.append(_semantic_result("REMOVED", source=source))
        else:
            changes = _semantic_property_changes(source, target)
            if changes:
                results.append(_semantic_result(
                    "MODIFIED", source, target, changes))
            else:
                moved = (
                    (source.get("range") or {}).get("startLine")
                    != (target.get("range") or {}).get("startLine"))
                results.append(_semantic_result(
                    "MOVED" if moved else "UNCHANGED", source, target))

    counts = {
        status: sum(item["status"] == status for item in results)
        for status in (
            "UNCHANGED", "MOVED", "ADDED", "REMOVED", "MODIFIED", "AMBIGUOUS")
    }
    return {
        "schemaVersion": "1.0",
        "entities": results,
        "stats": counts,
        "sourceParseIssues": source_issues,
        "targetParseIssues": target_issues,
        "sourceUnknownCount": source_unknown,
        "targetUnknownCount": target_unknown,
    }

