import os
import sys
import re
from collections import Counter
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text
import pikepdf
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional


class PDFAnalyzer:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.fixed_pdf_path = None
        self.original_filename = os.path.basename(pdf_path)
        self.file_dir = os.path.dirname(os.path.abspath(pdf_path))

    def repair_pdf(self):
        """Attempt to repair a corrupted PDF file"""
        try:
            print(f"PDF structure issues detected, attempting to repair file: {self.original_filename}")

            # Check file integrity
            file_size = os.path.getsize(self.pdf_path)
            if file_size < 100:
                raise ValueError(f"File too small ({file_size} bytes), possibly incomplete")

            # Use timestamp to ensure unique filename
            timestamp = os.path.getmtime(self.pdf_path)
            base_name, ext = os.path.splitext(self.original_filename)
            fixed_name = f"{base_name}_fixed_{int(timestamp)}{ext}"
            fixed_path = os.path.join(self.file_dir, fixed_name)

            # Safely repair PDF
            with pikepdf.open(self.pdf_path) as pdf:
                pdf.save(fixed_path)

            print(f"Repaired version created: {os.path.basename(fixed_path)}")
            return fixed_path

        except Exception as e:
            print(f"Repair failed: {e}")
            return None

    def extract_text(self):
        """Extract text from PDF using multiple methods"""
        methods = [
            self._try_pypdf2,
            self._try_pdfminer,
            self._try_bytes_repair,
        ]

        # Try all methods
        text = ""
        for method in methods:
            try:
                method_name = method.__name__.replace('_try_', '')
                print(f"Attempting method: {method_name}")
                text = method()
                if text and len(text) > 100:  # Ensure sufficient content
                    print(f"Successfully extracted {len(text):,} characters")
                    return self._clean_extracted_text(text)  # Clean extracted text
            except Exception as e:
                print(f"Method failed: {str(e)[:50]}...")

        # If all methods fail, try repairing then retrying
        print("\nRegular extraction failed, attempting to repair PDF...")
        self.fixed_pdf_path = self.repair_pdf()
        if self.fixed_pdf_path:
            methods_fixed = [
                self._try_pypdf2_fixed,
                self._try_pdfminer_fixed,
                self._try_bytes_repair_fixed,
            ]

            for method in methods_fixed:
                try:
                    method_name = method.__name__.replace('_try_', '').replace('_fixed', '')
                    print(f"Attempting post-repair method: {method_name}")
                    text = method()
                    if text and len(text) > 100:  # Ensure sufficient content
                        print(f"Successfully extracted {len(text):,} characters")
                        return self._clean_extracted_text(text)  # Clean extracted text
                except Exception as e:
                    print(f"Method failed: {str(e)[:50]}...")

        print("\nAll extraction methods failed!")
        return ""

    def _clean_extracted_text(self, text):
        """Clean extracted text by removing invalid characters"""
        # 1. Remove all CID markers (cid:xxx)
        text = re.sub(r'\(cid:\d+\)', '', text)

        # 2. Remove control characters (except newlines and tabs)
        # Build allowed control characters set (newline, tab, and space)
        allowed_controls = {'\n', '\t', ' '}

        # Filter out other control characters
        cleaned_text = ''.join(
            c for c in text
            if (c in allowed_controls) or (ord(c) >= 32 and ord(c) != 127)
        )

        # 3. Compress excess whitespace
        # Compress multiple spaces into single space
        cleaned_text = re.sub(r'[ \t]{2,}', ' ', cleaned_text)
        # Compress multiple newlines into double newline
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        # Remove leading/trailing whitespace from lines
        cleaned_text = '\n'.join(line.strip() for line in cleaned_text.split('\n'))

        # 4. Remove isolated blank lines
        cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)

        print(f"After text cleaning: {len(cleaned_text):,} characters (removed {len(text) - len(cleaned_text):,} invalid characters)")
        return cleaned_text

    def _try_pypdf2(self):
        """Extract text using PyPDF2 (supports multithreading)"""
        with open(self.pdf_path, 'rb') as file:
            pdf = PdfReader(file)

            # Attempt to decrypt encrypted PDF
            if pdf.is_encrypted:
                try:
                    pdf.decrypt("")  # Try empty password
                except Exception as e:
                    print(f"Decryption failed: {e}")

            # Use multithreading to extract text
            def extract_page(page):
                text = page.extract_text() or ""
                return text + "\n"

            with ThreadPoolExecutor() as executor:
                pages = list(pdf.pages)
                texts = list(executor.map(extract_page, pages))

            return "".join(texts)

    def _try_pdfminer(self):
        """Extract text using pdfminer"""
        return extract_text(self.pdf_path)

    def _try_bytes_repair(self):
        """Attempt byte-level repair and then extract text"""
        print("Attempting byte-level repair...")
        with open(self.pdf_path, 'rb') as file:
            data = file.read()

        # Check and repair EOF marker
        if not data.rstrip().endswith(b'%%EOF'):
            print("Adding missing EOF marker")
            data = data.rstrip() + b'\n%%EOF\n'

        # Check cross-reference table
        if b'startxref' not in data:
            print("Rebuilding basic structure")
            trailer = b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF"
            data = data + trailer % (1, len(data))

        # Use repaired data
        fixed_name = os.path.splitext(self.original_filename)[0] + "_byte_fixed.pdf"
        fixed_path = os.path.join(self.file_dir, fixed_name)
        with open(fixed_path, 'wb') as f:
            f.write(data)

        # Attempt to extract text from repaired file using PyPDF2
        try:
            with open(fixed_path, 'rb') as file:
                pdf = PdfReader(file)
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text
        except Exception as e:
            print(f"PyPDF2 extraction from repaired file failed: {e}")

        # Use pdfminer as fallback
        try:
            return extract_text(fixed_path)
        except Exception as e:
            print(f"pdfminer extraction from repaired file failed: {e}")
            return ""

    def _try_pypdf2_fixed(self):
        """Extract text using PyPDF2 on repaired version"""
        if not self.fixed_pdf_path:
            return ""

        with open(self.fixed_pdf_path, 'rb') as file:
            pdf = PdfReader(file)

            # Attempt to decrypt encrypted PDF
            if pdf.is_encrypted:
                try:
                    pdf.decrypt("")  # Try empty password
                except Exception as e:
                    print(f"Decryption of repaired file failed: {e}")

            # Use multithreading to extract text
            def extract_page(page):
                text = page.extract_text() or ""
                return text + "\n"

            with ThreadPoolExecutor() as executor:
                pages = list(pdf.pages)
                texts = list(executor.map(extract_page, pages))

            return "".join(texts)

    def _try_pdfminer_fixed(self):
        """Extract text using pdfminer on repaired version"""
        if not self.fixed_pdf_path:
            return ""
        return extract_text(self.fixed_pdf_path)

    def _try_bytes_repair_fixed(self):
        """Apply byte-level repair + extraction on repaired version"""
        if not self.fixed_pdf_path:
            return ""

        print("Attempting byte-level repair on repaired version...")
        with open(self.fixed_pdf_path, 'rb') as file:
            data = file.read()

        # Check and repair EOF marker
        if not data.rstrip().endswith(b'%%EOF'):
            print("Adding missing EOF marker")
            data = data.rstrip() + b'\n%%EOF\n'

        # Check cross-reference table
        if b'startxref' not in data:
            print("Rebuilding basic structure")
            trailer = b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF"
            data = data + trailer % (1, len(data))

        # Use repaired data
        fixed_name = os.path.splitext(self.original_filename)[0] + "_fixed_byte_fixed.pdf"
        fixed_path = os.path.join(self.file_dir, fixed_name)
        with open(fixed_path, 'wb') as f:
            f.write(data)

        # Attempt to extract using pdfminer
        try:
            return extract_text(fixed_path)
        except Exception as e:
            print(f"pdfminer extraction from repaired file failed: {e}")
            return ""

    def _count_characters_accurate(self, text, characters_to_count: List[str]):
        """More accurate character counting method"""
        # Create character set
        char_set = set()
        for char in characters_to_count:
            char_set.add(char)
            # Add common variants
            if char == '"':
                char_set.update(['"', '＂', '“', '”', '〝', '〞', '〟', '＂', '‟', '˝'])
            elif char == "'":
                char_set.update(["'", '＇', '‘', '’', '`', '´'])
            elif char == "!":
                char_set.update(['!', '！'])

        # Counters
        counters = {
            'digits': Counter(),  # Will track each digit separately
            'other_chars': Counter()
        }

        # Process each character in text
        for char in text:
            # Normalize character for consistency
            normalized = unicodedata.normalize('NFC', char)

            # Check if in character set
            if normalized in char_set:
                if normalized.isdigit():
                    counters['digits'][normalized] += 1
                else:
                    counters['other_chars'][normalized] += 1

        # Calculate total digits
        total_digits = sum(counters['digits'].values())
        total_other = sum(counters['other_chars'].values())

        return counters, total_digits, total_other

    def count_characters(self, text, characters_to_count: List[str]):
        """Count characters (using more accurate method)"""
        return self._count_characters_accurate(text, characters_to_count)

    def generate_report(self, counters, total_digits, total_other, characters_to_count: List[str]):
        """Generate report"""
        # Calculate total relevant characters
        total_relevant = total_digits + total_other

        report = []
        report.append(f"==== Character Statistical Analysis Report for {self.original_filename} ====")
        report.append("\n【Summary】")
        report.append(f"Total characters queried: {total_relevant:,}")

        # Digit distribution statistics
        if total_digits > 0:
            report.append("\n【Digit Distribution】")
            for digit in '0123456789':
                count = counters['digits'].get(digit, 0)
                if count > 0:
                    percentage = count / total_digits
                    report.append(f"  {digit}: {count:,} times ({percentage:.1%})")

        # Other character statistics
        if total_other > 0:
            report.append("\n【Other Characters】")
            for char, count in counters['other_chars'].items():
                report.append(f"  '{char}': {count:,} times")

        # Included character variants explanation
        report.append("\n【Character Variants Explanation】")
        report.append(f"* Queried characters: {', '.join(characters_to_count)}")
        report.append("* Statistics include all Unicode variant characters")
        report.append("* Filtered out CID characters, control characters, and invalid whitespace")

        # Repaired file information
        if self.fixed_pdf_path:
            report.append("\n【Note】")
            report.append(f"* Used repaired version: {os.path.basename(self.fixed_pdf_path)}")
            report.append("* Results may be incomplete, verify with original file")

        return "\n".join(report)

    def run_analysis(self, characters_to_count: List[str] = None):
        """Execute full analysis workflow"""
        print(f"\nStarting analysis: {self.original_filename}")

        # Verify file exists
        if not os.path.isfile(self.pdf_path):
            raise FileNotFoundError(f"File does not exist: {self.pdf_path}")

        # Set default query characters
        if characters_to_count is None:
            characters_to_count = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '"', "'", "!"]
            print(f"Using default query characters: {characters_to_count}")
        else:
            print(f"Query characters: {characters_to_count}")

        # Attempt repair and text extraction
        text = self.extract_text()

        if not text or len(text) < 100:
            print("\nFailed to extract valid text content!")
            file_size = os.path.getsize(self.pdf_path)
            if file_size < 1024:
                print(f"File may be incomplete or corrupted (size: {file_size} bytes)")
            return

        # Accurately count characters
        counters, total_digits, total_other = self.count_characters(text, characters_to_count)

        # Generate report
        report = self.generate_report(counters, total_digits, total_other, characters_to_count)

        print("\n" + "=" * 60)
        print(report)
        print("=" * 60)
        return report


from oxygent import oxy
analyze_pdf_character = oxy.FunctionHub(name="analyze_pdf_character_tool", timeout=900)


# @analyze_pdf_character.tool(description="Analyze the frequency of specific characters in a PDF file")
def analyze_pdf_characters_api(
        pdf_path: str,
        characters_to_count: Optional[List[str]] = None,
) -> str:
    """
    Analyze the frequency of specific characters in a PDF file

    Parameters:
    pdf_path: Full path to the PDF file
    characters_to_count: List of characters to count

    Returns:
    Dictionary containing analysis results
    """
    analyzer = PDFAnalyzer(pdf_path)
    # Return results
    return analyzer.run_analysis(characters_to_count)


if __name__ == "__main__":
    print("PDF Character Statistical Analysis Tool - Enhanced Version")
    print("=" * 60)

    # Get file path from command line or use default
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default to your test file path
        pdf_path = "****.pdf"

    # Verify file exists
    if not os.path.isfile(pdf_path):
        print(f"Error: File does not exist - {pdf_path}")
        sys.exit(1)

    print(f"Analyzing file: {os.path.basename(pdf_path)}")

    # Define characters to query
    characters_to_query = [ '0', '"', "'", "!"]

    # Run analysis
    result = analyze_pdf_characters_api(
        pdf_path=pdf_path,
        characters_to_count=characters_to_query,
    )

    # Output result information
    print("\nAnalysis complete")
    print(result)
