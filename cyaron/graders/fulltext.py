import hashlib
from .graderregistry import CYaRonGraders
from .mismatch import HashMismatch

@CYaRonGraders.grader("FullText")
def fulltext(content, std):
    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    std_hash = hashlib.sha256(std.encode('utf-8')).hexdigest()
    if content_hash == std_hash:
        return (True, None)
    else:
        return (False, HashMismatch(content, std, content_hash, std_hash))

