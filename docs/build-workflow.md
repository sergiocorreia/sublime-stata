# Package-test build workflow

The `Run Package Test (build.txt)` build variant is for developing an ado or Mata package while
keeping its integration test in the active Stata GUI session.

Place `build.txt` beside the saved `.ado` or `.mata` source. Its only nonblank, non-comment line is the
test do-file path, relative to that directory unless absolute:

```text
tests/test_mycommand.do
```

Quoted paths and a UTF-8 BOM are accepted. Select the variant with <kbd>Ctrl+Shift+B</kbd>. The target
file is read from disk, run with the `build.txt` directory as Stata's working directory, and delivered
through the same selected/pinned backend as a normal build.

The variant stops with an explicit error when the active source is unsaved, is not `.ado`/`.mata`, the
pointer is missing or contains more than one target, the target does not exist, or the file cannot be
decoded. It never substitutes the active buffer after a build-pointer failure.
