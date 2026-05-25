import sys
from data_wrangler import wrangle
from db import drop, create, insert, backup

def main():
    try:
        data = wrangle(src_dir='data', round_digits=4)
        drop()
        create()
        insert(data)
        backup()
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
