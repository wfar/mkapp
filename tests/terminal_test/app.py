import requests

if __name__ == "__main__":
    response = requests.get("https://httpbin.org/get", timeout=10)
    response.raise_for_status()
    for i in range(10, 0, -1):
        print(f"Countdown {i}...")

    print(f"Response payload: {response.json()}")
