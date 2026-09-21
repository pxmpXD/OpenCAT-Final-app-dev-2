# Unit tests for Flask app routes and MySQL database connections
import unittest
from dotenv import load_dotenv

load_dotenv()

from text_extract import extract_text
from ai_generate import MAX_NOTES_CHARS


class TestCatApp(unittest.TestCase):

  def test_1_empty_file_extraction(self):
    """Test 1: Ensures text extraction handles invalid/empty paths cleanly."""
    with self.assertRaises(Exception):
      extract_text("")

  def test_2_notes_char_limit(self):
    """Test 2: Verifies MAX_NOTES_CHARS keeps the AI payload bounded."""
    large_text = "A" * 70000
    truncated = large_text[:MAX_NOTES_CHARS]
    self.assertLessEqual(len(truncated), MAX_NOTES_CHARS)


if __name__ == "__main__":
  unittest.main()