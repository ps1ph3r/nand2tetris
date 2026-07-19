import sys
import re
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass


# Tokenizer
class TokenType(Enum):
    KEYWORD = auto()
    SYMBOL = auto()
    IDENTIFIER = auto()
    INT_CONST = auto()
    STRING_CONST = auto()


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str


KEYWORDS = [
    "class",
    "constructor",
    "function",
    "method",
    "field",
    "static",
    "var",
    "int",
    "char",
    "boolean",
    "void",
    "true",
    "false",
    "null",
    "this",
    "let",
    "do",
    "if",
    "else",
    "while",
    "return",
]

KEYWORD_REGEX = r"\b(?:{})\b".format("|".join(KEYWORDS))
SYMBOLS = [
    "{",
    "}",
    "(",
    ")",
    "[",
    "]",
    ".",
    ",",
    ";",
    "+",
    "-",
    "*",
    "/",
    "&",
    "|",
    "<",
    ">",
    "=",
    "~",
]

SYMBOL_REGEX = r"[{}]".format(re.escape("".join(SYMBOLS)))
INT_REGEX = r"\d+"
STRING_REGEX = r'"[^"\n]*"'
IDENTIFIER_REGEX = r"[a-zA-Z_]\w*"

MASTER_REGEX = re.compile(
    f"(?P<KEYWORD>{KEYWORD_REGEX})|"
    f"(?P<SYMBOL>{SYMBOL_REGEX})|"
    f"(?P<INT_CONST>{INT_REGEX})|"
    f"(?P<STRING_CONST>{STRING_REGEX})|"
    f"(?P<IDENTIFIER>{IDENTIFIER_REGEX})"
)


def remove_comments(raw_code: str) -> str:
    clean_code = re.sub(r"/\*.*?\*/", " ", raw_code, flags=re.DOTALL)
    clean_code = re.sub(r"//.*", "", clean_code)
    return clean_code


def tokenize(raw_code: str) -> list[Token]:
    clean_code = remove_comments(raw_code)
    tokens = []
    for match in MASTER_REGEX.finditer(clean_code):
        kind = match.lastgroup
        value = match.group(kind)
        if kind == "STRING_CONST":
            value = value[1:-1]
        tokens.append(Token(TokenType[kind], value))
    return tokens


# context & code generation (symbol table & vm writer)
class SymbolKind(Enum):
    STATIC = "static"
    FIELD = "this"
    ARG = "argument"
    VAR = "local"
    NONE = "none"


@dataclass
class Symbol:
    name: str
    type: str
    kind: SymbolKind
    index: int


class SymbolTable:
    def __init__(self):
        self.class_scope = {}
        self.subroutine_scope = {}
        self.indices = {
            SymbolKind.STATIC: 0,
            SymbolKind.FIELD: 0,
            SymbolKind.ARG: 0,
            SymbolKind.VAR: 0,
        }

    def start_subroutine(self):
        self.subroutine_scope.clear()
        self.indices[SymbolKind.ARG] = 0
        self.indices[SymbolKind.VAR] = 0

    def define(self, name: str, type: str, kind: SymbolKind):
        symbol = Symbol(name, type, kind, self.indices[kind])
        if kind in (SymbolKind.STATIC, SymbolKind.FIELD):
            self.class_scope[name] = symbol
        else:
            self.subroutine_scope[name] = symbol
        self.indices[kind] += 1

    def resolve(self, name: str) -> Symbol | None:
        return self.subroutine_scope.get(name) or self.class_scope.get(name)

    def count(self, kind: SymbolKind) -> int:
        return self.indices[kind]


class VMWriter:
    def __init__(self):
        self.output = []

    def write_push(self, segment: str, index: int):
        self.output.append(f"push {segment} {index}")

    def write_pop(self, segment: str, index: int):
        self.output.append(f"pop {segment} {index}")

    def write_arithmetic(self, command: str):
        self.output.append(command)

    def write_label(self, label: str):
        self.output.append(f"label {label}")

    def write_goto(self, label: str):
        self.output.append(f"goto {label}")

    def write_if(self, label: str):
        self.output.append(f"if-goto {label}")

    def write_call(self, name: str, n_args: int):
        self.output.append(f"call {name} {n_args}")

    def write_function(self, name: str, n_locals: int):
        self.output.append(f"function {name} {n_locals}")

    def write_return(self):
        self.output.append("return")

    def get_output(self) -> str:
        return "\n".join(self.output) + "\n"


# Compilation Engine - AST -> VM
class CompilationEngine:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.idx = 0
        self.symbols = SymbolTable()
        self.vm = VMWriter()

        self.class_name = ""
        self.label_counter = 0

    def get_label(self, prefix: str) -> str:
        self.label_counter += 1
        return f"{prefix}{self.label_counter}"

    def has_more(self) -> bool:
        return self.idx < len(self.tokens)

    def peek(self, offset: int = 0) -> Token | None:
        if self.idx + offset < len(self.tokens):
            return self.tokens[self.idx + offset]
        return None

    def advance(self) -> Token:
        token = self.tokens[self.idx]
        self.idx += 1
        return token

    def consume(self, expected_value: str = None) -> Token:
        token = self.advance()
        if expected_value and token.value != expected_value:
            raise SyntaxError(f"Expected '{expected_value}', got '{token.value}'")
        return token

    # compilation logic

    def compile_class(self):
        self.consume("class")
        self.class_name = self.advance().value
        self.consume("{")

        while self.has_more() and self.peek().value in ["static", "field"]:
            self.compile_class_var_dec()

        while self.has_more() and self.peek().value in [
            "constructor",
            "function",
            "method",
        ]:
            self.compile_subroutine()

        self.consume("}")

    def compile_class_var_dec(self):
        kind_str = self.advance().value
        kind = SymbolKind.STATIC if kind_str == "static" else SymbolKind.FIELD
        type_str = self.advance().value
        name = self.advance().value
        self.symbols.define(name, type_str, kind)

        while self.peek().value == ",":
            self.consume(",")
            name = self.advance().value
            self.symbols.define(name, type_str, kind)

        self.consume(";")

    def compile_subroutine(self):
        self.symbols.start_subroutine()

        subroutine_type = self.advance().value  # constructor, function, method
        _return_type = self.advance().value
        subroutine_name = self.advance().value

        if subroutine_type == "method":
            self.symbols.define("this", self.class_name, SymbolKind.ARG)

        self.consume("(")
        self.compile_parameter_list()
        self.consume(")")

        self.consume("{")
        while self.peek().value == "var":
            self.compile_var_dec()

        n_locals = self.symbols.count(SymbolKind.VAR)
        self.vm.write_function(f"{self.class_name}.{subroutine_name}", n_locals)

        if subroutine_type == "constructor":
            n_fields = self.symbols.count(SymbolKind.FIELD)
            self.vm.write_push("constant", n_fields)
            self.vm.write_call("Memory.alloc", 1)
            self.vm.write_pop("pointer", 0)
        elif subroutine_type == "method":
            self.vm.write_push("argument", 0)
            self.vm.write_pop("pointer", 0)

        self.compile_statements()
        self.consume("}")

    def compile_parameter_list(self):
        if self.peek().value != ")":
            type_str = self.advance().value
            name = self.advance().value
            self.symbols.define(name, type_str, SymbolKind.ARG)

            while self.peek().value == ",":
                self.consume(",")
                type_str = self.advance().value
                name = self.advance().value
                self.symbols.define(name, type_str, SymbolKind.ARG)

    def compile_var_dec(self):
        self.consume("var")
        type_str = self.advance().value
        name = self.advance().value
        self.symbols.define(name, type_str, SymbolKind.VAR)

        while self.peek().value == ",":
            self.consume(",")
            name = self.advance().value
            self.symbols.define(name, type_str, SymbolKind.VAR)

        self.consume(";")

    def compile_statements(self):
        while self.has_more() and self.peek().value in [
            "let",
            "if",
            "while",
            "do",
            "return",
        ]:
            val = self.peek().value
            if val == "let":
                self.compile_let()
            elif val == "if":
                self.compile_if()
            elif val == "while":
                self.compile_while()
            elif val == "do":
                self.compile_do()
            elif val == "return":
                self.compile_return()

    def compile_let(self):
        self.consume("let")
        var_name = self.advance().value
        symbol = self.symbols.resolve(var_name)
        is_array = False

        if self.peek().value == "[":
            is_array = True
            self.consume("[")
            self.compile_expression()
            self.consume("]")
            self.vm.write_push(symbol.kind.value, symbol.index)
            self.vm.write_arithmetic("add")

        self.consume("=")
        self.compile_expression()
        self.consume(";")

        if is_array:
            self.vm.write_pop("temp", 0)
            self.vm.write_pop("pointer", 1)
            self.vm.write_push("temp", 0)
            self.vm.write_pop("that", 0)
        else:
            self.vm.write_pop(symbol.kind.value, symbol.index)

    def compile_if(self):
        label_false = self.get_label("IF_FALSE")
        label_end = self.get_label("IF_END")

        self.consume("if")
        self.consume("(")
        self.compile_expression()
        self.consume(")")

        self.vm.write_arithmetic("not")
        self.vm.write_if(label_false)

        self.consume("{")
        self.compile_statements()
        self.consume("}")
        self.vm.write_goto(label_end)

        self.vm.write_label(label_false)
        if self.peek().value == "else":
            self.consume("else")
            self.consume("{")
            self.compile_statements()
            self.consume("}")

        self.vm.write_label(label_end)

    def compile_while(self):
        label_exp = self.get_label("WHILE_EXP")
        label_end = self.get_label("WHILE_END")

        self.vm.write_label(label_exp)
        self.consume("while")
        self.consume("(")
        self.compile_expression()
        self.consume(")")

        self.vm.write_arithmetic("not")
        self.vm.write_if(label_end)

        self.consume("{")
        self.compile_statements()
        self.consume("}")

        self.vm.write_goto(label_exp)
        self.vm.write_label(label_end)

    def compile_do(self):
        self.consume("do")
        self.compile_term_call(self.advance().value)
        self.consume(";")
        self.vm.write_pop("temp", 0)

    def compile_return(self):
        self.consume("return")
        if self.peek().value != ";":
            self.compile_expression()
        else:
            self.vm.write_push("constant", 0)
        self.consume(";")
        self.vm.write_return()

    def compile_expression(self):
        self.compile_term()
        ops = {
            "+": "add",
            "-": "sub",
            "*": "Math.multiply",
            "/": "Math.divide",
            "&": "and",
            "|": "or",
            "<": "lt",
            ">": "gt",
            "=": "eq",
        }

        while self.has_more() and self.peek().value in ops:
            op = self.advance().value
            self.compile_term()
            if op in ["*", "/"]:
                self.vm.write_call(ops[op], 2)
            else:
                self.vm.write_arithmetic(ops[op])

    def compile_term(self):
        token = self.advance()

        if token.type == TokenType.INT_CONST:
            self.vm.write_push("constant", int(token.value))

        elif token.type == TokenType.STRING_CONST:
            self.vm.write_push("constant", len(token.value))
            self.vm.write_call("String.new", 1)
            for char in token.value:
                self.vm.write_push("constant", ord(char))
                self.vm.write_call("String.appendChar", 2)

        elif token.value == "true":
            self.vm.write_push("constant", 0)
            self.vm.write_arithmetic("not")

        elif token.value in ["false", "null"]:
            self.vm.write_push("constant", 0)

        elif token.value == "this":
            self.vm.write_push("pointer", 0)

        elif token.value in ["-", "~"]:
            self.compile_term()
            self.vm.write_arithmetic("neg" if token.value == "-" else "not")

        elif token.value == "(":
            self.compile_expression()
            self.consume(")")

        elif token.type == TokenType.IDENTIFIER:
            next_val = self.peek().value

            if next_val == "[":
                self.consume("[")
                self.compile_expression()
                self.consume("]")
                symbol = self.symbols.resolve(token.value)
                self.vm.write_push(symbol.kind.value, symbol.index)
                self.vm.write_arithmetic("add")
                self.vm.write_pop("pointer", 1)
                self.vm.write_push("that", 0)
            elif next_val in ["(", "."]:
                self.compile_term_call(token.value)
            else:
                symbol = self.symbols.resolve(token.value)
                self.vm.write_push(symbol.kind.value, symbol.index)

    def compile_term_call(self, name: str):
        n_args = 0
        func_name = name

        if self.peek().value == ".":
            self.consume(".")
            method_name = self.advance().value
            symbol = self.symbols.resolve(name)

            if symbol:
                self.vm.write_push(symbol.kind.value, symbol.index)
                func_name = f"{symbol.type}.{method_name}"
                n_args += 1
            else:
                func_name = f"{name}.{method_name}"
        else:
            self.vm.write_push("pointer", 0)
            func_name = f"{self.class_name}.{name}"
            n_args += 1

        self.consume("(")
        n_args += self.compile_expression_list()
        self.consume(")")

        self.vm.write_call(func_name, n_args)

    def compile_expression_list(self) -> int:
        n_args = 0
        if self.peek().value != ")":
            self.compile_expression()
            n_args += 1
            while self.peek().value == ",":
                self.consume(",")
                self.compile_expression()
                n_args += 1
        return n_args


def main():
    if len(sys.argv) != 2:
        print("Usage: python JackCompiler.py <file.jack | directory>")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if input_path.is_dir():
        jack_files = list(input_path.glob("*.jack"))
    else:
        jack_files = [input_path]

    for jack_file in jack_files:
        raw_text = jack_file.read_text()
        tokens = tokenize(raw_text)

        compiler = CompilationEngine(tokens)
        compiler.compile_class()
        vm_code = compiler.vm.get_output()

        output_file = jack_file.with_suffix(".vm")
        output_file.write_text(vm_code)
        print(f"Compiled {jack_file.name} -> {output_file.name}")


if __name__ == "__main__":
    main()
