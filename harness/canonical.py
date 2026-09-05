"""The canonical text form of blueprint 9.2, frozen: Unicode NFKC, soft hyphens joined, every run of whitespace
collapsed to one space, trimmed; case and punctuation kept. The identity of a quoted span is the SHA-256 of its
canonical form encoded as UTF-8.

`canonical` is the one implementation the harness uses everywhere (harness.pdftext defines it, every module reads it
through there); this module is its named home for the two-lane equality test (the application ports it as
src/lib/canonical.ts) and adds the hash.
"""

import hashlib

from .pdftext import canonical

__all__ = ["canonical", "quote_hash"]


def quote_hash(text):
    """sha256 over canonical(text) encoded as UTF-8, hex."""
    return hashlib.sha256(canonical(text).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    assert canonical("a­b  c\n\td ") == "ab c d"
    assert canonical("ﬁ") == "fi"
    assert (
        quote_hash(" x  y ") == quote_hash("x y") == hashlib.sha256(b"x y").hexdigest()
    )
    print("canonical: ok")
