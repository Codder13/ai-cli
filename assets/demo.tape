# Render from the repo root: vhs assets/demo.tape
Output assets/demo.gif

Set FontSize 14
Set FontFamily "CaskaydiaMono Nerd Font"
Set LineHeight 1.25
Set Width 1240
Set Height 780
Set Padding 20
Set Theme "Catppuccin Mocha"
Set WindowBar "Colorful"
Set BorderRadius 8
Set TypingSpeed 28ms

# Reset session cleanly before starting
Hide
Type "export NO_COLOR="
Enter
Type "ai --clear"
Enter
Type "clear"
Enter
Show

Sleep 400ms

# 1. Everyday CLI query with syntax-highlighted code
Type "ai how to find files larger than 100MB in current dir?"
Sleep 300ms
Enter
Sleep 8s

# 2. Terminal tab session continuity without quotes
Type "ai now sort them by size"
Sleep 300ms
Enter
Sleep 8s

Type "clear"
Enter
Sleep 400ms

# 3. Unix pipeline processing via stdin
Type "echo 'def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)' | ai make this iterative in python"
Sleep 400ms
Enter
Sleep 8s

Type "clear"
Enter
Sleep 400ms

# 4. Git workflow integration
Type "git diff PKGBUILD | ai write a concise commit message"
Sleep 400ms
Enter
Sleep 8s

Type "clear"
Enter
Sleep 400ms

# 5. On-the-fly harness switching
Type "ai -a omp write a fast oneliner to find external IP"
Sleep 400ms
Enter
Sleep 8s

Type "clear"
Enter
Sleep 400ms

# 6. Raw Unix pipe composition
Type "ai --raw calculate 2 to the power of 16 | tr -d ' ' | rev"
Sleep 400ms
Enter
Sleep 6s

Type "clear"
Enter
Sleep 400ms

# 7. LaTeX Math rendering into clean terminal Unicode
Type "ai show the quadratic formula and gaussian integral in LaTeX"
Sleep 300ms
Enter
Sleep 8s

Type "ai now give me Euler identity"
Sleep 300ms
Enter
Sleep 8s

Sleep 2s
