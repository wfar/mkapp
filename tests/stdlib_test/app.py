import time

if __name__ == "__main__":
    print("Hello World!")
    print(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
