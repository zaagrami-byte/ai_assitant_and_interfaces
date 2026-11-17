"""Énumération isolée : certaines piles PortAudio restent bloquées si le serveur disparaît."""

import json


def main():
    import sounddevice as sd

    devices = [
        (str(i), device["name"])
        for i, device in enumerate(sd.query_devices())
        if device["max_input_channels"]
    ]
    print(json.dumps(devices, ensure_ascii=False))


if __name__ == "__main__":
    main()
