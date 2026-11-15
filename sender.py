import socket
import struct
import time
import argparse

HEADER = struct.Struct("!Id")


def start_sender(host, port, count, rate, payload_size):

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    destination = (host, port)
    payload = b"X" * payload_size

    interval = 1 / rate if rate > 0 else 0

    sent_bytes = 0
    successful_sends = 0

    start_time = time.time()

    print(f"Sending UDP traffic to {host}:{port}")

    for sequence in range(count):

        sent_time = time.time()

        packet = HEADER.pack(sequence, sent_time) + payload

        try:
            bytes_sent = sock.sendto(packet, destination)
            sent_bytes += bytes_sent
            successful_sends += 1

        except OSError as error:
            print("Send error:", error)

        target_time = start_time + (sequence + 1) * interval
        remaining = target_time - time.time()

        if remaining > 0:
            time.sleep(remaining)

    elapsed = time.time() - start_time

    sock.close()

    throughput = (
        sent_bytes * 8 / elapsed / 1_000_000
        if elapsed > 0 else 0
    )

    print("\n----- UDP SENDER RESULTS -----")
    print("Packets sent:", successful_sends)
    print("Bytes sent:", sent_bytes)
    print(f"Elapsed time: {elapsed:.3f} seconds")
    print(f"Sending throughput: {throughput:.4f} Mbps")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--rate", type=int, default=500)
    parser.add_argument("--payload-size", type=int, default=1024)

    args = parser.parse_args()

    start_sender(
        args.host,
        args.port,
        args.count,
        args.rate,
        args.payload_size
    )
