program define dodo
    // Parse input: first token is filename, remainder are arguments
    gettoken filename args : 0

    // Add .do if not there
    loc has_extension = strpos("`filename'", ".do") + 2 == strlen("`filename'")
    if (!`has_extension') loc filename "`filename'.do"
    
    // 1. Verify the file exists
    capture confirm file "`filename'"
    if _rc {
        di as error "Error: File `filename' not found!"
        exit 601
    }

    // 2. Always copy to a temporary file
    tempfile tempdo
    copy "`filename'" "`tempdo'", replace

    // 3. Verbose status update and window title
    di as text `"Executing {stata doedit "`filename'":`filename'} (copy)..."'
    window manage maintitle "Running: `filename'"
    di as text "{hline 60}"

    // 4. Execute the temporary do-file with any arguments
    capture noisily do "`tempdo'" `args'
    local rc = _rc
    cap cd "$code"

    // 5. Crash Handling
    if (`rc' != 0) {
        di as text "{hline 60}"
        di as error `"CRASH DETECTED IN: {stata doedit "`filename'":`filename'}"'
        di as error "Return code: `rc'"
        
        // Update the window title to show the crash
        window manage maintitle "CRASHED: `filename' (`rc')"


        // Beep (comment out if not Sergio)
        !quack.wav
        
        // Stop the master script and pass the error code up
        exit `rc'
    }

    // 6. Reset window title to empty upon success
    *window title ""
    window manage maintitle reset


end
