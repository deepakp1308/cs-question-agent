# Data transmission

## Packets

Data is broken down into smaller chunks called packets before being transmitted over a network. Splitting data into packets means individual packets can be routed independently, congestion on a single path does not stop the whole transfer, and the receiver can detect and request only the missing packets if something goes wrong.

Each packet has three parts:
- Packet header — contains the sender IP address, the receiver IP address, the packet number (so packets can be reassembled in order at the destination), and the total number of packets.
- Payload — the actual data being carried.
- Trailer — contains an error-detection value such as a checksum or cyclic redundancy check (CRC) and a marker indicating the end of the packet.

At the destination the packets are reassembled into the original file using the packet numbers. If a packet is missing or damaged the receiver requests that specific packet again.

## Transmission methods

Simplex transmission sends data in one direction only (for example from a computer to a printer, although most modern printers are actually duplex).

Half-duplex transmission sends data in both directions but only one direction at a time (for example a walkie-talkie).

Full-duplex transmission sends data in both directions simultaneously (for example a telephone call).

Serial transmission sends data one bit at a time over a single wire. It is slower per wire but avoids skew, so it is reliable over long distances and is the standard for most modern interfaces.

Parallel transmission sends several bits at the same time, one bit per wire. It is faster over short distances but suffers from skew (bits arriving at slightly different times) over long distances. It is used inside a computer for short, high-bandwidth internal buses.

## Universal Serial Bus (USB)

USB is a serial interface standard used to connect peripherals to a computer. Advantages of USB: the connector is standardised so it is hard to plug in incorrectly; devices are automatically detected and the correct driver is loaded; USB also supplies power so some devices do not need a separate power source; data transfer rates are high and improve with each generation (USB 2, 3, 3.1, etc.). Disadvantages: cable length is limited to about 5 m for USB 2; older USB versions are slower than specialised alternatives.

## Errors during transmission

Errors can happen because of electrical interference, poor-quality cables, loss of signal, or skew in parallel transmission. An error may be a bit being flipped, a bit being lost, or bits being duplicated.

## Error detection methods

Parity check: an extra bit, the parity bit, is added to each byte so that the total number of 1s is odd (odd parity) or even (even parity). When the byte arrives the receiver counts the 1s; if the count does not match the expected parity an error is reported. Parity detects an odd number of bit errors but cannot detect an even number, and cannot correct errors.

Checksum: the sender adds up the bytes in a block using a defined rule and sends the checksum along with the data. The receiver performs the same calculation; if the result differs, an error is reported and the block is retransmitted.

Echo check: the receiver sends the data back to the sender; the sender compares the returned data with the original. Simple but doubles the traffic, and if the same error occurs on the echo it fails.

Check digit: an extra digit added to a number (for example the last digit of an ISBN or a credit-card number) calculated from the other digits using a defined algorithm. Used on human-entered numbers to catch typing mistakes.

Automatic repeat request (ARQ): the receiver acknowledges each packet (ACK) or requests a resend (NAK). If the sender does not receive an ACK within a set time, or receives a NAK, it retransmits the packet.

## Why encryption is useful

Encryption converts plaintext into ciphertext that is unreadable without the correct key. Even if an attacker intercepts the data in transit, they cannot read or usefully alter it. Encryption protects confidentiality on open networks such as the internet.

## Symmetric and asymmetric encryption

Symmetric encryption uses one shared key for both encryption and decryption. The sender and receiver must both have the same secret key, and the key must be shared securely beforehand. Symmetric encryption is fast and suitable for encrypting large amounts of data. If the key is intercepted, all data is compromised.

Asymmetric encryption uses a key pair: a public key and a private key. Anything encrypted with the public key can only be decrypted with the matching private key. The public key can be published openly. Asymmetric encryption solves the key-distribution problem but is computationally slower than symmetric encryption. In practice, asymmetric encryption is typically used only to securely exchange a symmetric session key, and the session key is then used for the bulk of the data transfer.
