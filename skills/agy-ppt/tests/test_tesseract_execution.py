import hashlib, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, "skills/agy-ppt/scripts")
from ocr_providers import OCRError, OCRRequest, ProcessResult, TesseractProvider, parse_tsv

TSV="level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tHello\n5\t1\t1\t1\t1\t2\t10\t0\t10\t10\t80\t世界\n"
class Runner:
    def __init__(self, result): self.result=result; self.calls=[]
    def run(self, argv): self.calls.append(argv); return self.result
class ExecutionTests(unittest.TestCase):
    def test_tsv_parse_text_regions_confidence(self):
        raw, regions=parse_tsv(TSV, {"image_dimensions":(20,20)})
        self.assertEqual(raw,"Hello 世界"); self.assertEqual(regions[0]["region_id"],"w-1-1-1-1-1"); self.assertEqual(regions[0]["confidence"]["raw_confidence"],90.0)
    def test_malformed_tsv_rejected(self):
        with self.assertRaises(OCRError) as c: parse_tsv("bad\theader\n")
        self.assertEqual(c.exception.error_code,"OCR_PROVIDER_OUTPUT_INVALID")
    def test_model_change_prevents_execution(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d,"eng.traineddata"); p.write_bytes(b"a"); t=TesseractProvider("t",runner=Runner(ProcessResult(0,TSV,"")),tessdata_dir=d); old=t.discover_traineddata("eng"); p.write_bytes(b"b")
            with self.assertRaises(OCRError) as c: t.recognize(OCRRequest(b"i","s",hashlib.sha256(b"raw").hexdigest(),{"kind":"image","ordinal":1}),expected_models=old)
            self.assertEqual(c.exception.error_code,"OCR_MODEL_CHANGED")
    def test_unchanged_model_executes_and_preserves_source_digest(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,"eng.traineddata").write_bytes(b"a")
            runner=Runner(ProcessResult(0,TSV,"")); t=TesseractProvider("t",runner=runner,tessdata_dir=d)
            old=t.discover_traineddata("eng"); digest=hashlib.sha256(b"raw").hexdigest()
            out=t.recognize(OCRRequest(b"i","s",digest,{"kind":"image","ordinal":1}),expected_models=old)
            self.assertEqual(out.source_digest,digest); self.assertEqual(len(runner.calls),1)
            self.assertEqual(runner.calls[0][3:6], ["--tessdata-dir", d, "tsv"])
