import time
import fu_ui as ui

ui.logo()

ui.header("FU REQUEST", "◆")
ui.info("Platform", "ubuntu x86_64")
ui.info("Mode", "retrieval-first")
ui.info("Workspace", "~/Desktop/FU-Workspace")

print()

ui.progress("Curated KB", 100, 100)
time.sleep(.15)

ui.progress("TLDR", 100, 100)
time.sleep(.15)

ui.progress("Commandlinefu", 100, 100)
time.sleep(.15)

ui.source_line("TLDR", 66)
ui.source_line("COMMANDLINEFU", 93)

ui.command_box(
    'find "$HOME/Downloads" -type f -printf \'%s %p\\n\' | '
    'sort -nr | head -n 10'
)

ui.auto_approved()
ui.success("Completed")
ui.timing(0.143)
