To update built-in commands:

1. Download [strings2](http://split-code.com/strings2.html)

2. Run it:

```
strings2 -a -nh StataMP-64.exe > builtin_candidates.txt
```

3. Get list of ados:

```
ls -A1 */*.ado > ~/ados.txt
```

4. Run do-file
