# Hardware

## The Central Processing Unit (CPU)

The CPU is the part of a computer that fetches, decodes and executes program instructions. It is often called the brain of the computer. The CPU reads instructions from main memory, decides what they mean, performs the required operation, and writes any result back to memory or to a register.

## Von Neumann architecture

In a Von Neumann machine program instructions and data share the same main memory and travel over the same bus. A Von Neumann CPU has the following key components:

- Arithmetic Logic Unit (ALU) — performs arithmetic operations (add, subtract, multiply, divide) and logical operations (AND, OR, NOT, comparisons).
- Control Unit (CU) — decodes instructions and sends control signals to the rest of the computer so the instruction is carried out.
- Registers — small, very fast storage locations inside the CPU used during an instruction. Important registers include the Program Counter (PC) which holds the address of the next instruction, the Memory Address Register (MAR) which holds the address being accessed, the Memory Data Register (MDR) which holds the value being read from or written to memory, the Accumulator which holds the current result of ALU operations, and the Current Instruction Register (CIR) which holds the instruction currently being executed.
- Buses — parallel wires that carry data, addresses, or control signals between the CPU, memory, and I/O devices. The address bus carries the memory address, the data bus carries the actual data, the control bus carries control signals.

## The fetch-decode-execute cycle

1. Fetch — the address in the PC is copied to the MAR. The instruction at that address is copied from memory into the MDR and then into the CIR. The PC is incremented so it points to the next instruction.
2. Decode — the control unit interprets the instruction to work out what operation to perform.
3. Execute — the operation is carried out, typically by the ALU. Any result is written back to a register or to memory.

The cycle then repeats with the next instruction.

## Embedded systems

An embedded system is a dedicated computer built into a larger device to carry out a specific task. Examples include washing machines, microwave ovens, traffic lights, car engine management systems, and fitness trackers. Embedded systems typically have a fixed program stored in ROM, limited memory, and real-time constraints. They are usually cheaper, more reliable, and use less power than a general-purpose computer.

## Input and output devices

Input devices provide data to the computer. Examples include keyboards, mice, microphones, barcode scanners, QR readers, cameras, touch screens, and sensors. Output devices present data to the user or to the physical world. Examples include monitors, printers, speakers, actuators, and motors.

## Sensors

A sensor is an input device that measures a physical quantity and converts it to a signal the computer can read. Common sensors:
- Temperature sensor — measures heat.
- Light sensor — measures brightness.
- Pressure sensor — measures force per unit area, often used in alarms and weighing machines.
- Moisture / humidity sensor — measures water content in soil or air.
- Infrared / motion sensor — detects movement.
- pH sensor — measures acidity.
- Gas sensor — detects specific gases.
An analogue-to-digital converter (ADC) turns the continuous sensor signal into discrete digital values the computer can process.

## Primary memory: RAM and ROM

Random Access Memory (RAM) holds the program and data the CPU is currently using. RAM is volatile — its contents are lost when power is removed. RAM is read/write. More RAM lets the computer run more or larger programs at once.

Read Only Memory (ROM) stores data that cannot normally be changed. ROM is non-volatile — its contents persist when power is removed. Its most common use is storing the bootstrap / BIOS program that starts the computer when it is switched on.

## Secondary storage

Secondary storage holds data long-term, including programs that are not currently running and user files.

- Magnetic storage — hard disk drives (HDD). Data is stored as magnetised spots on spinning platters. Large capacity and relatively cheap per gigabyte, but slower than solid state and sensitive to physical shock.
- Solid-state storage — SSDs and USB flash drives. Data is stored in flash memory (NAND gates that trap electrons). Fast, silent, no moving parts, shock-resistant, but more expensive per gigabyte than HDD and with a limit on the number of write cycles.
- Optical storage — CDs, DVDs, Blu-rays. Data is read by a laser reflecting off pits and lands on the surface. Low-cost, portable, but low capacity and slow compared with SSD.

## Virtual memory

Virtual memory is an area of secondary storage set aside to be used as extra RAM. When physical RAM is full, pages of data not currently being used are moved (paged) to the virtual memory on disk, freeing real RAM for current work. The CPU is able to run programs that are larger than the available RAM, but because disk is much slower than RAM the computer slows down noticeably when heavy paging is needed.

## Cloud storage

Cloud storage stores files on remote servers accessed over the internet. Advantages: files are available from any device with an internet connection; the provider handles backups and hardware failures; storage can be scaled up easily. Disadvantages: needs a reliable internet connection; ongoing subscription cost; privacy and security depend on trusting the provider.

## Connecting to a network

A computer on a network has several addresses and components:
- MAC address — a 48-bit physical address burned into the network interface card, written as 12 hexadecimal digits usually in pairs. It identifies the hardware and does not change between networks.
- IP address — a logical address assigned to a device on a network. IPv4 addresses are 32 bits long, written as four decimal numbers 0–255 separated by dots. IPv6 addresses are 128 bits, written as eight groups of four hexadecimal digits separated by colons.
- Network Interface Card (NIC) — the hardware that lets a computer connect to a network, wired or wireless.
- Router — forwards packets between networks using IP addresses.
- Switch — forwards packets within a network using MAC addresses.
