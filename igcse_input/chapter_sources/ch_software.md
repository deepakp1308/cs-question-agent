# Software

## Types of software

Software is the set of programs that tell a computer what to do. It is usually divided into two main categories.

- System software controls the hardware and provides a platform for other software to run. Examples: the operating system, device drivers, utilities, compilers and assemblers.
- Application software performs tasks for the user. Examples: word processors, spreadsheets, web browsers, games, media players.

## The operating system

The operating system (OS) is the most important piece of system software. It acts as a bridge between the user, the application software, and the hardware. Typical functions of an operating system include:

- Managing memory — deciding which program and data are held in RAM, moving pages between RAM and virtual memory.
- Managing processes — scheduling which process runs next on the CPU, switching between processes so several appear to run at once.
- Managing input and output — passing data to and from devices through device drivers.
- Managing files — organising data into files and folders on secondary storage, keeping track of where each file is stored, controlling read/write access.
- Providing a user interface — a graphical user interface (GUI) or a command-line interface (CLI) so the user can interact with the computer.
- Managing security — user accounts, passwords, permissions, and access to resources.
- Managing errors — detecting problems and reporting them to the user or to application programs.

Without an operating system a general-purpose computer cannot be used in any practical way: the user would have to communicate directly with the hardware.

## High-level and low-level languages

A programming language is a formal notation used to write a program.

- High-level languages (Python, Java, C#, JavaScript, VB, and many more) are designed to be easy for humans to read and write. One statement in a high-level language usually does the work of many machine instructions. They are portable between different CPU architectures. They must be translated into machine code before the CPU can execute them.
- Low-level languages are close to the hardware. Assembly language uses short mnemonics (for example MOV, ADD, JMP) that map almost one-to-one to CPU instructions. Machine code is the actual binary instructions the CPU executes; it is specific to a particular CPU architecture.

Advantages of high-level languages: easier and faster to write, easier to read and maintain, portable, fewer bugs.
Advantages of low-level languages: faster execution, smaller memory footprint, direct control of specific hardware features, essential for writing device drivers and operating system kernels.

## Translators

Before a high-level program can run, it must be translated into machine code. There are three common kinds of translator.

- Compiler — translates the entire source program into machine code in one go, producing an executable file. The executable can then be run many times without re-translating. Compilers produce fast, efficient programs and report all the errors found in the whole program at the end of compilation. Examples: C, C++, Go.
- Interpreter — reads the source program one statement at a time and carries it out immediately, without producing a standalone executable. Interpreters make development and debugging easier because you can run code straight away and stop when an error is found, but execution is slower. Examples: Python (in CPython), traditional BASIC, many JavaScript shells.
- Assembler — translates assembly-language code into machine code. It is the translator used for low-level assembly programs.

Some modern language runtimes use a hybrid approach: the source is first compiled into an intermediate bytecode and then that bytecode is interpreted or just-in-time (JIT) compiled at run time.

## Integrated development environments (IDEs)

An IDE is software used to write and test programs. A typical IDE includes:

- A code editor with syntax highlighting that colours keywords, strings, and comments so code is easier to read.
- Autocomplete / code completion that suggests names of variables, functions and keywords as you type.
- A compiler or interpreter, integrated so the program can be run with one click.
- A debugger that allows the programmer to run the program step by step, set breakpoints, and inspect the values of variables while the program is paused.
- Error reporting that highlights syntax errors in the editor as the code is written.

IDEs save time and reduce errors by combining all the tools a programmer needs into a single application.
