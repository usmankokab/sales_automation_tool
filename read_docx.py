import sys
import docx2txt

def main():
    if len(sys.argv) < 2:
        print("Usage: python read_docx.py <docx_file>")
        sys.exit(1)
    docx_file = sys.argv[1]
    text = docx2txt.process(docx_file)
    print(text)

if __name__ == "__main__":
    main()