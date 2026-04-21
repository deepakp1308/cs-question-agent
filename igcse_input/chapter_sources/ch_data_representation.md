# Data representation

## Why computers use binary

Computers are built from electronic components that have two stable states: on or off. These two states map naturally to the two digits of the binary number system, 1 and 0. Every value a computer processes — numbers, text, images, sound, instructions — is ultimately stored as a long sequence of binary digits (bits). A single bit can hold one of two values. A group of 8 bits is called a byte and can represent 2^8 = 256 different values.

## Binary, denary and hexadecimal

Denary (also called decimal) is the base-10 system humans use every day, with digits 0 to 9. Each position in a denary number represents a power of 10.

Binary is the base-2 system with digits 0 and 1. Each position represents a power of 2. For an 8-bit number the place values from left (most significant) to right (least significant) are 128, 64, 32, 16, 8, 4, 2, 1.

To convert binary to denary, add up the place values wherever there is a 1. For example 11010010 has 1s in the 128, 64, 16 and 2 columns, giving 128 + 64 + 16 + 2 = 210.

To convert denary to binary, repeatedly divide by 2 and record the remainders, then read them in reverse order; or subtract the largest power of 2 that fits, put a 1 in that column, and continue with the remainder.

Hexadecimal (base 16) uses the digits 0-9 and the letters A-F, where A = 10, B = 11, C = 12, D = 13, E = 14, F = 15. Each hexadecimal digit represents exactly 4 bits (a nibble), so one byte is two hexadecimal digits. Hexadecimal is used in memory dumps, MAC addresses, HTML colour codes, error codes, and assembly language because it is much shorter and easier to read than binary.

To convert binary to hexadecimal, split the binary number into groups of 4 bits from the right and convert each group to its hex digit. For example 11010010 splits as 1101 | 0010 which is D | 2, giving D2. To convert hex to binary, replace each hex digit with its 4-bit binary equivalent.

To convert between hex and denary, convert via binary, or use positional arithmetic: each position in a hex number is a power of 16. For example 2A hex = 2 × 16 + 10 = 42 denary.

## Binary addition and overflow

Binary addition follows the same column rules as denary but with only two digits: 0 + 0 = 0, 0 + 1 = 1, 1 + 1 = 10 (write 0 carry 1), 1 + 1 + 1 = 11 (write 1 carry 1).

Overflow occurs when the result of an addition requires more bits than the register can hold. For an 8-bit register the maximum unsigned value is 255 (11111111). If an addition produces a 9-bit result the leftmost bit is lost; this is called an overflow error and the stored answer is incorrect.

## Binary shifts

A binary shift moves the bits in a register left or right by a fixed number of places. A left shift by n places multiplies the value by 2^n; a right shift by n places divides the value by 2^n and discards any remainder. Bits shifted out of the register are lost and zeros are shifted in from the opposite side. Shifts are much faster than multiplication and division for powers of two.

## Two's complement for negative numbers

Two's complement is the standard method for representing signed integers in binary. The leftmost bit is the sign bit: 0 means positive, 1 means negative. To find the two's complement of a positive number, invert all the bits and add 1. For example, in 8 bits, +5 is 00000101; invert to 11111010; add 1 to get 11111011, which is -5. The range of an 8-bit two's complement number is -128 to +127.

## Representing text, images and sound

Text is represented using character sets. ASCII uses 7 bits to encode 128 characters (letters, digits, punctuation, control codes); extended ASCII uses 8 bits for 256. Unicode uses up to 32 bits and can represent every character in every writing system in the world, at the cost of extra storage.

A digital image is made from a grid of pixels. Each pixel's colour is stored as a binary number. Colour depth is the number of bits per pixel: 1 bit gives black and white, 8 bits gives 256 colours, 24 bits (true colour) gives about 16.7 million colours. Resolution is the width in pixels multiplied by the height in pixels. File size in bits = width × height × colour depth. Increasing resolution or colour depth increases detail and file size.

Sound is recorded by sampling the analogue wave at regular intervals. The sample rate is how many samples are taken per second, measured in hertz (Hz). The sample resolution (bit depth) is the number of bits used to store each sample. Higher sample rate and higher bit depth give better sound quality at the cost of a larger file. File size in bits = sample rate × bit depth × duration in seconds × number of channels.

## File sizes

File size is measured in bytes and multiples: 1 kibibyte (KiB) = 1024 bytes, 1 mebibyte (MiB) = 1024 KiB, 1 gibibyte (GiB) = 1024 MiB, 1 tebibyte (TiB) = 1024 GiB. In everyday use the decimal prefixes kilobyte (1000 bytes), megabyte (1 000 000 bytes), etc. are also common.

## Compression

Compression reduces the size of a file so that it uses less storage and can be transmitted faster. Lossless compression reduces file size without losing any data; the original file can be reconstructed exactly. Examples include run-length encoding (RLE) and the ZIP format. RLE replaces a run of repeated values with a single value and a count. Lossless compression is suitable for text, program code, and medical images where no loss is acceptable.

Lossy compression reduces file size by discarding some data permanently. The file is smaller but the original cannot be recovered exactly. Examples include JPEG for images and MP3 for sound. Lossy compression removes detail that humans are less likely to notice, giving a much greater reduction in size than lossless methods. It is used for photos, music, and video where some loss is acceptable.
