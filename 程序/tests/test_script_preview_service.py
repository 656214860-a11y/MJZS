import tempfile
import unittest
from pathlib import Path

from script_preview_service import (ASYNC_PREVIEW_BYTES, PREVIEW_CHUNK_CHARS, READ_ERROR,
                                    preview_chunks, read_preview, should_load_async)


class ScriptPreviewServiceTests(unittest.TestCase):
    def test_small_and_large_file_choose_expected_loading_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            small = Path(folder) / 'small.md'
            large = Path(folder) / 'large.md'
            small.write_text('小剧本', encoding='utf-8')
            large.write_bytes(b'x' * (ASYNC_PREVIEW_BYTES + 1))
            self.assertFalse(should_load_async(small))
            self.assertTrue(should_load_async(large))

    def test_missing_file_uses_page_empty_text(self):
        self.assertEqual(read_preview(Path(tempfile.gettempdir()) / 'missing-script.md', '暂无剧本'), '暂无剧本')

    def test_text_is_read_through_preview_service(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'script.md'
            path.write_text('自然语言剧本', encoding='utf-8')
            self.assertEqual(read_preview(path), '自然语言剧本')

    def test_preview_chunks_preserve_order_and_bound_size(self):
        text = '剧本段落' * (PREVIEW_CHUNK_CHARS // 2 + 3)
        chunks = list(preview_chunks(text))
        self.assertGreater(len(chunks), 1)
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(chunk) <= PREVIEW_CHUNK_CHARS for chunk in chunks))
