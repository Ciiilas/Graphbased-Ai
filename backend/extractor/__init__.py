"""Scala extraction components."""

from backend.extractor.ast_serializer import AstSerializer
from backend.extractor.parser import ScalaTreeSitterParser
from backend.extractor.relations import RelationExtractor
from backend.extractor.scanner import ScalaFileScanner
from backend.extractor.symbols import SymbolExtractor

__all__ = [
    "AstSerializer",
    "RelationExtractor",
    "ScalaFileScanner",
    "ScalaTreeSitterParser",
    "SymbolExtractor",
]
