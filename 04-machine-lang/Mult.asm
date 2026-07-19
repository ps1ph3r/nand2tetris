// This file is part of www.nand2tetris.org
// and the book "The Elements of Computing Systems"
// by Nisan and Schocken, MIT Press.

// Multiplies R0 and R1 and stores the result in R2.
// (R0, R1, R2 refer to RAM[0], RAM[1], and RAM[2], respectively.)
// The algorithm is based on repetitive addition.

// While R1 > 0:
//     R2 += R0
//	   R1 -= 1


// Ensure R1 <= R0 (loop on smaller operand)
@R0
D=M

@R1
D=D-M

@NO_SWAP
D;JGE // R0 >= R1 → no swap

// swap
// temp = a
@R0
D=M

@TEMP
M=D

// a = b
@R1
D=M

@R0
M=D

// b = temp
@TEMP
D=M

@R1
M=D

(NO_SWAP)
	// Initialise R2 to 0
	@R2
	M=0

(LOOP)
	// R1 in DReg
    @R1
    D=M
	
	// If D(R1) == 0; Go to End
	@END
	D;JEQ

	// Put R0 in DReg
    @R0
    D=M
	
	@R2
	M=D+M
	
	@R1
	M=M-1
	
	@LOOP
	0;JMP
	
(END)
    @END
    0;JMP