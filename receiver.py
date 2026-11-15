import socket
import struct
import time
import argparse

HEADER = struct.Struct("!Id")


def start_receiver(host, port, expected, timeout):

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.settimeout(timeout)

    received_sequences = set()
    total_bytes = 0
    delays = []

    first_arrival = None
    last_arrival = None

    print(f"UDP Receiver listening on {host}:{port}")

    while True:
        try:
            data, address = sock.recvfrom(65535)
        except socket.timeout:
            break

        arrival_time = time.time()

        if len(data) < HEADER.size:
            continue

        sequence, sent_time = HEADER.unpack(data[:HEADER.size])

        if sequence in received_sequences:
            continue

        received_sequences.add(sequence)
        total_bytes += len(data)

        delays.append((arrival_time - sent_time) * 1000)

        if first_arrival is None:
            first_arrival = arrival_time

        last_arrival = arrival_time

    sock.close()

    received = len(received_sequences)
    lost = max(0, expected - received)

    loss_percentage = (
        lost / expected * 100 if expected > 0 else 0
    )

    duration = (
        last_arrival - first_arrival
        if first_arrival is not None and last_arrival > first_arrival
        else 0
    )

    throughput = (
        total_bytes * 8 / duration / 1_000_000
        if duration > 0 else 0
    )

    average_delay = (
        sum(delays) / len(delays) if delays else 0
    )

    print("\n----- UDP RECEIVER RESULTS -----")
    print("Expected packets:", expected)
    print("Received packets:", received)
    print("Lost packets:", lost)
    print(f"Packet loss: {loss_percentage:.2f}%")
    print(f"Received bytes: {total_bytes}")
    print(f"Throughput: {throughput:.4f} Mbps")
    print(f"Average delay: {average_delay:.3f} ms")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--expected", type=int, default=1000)
    parser.add_argument("--timeout", type=int, default=5)

    args = parser.parse_args()

    start_receiver(
        args.host,
        args.port,
        args.expected,
        args.timeout
    )
