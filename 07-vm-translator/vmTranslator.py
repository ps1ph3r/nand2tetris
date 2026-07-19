import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Union
from enum import Enum, auto


# AST (abstract syntax tree) definitions
class Segment(Enum):
    CONSTANT = auto()
    LOCAL = auto()
    ARGUMENT = auto()
    THIS = auto()
    THAT = auto()
    TEMP = auto()
    POINTER = auto()
    STATIC = auto()


@dataclass(frozen=True)
class Push:
    segment: Segment
    index: int


@dataclass(frozen=True)
class Pop:
    segment: Segment
    index: int


@dataclass(frozen=True)
class Arithmetic:
    op: str


@dataclass(frozen=True)
class Label:
    label_name: str


@dataclass(frozen=True)
class Goto:
    label_name: str


@dataclass(frozen=True)
class IfGoto:
    label_name: str


@dataclass(frozen=True)
class Function:
    name: str
    n_vars: int


@dataclass(frozen=True)
class Call:
    name: str
    n_args: int


@dataclass(frozen=True)
class Return:
    pass  # return takes no argument


# A type alias representing any valid VM command
Command = Union[Push, Pop, Arithmetic, Label, Goto, IfGoto, Function, Call, Return]


# context & lookups
# Holds state needed during generation, like the current filename for static variables or labels.
@dataclass
class Context:
    filename: str
    label_count: int = 0

    def next_label(self) -> str:
        self.label_count += 1
        return f"{self.filename}.L{self.label_count}"


# Maps our Segment enum to the Hack assembly base pointers
SEGMENT_SYMBOLS = {
    Segment.LOCAL: "LCL",
    Segment.ARGUMENT: "ARG",
    Segment.THIS: "THIS",
    Segment.THAT: "THAT",
    # TEMP, POINTER, and STATIC have special rules and don't use base pointers in the way others do.
}

BINARY_OPS = {
    "add": "M=D+M",
    "sub": "M=M-D",  # !! y is in D, x is in M
    "and": "M=D&M",
    "or": "M=D|M",
}

UNARY_OPS = {"neg": "M=-M", "not": "M=!M"}

COMPARE_JUMPS = {"eq": "JEQ", "gt": "JGT", "lt": "JLT"}


# Parser - String -> AST
def parse_line(line: str) -> Command | None:
    cleaned = line.split("//")[0].strip()
    if not cleaned:
        return None

    parts = cleaned.split()
    match parts[0]:
        case "push":
            return Push(segment=Segment[parts[1].upper()], index=int(parts[2]))
        case "pop":
            return Pop(segment=Segment[parts[1].upper()], index=int(parts[2]))
        case "add" | "sub" | "neg" | "eq" | "gt" | "lt" | "and" | "or" | "not":
            return Arithmetic(op=parts[0])
        case "label":
            return Label(label_name=parts[1])
        case "goto":
            return Goto(label_name=parts[1])
        case "if-goto":
            return IfGoto(label_name=parts[1])
        case "function":
            return Function(name=parts[1], n_vars=int(parts[2]))
        case "call":
            return Call(name=parts[1], n_args=int(parts[2]))
        case "return":
            return Return()
        case _:
            raise ValueError(f"Unknown command: {cleaned}")


# Code Generator AST -> Assembly strings
def codegen(cmd: Command, ctx: Context) -> list[str]:
    match cmd:
        # PUSH CONSTANT
        case Push(segment=Segment.CONSTANT, index=idx):
            return [
                f"@{idx}",
                "D=A",  # D = idx
                "@SP",
                "A=M",  # A = RAM[SP] (Point A to the top of the stack)
                "M=D",  # RAM[A] = D
                "@SP",
                "M=M+1",  # SP++
            ]

        # PUSH VIRTUAL SEGMENT
        case Push(segment=seg, index=idx) if seg in SEGMENT_SYMBOLS:
            sym = SEGMENT_SYMBOLS[seg]
            return [
                # Copy index value to data register
                f"@{idx}",
                "D=A",
                # Add the segment base address pointer to index
                f"@{sym}",
                "A=D+M",
                # Get the value from the calculated address
                "D=M",
                # Push D onto the stack and increment SP
                "@SP",
                "A=M",
                "M=D",
                "@SP",
                "M=M+1",
            ]

        case Pop(segment=seg, index=idx) if seg in SEGMENT_SYMBOLS:
            sym = SEGMENT_SYMBOLS[seg]
            return [
                # Calculate target address and store in R13
                f"@{idx}",
                "D=A",
                f"@{sym}",
                # D = base + index
                "D=D+M",
                # RAM[13] = target address
                "@R13",
                "M=D",
                # Pop the top stack value into D
                "@SP",
                "AM=M-1",
                # D = popped value
                "D=M",
                # Move D to the target address stored in R13
                "@R13",
                "A=M",  # A = target address
                "M=D",  # Write popped value to target
            ]

        # BINARY ARITHMETIC & LOGICAL(Add, Sub, And, Or)
        case Arithmetic(op=op) if op in BINARY_OPS:
            calc_instruction = BINARY_OPS[op]
            return [
                # Move SP down and select the second operand y
                "@SP",
                "M=M-1",
                # Store the second operand in D, D = y
                "A=M",
                "D=M",
                # Select the first operand (one slot below)
                "A=A-1",
                # Add D and M, store in M, x=y+x
                calc_instruction,
                # Remember: SP is already in the right place now!
            ]

        # UNARY OPERATIONS (neg, not)
        case Arithmetic(op=op) if op in UNARY_OPS:
            calc_instruction = UNARY_OPS[op]
            return [
                # Select the operand x
                "@SP",
                "A=M-1",  # point it to the top item
                calc_instruction,  # mutate it in place
            ]

        # COMPARISONS (eq, gt, lt)
        case Arithmetic(op=op) if op in COMPARE_JUMPS:
            jmp_directive = COMPARE_JUMPS[op]
            label_true = ctx.next_label()
            label_end = ctx.next_label()

            return [
                # SP down to y
                "@SP",
                "AM=M-1",
                # store y in D
                "D=M",
                # now move to x (A=A-1)
                "A=A-1",
                # store x-y in D
                "D=M-D",
                # jump if equal
                f"@{label_true}",
                f"D;{jmp_directive}",  # Inject JEQ, JGT, or JLT here
                # false block
                # We must point A back to x's slot because @label_true ruined it
                "@SP",
                "A=M-1",
                "M=0",
                f"@{label_end}",
                "0;JMP",  # Jump to the end to skip the true block
                # true block
                f"({label_true})",
                # We must point A back to x's slot again for the same reason
                "@SP",
                "A=M-1",
                "M=-1",
                # end passthrough
                f"({label_end})",
            ]

        # FIXED MEMORY SEGMENTS (temp, pointer)
        case Push(segment=seg, index=idx) if seg in (Segment.TEMP, Segment.POINTER):
            base = 5 if seg == Segment.TEMP else 3
            target_addr = base + idx
            return [
                # push temp/pointer
                f"@{target_addr}",
                "D=M",  # read the value directly, No pointer chasing needed.
                "@SP",
                "A=M",
                "M=D",
                "@SP",
                "M=M+1",
            ]

        case Pop(segment=seg, index=idx) if seg in (Segment.TEMP, Segment.POINTER):
            base = 5 if seg == Segment.TEMP else 3
            target_addr = base + idx
            return [
                # pop temp/pointer
                "@SP",
                "AM=M-1",
                "D=M",
                f"@{target_addr}",
                "M=D",  # Just write D directly to the fixed address
            ]

        # STATIC SEGMENT
        case Push(segment=Segment.STATIC, index=idx):
            return [
                f"// push static {idx}",
                f"@{ctx.filename}.{idx}",
                "D=M",
                "@SP",
                "A=M",
                "M=D",
                "@SP",
                "M=M+1",
            ]

        case Pop(segment=Segment.STATIC, index=idx):
            return [
                f"// pop static {idx}",
                "@SP",
                "AM=M-1",
                "D=M",
                f"@{ctx.filename}.{idx}",
                "M=D",
            ]

        case Label(label_name=name):
            return [
                f"// label {name}",
                f"({name})",
            ]

        case Goto(label_name=name):
            return [
                f"// goto {name}",
                f"@{name}",
                "0;JMP",
            ]

        case IfGoto(label_name=name):
            return [
                f"// if-goto {name}",
                "@SP",
                "AM=M-1",
                "D=M",
                f"@{name}",
                "D;JNE",
            ]

        # FUNCTION COMMANDS
        case Function(name=func_name, n_vars=n):
            # 1. Declare the function's entry label (using the parentheses syntax!)
            asm = [
                f"// function {func_name} {n}",
                f"({func_name})",
            ]

            # Push '0' onto the stack 'n' times to initialize the local variables.
            for _ in range(n):
                asm.extend(
                    [
                        "@SP",
                        "A=M",  # A = RAM[SP] (Point A to the top of the stack)
                        "M=0",  # RAM[A] = 0
                        "@SP",
                        "M=M+1",  # SP++
                    ]
                )

            return asm

        case Call(name=func_name, n_args=n):
            ret_addr = ctx.next_label()

            # tiny helper for pushing predefined symbols (LCL, ARG, THIS, THAT)
            # load the symbol into A, read its value (M) into D, and push D to the stack.
            def push_symbol(sym):
                return [
                    f"@{sym}",
                    "D=M",
                    "@SP",
                    "A=M",
                    "M=D",
                    "@SP",
                    "M=M+1",
                ]

            asm = [f"// call {func_name} {n}"]

            # Push return address (this is slightly different because it's a label/value, not a RAM pointer)
            asm.extend(
                [
                    f"@{ret_addr}",
                    "D=A",
                    "@SP",
                    "A=M",
                    "M=D",
                    "@SP",
                    "M=M+1",
                ]
            )

            # 2. Push LCL, ARG, THIS, THAT
            asm.extend(push_symbol("LCL"))
            asm.extend(push_symbol("ARG"))
            asm.extend(push_symbol("THIS"))
            asm.extend(push_symbol("THAT"))

            # 3. Reposition ARG to SP - 5 - nArgs
            asm.extend(
                [
                    "// ARG = SP - 5 - nArgs",
                    # Load SP into D
                    "@SP",
                    "D=M",
                    # Subtract 5
                    "@5",
                    "D=D-A",
                    # Subtract n (n_args)
                    f"@{n}",
                    "D=D-A",
                    # Store the result in ARG
                    "@ARG",
                    "M=D",
                ]
            )

            # Reposition LCL to SP
            asm.extend(
                [
                    "// LCL = SP",
                    "@SP",
                    "D=M",
                    "@LCL",
                    "M=D",
                ]
            )

            # Jump to the function
            asm.extend(
                [
                    f"@{func_name}",
                    "0;JMP",
                ]
            )

            # Inject the return address label
            asm.append(f"({ret_addr})")

            return asm

        case Return():
            return [
                "// --- return ---",
                # frame = LCL (Using R13 as 'frame')
                "@LCL",
                "D=M",
                "@R13",
                "M=D",
                # retAddr = *(frame - 5) (Using R14 as 'retAddr')
                "// retAddr = *(frame - 5)",
                "@5",
                "D=A",
                "@R13",
                "A=M-D",  # A = frame - 5
                "D=M",  # D = *(frame - 5)
                "@R14",
                "M=D",  # R14 = return address
                # *ARG = pop()
                "// *ARG = pop()",
                "@SP",
                "A=M-1",
                "D=M",
                "@ARG",
                "A=M",
                "M=D",
                # SP = ARG + 1
                "// SP = ARG + 1",
                "@ARG",
                "D=M",
                "@SP",
                "M=D+1",
                # THAT = *(frame - 1)
                "// THAT = *(frame - 1)",
                "@R13",
                "AM=M-1",  # Decrement pointer and select it
                "D=M",
                "@THAT",
                "M=D",
                # THIS = *(frame - 2)
                "// THIS = *(frame - 2)",
                "@R13",
                "AM=M-1",  # R13 is now frame - 2!
                "D=M",
                "@THIS",
                "M=D",
                # ARG = *(frame - 3)
                "// ARG = *(frame - 3)",
                "@R13",
                "AM=M-1",  # R13 is now frame - 3!
                "D=M",
                "@ARG",
                "M=D",
                # LCL = *(frame - 4)
                "// LCL = *(frame - 4)",
                "@R13",
                "AM=M-1",  # R13 is now frame - 4!
                "D=M",
                "@LCL",
                "M=D",
                # goto retAddr
                "// goto retAddr",
                "@R14",
                "A=M",  # Point A to the return address
                "0;JMP",  # Jump!
            ]

        case _:
            # Debug : Catch-all for commands that haven't been implemented yet
            return [f"// TODO: Implement {cmd}"]


def main():
    if len(sys.argv) != 2:
        print("Usage: python vmTranslator.py <file.vm | directory>")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    # Check if input is a directory or a single file
    if input_path.is_dir():
        vm_files = list(input_path.glob("*.vm"))
        output_path = input_path / f"{input_path.name}.asm"
        include_bootstrap = True
    else:
        vm_files = [input_path]
        output_path = input_path.with_suffix(".asm")
        include_bootstrap = False

    assembly = []

    # Bootstrap code (only if directory)
    if include_bootstrap:
        ctx = Context(filename="Boot")
        assembly.extend(
            [
                "// BOOTSTRAP",
                "@256",
                "D=A",
                "@SP",
                "M=D",
            ]
        )
        assembly.extend(codegen(Call("Sys.init", 0), ctx))

    for vm_file in vm_files:
        # Create a new context so Static variables use the correct filename prefix
        ctx = Context(filename=vm_file.stem)

        raw_lines = vm_file.read_text().splitlines()
        commands = [cmd for line in raw_lines if (cmd := parse_line(line)) is not None]

        for cmd in commands:
            assembly.append(f"// {cmd}")
            assembly.extend(codegen(cmd, ctx))

    output_path.write_text("\n".join(assembly) + "\n")
    print(f"Successfully compiled to {output_path.name}")


if __name__ == "__main__":
    main()
