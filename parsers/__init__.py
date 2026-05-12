"""parsers package — converts various input formats to normalised descriptions."""
from .nlp_parser         import NLPParser
from .json_parser        import JSONParser
from .pdf_parser         import PDFParser

__all__ = ["NLPParser", "JSONParser", "PDFParser"]
