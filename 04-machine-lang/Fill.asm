// This file is part of www.nand2tetris.org
// and the book "The Elements of Computing Systems"
// by Nisan and Schocken, MIT Press.

// Runs an infinite loop that listens to the keyboard input.
// When a key is pressed (any key), the program blackens the screen,
// i.e. writes "black" in every pixel. When no key is pressed, 
// the screen should be cleared.

// Loop through the pixels, at each increment in pixel, check keyboard reg val, do acc

// 16384 - First screen reg addr
// 24575 - Last screen reg addr
// keyboard addr = 24576

// initialising curr
@16384
D=A

@curr
M=D

(KEYB)
	// read keyb reg
	@24576
	D=M

	// if no key pressed, keyb == 0, color = 0(white, clr screen)
	@ELSE
	D;JEQ

	// if key is pressed, keyb != 0, color = -1(black)
	@color
	M=-1

	// goto screen loop
	@DISPLAY
	0;JMP
	
(ELSE)
	@color
	M=0
	
	@DISPLAY
	0;JMP

(DISPLAY)
	// write color val in pixel reg
	@color
	D=M
	
	// !! Ptr->Ptr 
	@curr
	A=M
	M=D

	// incr curr addr
	@curr
	M=M+1
	
	// if addr > than last, goto keyboard loop
	// curr - 24575 > 0
	@curr
	D=M
	
	@24575
	D=D-A
	
	@RESET_CURR
	D;JGT

	@KEYB
	0;JMP

(RESET_CURR)
	// reset curr to 16384
	@16384
	D=A
	
	@curr
	M=D

	@KEYB
	0;JMP